"""Passwortwechsel und der Platzhalter-Hash der Saganta-Konten.

Jeder Test prueft **beide** Richtungen: dass der richtige Weg traegt UND dass
der falsche abgewiesen wird. Eine Pruefung, die nur den Erfolgsfall kennt, ist
bei Zugangsdaten wertlos, sie bleibt gruen, wenn die Sperre ganz fehlt.

Gelaufen wird gegen die **ausgelieferte** App (``app.main:app``) mit einer
Wegwerf-Datenbank, nicht gegen einen Nachbau der Routen. Ein Nachbau beweist,
dass die Idee stimmt, nicht dass der Dienst sie hat.

Lauf: ``bash run-tests.sh``
"""

import os
import tempfile
import unittest

ALT = "altes-geheimnis-123"
NEU = "neues-geheimnis-456"


def _frische_app():
    """App plus eigene SQLite-Datei, die Dienst-Datenbank bleibt unberuehrt.

    ``get_db`` wird ueber ``dependency_overrides`` ersetzt und nicht ueber
    die Umgebung: ``app.db`` baut seine Engine beim Import, eine spaeter
    gesetzte ``DATABASE_URL`` wuerde also nichts mehr aendern. Genau so ein
    stiller Fehlgriff liesse den Test gegen ``/tmp/nicht-benutzt.db`` laufen
    und trotzdem gruen aussehen.
    """
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app import main as main_modul
    from app.db import Base, get_db
    from app.models import User  # noqa: F401  Tabellen registrieren

    pfad = tempfile.mkdtemp(prefix="postfach-pruefung-")
    engine = create_engine(f"sqlite:///{os.path.join(pfad, 'pruefung.db')}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Sitzung = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _test_db():
        db = Sitzung()
        try:
            yield db
        finally:
            db.close()

    main_modul.app.dependency_overrides[get_db] = _test_db
    # Der Rate-Limiter zaehlt pro IP und ueber Modul-Zustand hinweg. Ohne das
    # Leeren summieren sich die Tests gegenseitig auf und der letzte bekommt 429.
    main_modul._rate_store.clear()
    return TestClient(main_modul.app), Sitzung


class PlatzhalterHash(unittest.TestCase):
    """``!saganta`` im Feld ``password_hash`` darf nie eine Ausnahme werfen."""

    def test_pruefung_gegen_platzhalter_ist_falsch_und_wirft_nicht(self):
        """Der Kern: ``bcrypt.checkpw`` wirft hier ``ValueError``.

        Ohne das Abfangen antwortet ``/login`` mit 500 statt 401, sobald jemand
        den Namen eines automatisch angelegten Saganta-Postfachs raet. Ein 500
        gegen ein 401 ist zugleich die Auskunft, dass der Name existiert.
        """
        from app.auth import OHNE_PASSWORT, verify_password
        self.assertFalse(verify_password("irgendwas", OHNE_PASSWORT))
        self.assertFalse(verify_password("", OHNE_PASSWORT))

    def test_echter_hash_wird_weiter_richtig_geprueft(self):
        """Gegenprobe: das Abfangen darf nicht alles auf False ziehen."""
        from app.auth import hash_password, verify_password
        h = hash_password(ALT)
        self.assertTrue(verify_password(ALT, h))
        self.assertFalse(verify_password(NEU, h))

    def test_anmeldeweg_haengt_am_hash_und_nicht_am_sub(self):
        """Ein von Hand gebundenes Konto hat Sub **und** Passwort.

        Eine Pruefung auf ``user.sub`` wuerde genau ihm die Passwortaenderung
        wegnehmen, und das ist das einzige echte Konto in diesem Dienst.
        """
        from types import SimpleNamespace
        from app.auth import OHNE_PASSWORT, hash_password, hat_passwort_anmeldung
        gebunden = SimpleNamespace(password_hash=hash_password(ALT), sub="KONTO-A")
        reines_saganta = SimpleNamespace(password_hash=OHNE_PASSWORT, sub="KONTO-B")
        ohne_alles = SimpleNamespace(password_hash="", sub=None)
        self.assertTrue(hat_passwort_anmeldung(gebunden))
        self.assertFalse(hat_passwort_anmeldung(reines_saganta))
        self.assertFalse(hat_passwort_anmeldung(ohne_alles))


class Wechsel(unittest.TestCase):
    """Der Endpunkt, gegen die ausgelieferte App."""

    def setUp(self):
        self.client, self.Sitzung = _frische_app()
        self.addCleanup(self.client.close)
        antwort = self.client.post("/api/auth/register", json={
            "username": "pruefkonto", "password": ALT, "display_name": "Pruefkonto",
        })
        self.assertEqual(antwort.status_code, 201, antwort.text)

    def test_wechsel_traegt_und_das_alte_passwort_gilt_danach_nicht_mehr(self):
        antwort = self.client.post("/api/auth/change-password", json={
            "current_password": ALT, "new_password": NEU,
        })
        self.assertEqual(antwort.status_code, 204, antwort.text)

        self.client.post("/api/auth/logout")
        alt = self.client.post("/api/auth/login", json={
            "username": "pruefkonto", "password": ALT,
        })
        self.assertNotEqual(alt.status_code, 200, "das alte Passwort gilt noch")
        neu = self.client.post("/api/auth/login", json={
            "username": "pruefkonto", "password": NEU,
        })
        self.assertEqual(neu.status_code, 200, neu.text)

    def test_falsches_aktuelles_passwort_wird_abgewiesen(self):
        antwort = self.client.post("/api/auth/change-password", json={
            "current_password": "falsch-falsch", "new_password": NEU,
        })
        self.assertEqual(antwort.status_code, 401, antwort.text)
        # Gegenprobe: der Wechsel hat NICHT stattgefunden.
        weiter = self.client.post("/api/auth/change-password", json={
            "current_password": ALT, "new_password": NEU,
        })
        self.assertEqual(weiter.status_code, 204, weiter.text)

    def test_ohne_anmeldung_kein_wechsel(self):
        """Der wichtigste Negativfall: ein Fremder darf hier nicht hinein."""
        anonym = TestClientOhneCookies(self.client)
        antwort = anonym.post("/api/auth/change-password", json={
            "current_password": ALT, "new_password": NEU,
        })
        self.assertEqual(antwort.status_code, 401, antwort.text)

    def test_neues_passwort_darf_nicht_das_alte_sein(self):
        """Sonst meldet der Dienst Erfolg, ohne dass sich etwas aendert."""
        antwort = self.client.post("/api/auth/change-password", json={
            "current_password": ALT, "new_password": ALT,
        })
        self.assertEqual(antwort.status_code, 422, antwort.text)

    def test_zu_kurzes_passwort_wird_abgewiesen(self):
        antwort = self.client.post("/api/auth/change-password", json={
            "current_password": ALT, "new_password": "kurz",
        })
        self.assertEqual(antwort.status_code, 422, antwort.text)

    def test_andere_sitzungen_enden_die_eigene_bleibt(self):
        """Ein Passwortwechsel ist der Griff gegen einen fremden Zugriff.

        Bleiben die alten Sitzungen gueltig (72 h), hat er genau das nicht
        getan. Die eigene muss zugleich ueberleben, sonst sieht ein gelungener
        Wechsel wie ein Rauswurf aus.
        """
        zweites_geraet = TestClientOhneCookies(self.client)
        anmeldung = zweites_geraet.post("/api/auth/login", json={
            "username": "pruefkonto", "password": ALT,
        })
        self.assertEqual(anmeldung.status_code, 200, anmeldung.text)
        self.assertEqual(zweites_geraet.get("/api/auth/me").status_code, 200)

        self.client.post("/api/auth/change-password", json={
            "current_password": ALT, "new_password": NEU,
        })

        self.assertEqual(zweites_geraet.get("/api/auth/me").status_code, 401,
                         "die fremde Sitzung lebt nach dem Wechsel weiter")
        self.assertEqual(self.client.get("/api/auth/me").status_code, 200,
                         "die eigene Sitzung wurde mit abgeraeumt")

    def test_me_meldet_den_anmeldeweg(self):
        """Die Oberflaeche entscheidet daran, ob sie das Formular zeigt."""
        antwort = self.client.get("/api/auth/me")
        self.assertEqual(antwort.status_code, 200, antwort.text)
        self.assertIs(antwort.json()["has_password"], True)


def TestClientOhneCookies(vorbild):
    """Ein zweiter Client auf derselben App, mit eigenem Cookie-Topf.

    ``TestClient`` haelt seine Cookies im Objekt. Ohne einen zweiten Client
    traegt jeder Aufruf die Sitzung des ersten mit, und ein Test "ohne
    Anmeldung" prueft dann nichts.
    """
    from fastapi.testclient import TestClient
    return TestClient(vorbild.app)


if __name__ == "__main__":
    unittest.main()
