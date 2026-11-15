"""Fristvorschlag aus Text, offene Fristen, erledigt, Filter.

Alle Briefe hier sind erfunden. Gelaufen wird gegen die ausgelieferte App mit
einer Wegwerf-Datenbank, deren Schema aus den Migrationen kommt (FTS5 samt
Triggern), nicht aus ``create_all``.

Lauf: ``bash run-tests.sh``
"""
import unittest
from datetime import date, datetime, timedelta

from sqlalchemy.orm import sessionmaker

from _wegwerf_db import engine_fuer, migriere, neue_datei


async def _als_async(wert):
    return wert


# --- Fristvorschlag aus Text ------------------------------------------------

class FristAusText(unittest.TestCase):
    def setUp(self):
        from app.services.frist_service import frist_aus_text
        self.f = frist_aus_text

    def test_datum_mit_fristwort(self):
        v = self.f("Bitte zahlbar bis zum 15.12.2026 auf das Konto.", date(2026, 11, 1))
        self.assertEqual(v.datum, date(2026, 12, 15))
        self.assertIn("15.12.2026", v.stelle)

    def test_datum_ohne_fristwort_ist_keine_frist(self):
        """Briefkopf und Rechnungsdatum duerfen nicht als Frist erscheinen."""
        text = "Musterstadt, 01.11.2026\nRechnung Nr. 4711 vom 01.11.2026\nBetrag 12,00 EUR"
        self.assertIsNone(self.f(text, date(2026, 11, 1)))

    def test_ausgeschriebener_monat(self):
        v = self.f("Ihre Antwort erwarten wir spaetestens am 3. Januar 2027.", date(2026, 11, 20))
        self.assertEqual(v.datum, date(2027, 1, 3))
        v = self.f("Fällig am 7. März 2027", date(2027, 2, 1))
        self.assertEqual(v.datum, date(2027, 3, 7))

    def test_relative_frist_ab_briefdatum(self):
        v = self.f("Bitte begleichen Sie den Betrag innerhalb von 14 Tagen.", date(2026, 11, 1))
        self.assertEqual(v.datum, date(2026, 11, 15))
        v = self.f("Widerspruch ist binnen eines Monats moeglich, binnen zwei Wochen zahlen.",
                   date(2026, 1, 31))
        self.assertEqual(v.datum, date(2026, 2, 14))

    def test_relative_frist_braucht_bezug(self):
        self.assertIsNone(self.f("innerhalb von 14 Tagen", None))

    def test_monatsende_wird_nicht_ueberlaufen(self):
        v = self.f("innerhalb von einem Monat", date(2026, 1, 31))
        self.assertEqual(v.datum, date(2026, 2, 28))

    def test_zeitraum_ist_keine_frist(self):
        text = "Leistungszeitraum vom 01.10.2026 bis 31.10.2026. Zahlbar bis 20.11.2026."
        v = self.f(text, date(2026, 11, 2))
        self.assertEqual(v.datum, date(2026, 11, 20))

    def test_frueheste_gueltige_frist_gewinnt_und_vergangenes_zaehlt_nicht(self):
        text = ("Ihre Frist bis 01.09.2026 ist abgelaufen. Neue Frist bis 30.11.2026, "
                "sonst spaetestens bis 15.12.2026.")
        v = self.f(text, date(2026, 11, 3))
        self.assertEqual(v.datum, date(2026, 11, 30))

    def test_unmoegliches_datum_und_zweistelliges_jahr(self):
        self.assertIsNone(self.f("zahlbar bis 31.02.2027", date(2026, 11, 1)))
        v = self.f("zahlbar bis 05.01.27", date(2026, 11, 1))
        self.assertEqual(v.datum, date(2027, 1, 5))

    def test_leerer_text(self):
        self.assertIsNone(self.f("", date(2026, 1, 1)))
        self.assertIsNone(self.f(None, date(2026, 1, 1)))


# --- Datenbank und App -------------------------------------------------------

HEUTE = date(2026, 11, 13)


class MitDatenbank(unittest.TestCase):
    """Zwei Mandanten, erfundene Briefe, echtes Schema."""

    def setUp(self):
        from app.models import Correspondent, Letter, Tag, User

        self.pfad = neue_datei()
        migriere(self.pfad)
        self.engine = engine_fuer(self.pfad)
        self.addCleanup(self.engine.dispose)
        self.Sitzung = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)
        db = self.Sitzung()
        self.addCleanup(db.close)
        self.db = db

        a = User(username="konto-a", password_hash="!saganta", display_name="A")
        b = User(username="konto-b", password_hash="!saganta", display_name="B")
        db.add_all([a, b]); db.flush()
        self.a, self.b = a.id, b.id
        stadtwerk = Correspondent(user_id=a.id, name="Stadtwerk Muster", normalized="stadtwerk muster")
        kasse = Correspondent(user_id=a.id, name="Kasse Beispiel", normalized="kasse beispiel")
        fremd = Correspondent(user_id=b.id, name="Fremd AG", normalized="fremd ag")
        db.add_all([stadtwerk, kasse, fremd]); db.flush()
        self.stadtwerk, self.kasse = stadtwerk.id, kasse.id
        wichtig = Tag(user_id=a.id, name="wichtig", color="#aa5500")
        steuer = Tag(user_id=a.id, name="steuer", color="#225588")
        db.add_all([wichtig, steuer]); db.flush()
        self.wichtig, self.steuer = wichtig.id, steuer.id

        def brief(**kw):
            l = Letter(ocr_status="done", analysis_status="done", is_archived=False, **kw)
            db.add(l); db.flush()
            return l

        self.ueberfaellig = brief(user_id=a.id, title="Mahnung Strom", category="Rechnung",
                                  correspondent_id=stadtwerk.id, letter_date="2026-10-20",
                                  frist_bis=HEUTE - timedelta(days=3),
                                  ocr_text="Abschlag Strom offen, Mahnstufe eins")
        self.bald = brief(user_id=a.id, title="Beitrag Kasse", category="Versicherung",
                          correspondent_id=kasse.id, letter_date="2026-11-02",
                          frist_bis=HEUTE + timedelta(days=5),
                          ocr_text="Beitragsbescheid fuer das Jahr")
        self.erledigt = brief(user_id=a.id, title="Alte Rechnung", category="Rechnung",
                              correspondent_id=stadtwerk.id, letter_date="2025-03-01",
                              frist_bis=HEUTE - timedelta(days=200),
                              erledigt_am=datetime(2025, 3, 10, 9, 0),
                              ocr_text="Jahresabrechnung Strom und Gas")
        self.geloescht = brief(user_id=a.id, title="Weg", frist_bis=HEUTE,
                               deleted_at=datetime(2026, 11, 1), received_date="2026-10-01")
        self.ohne_datum = brief(user_id=a.id, title="Ohne Datum", category="Sonstiges",
                                received_date="2024-06-01", ocr_text="Notiz ohne Frist")
        self.vorschlag = brief(user_id=a.id, title="Neue Rechnung", category="Rechnung",
                               letter_date="2026-11-10", created_at=datetime(2026, 11, 10, 8, 0),
                               ocr_text="Bitte ueberweisen. Zahlbar bis 01.12.2026.")
        self.fremder = brief(user_id=b.id, title="Fremder Brief", category="Rechnung",
                             correspondent_id=fremd.id, letter_date="2026-11-01",
                             frist_bis=HEUTE - timedelta(days=1),
                             created_at=datetime(2026, 11, 10, 8, 0),
                             ocr_text="Zahlbar bis 20.11.2026, Strom")
        self.ueberfaellig.tags = [wichtig]
        self.bald.tags = [wichtig, steuer]
        self.erledigt.tags = [steuer]
        db.commit()


class OffeneFristen(MitDatenbank):
    def test_sortiert_und_ueberfaellig_markiert(self):
        from app.services.frist_service import offene_fristen
        e = offene_fristen(self.db, self.a, HEUTE)
        self.assertEqual([x["letter"].id for x in e], [self.ueberfaellig.id, self.bald.id])
        self.assertTrue(e[0]["ueberfaellig"])
        self.assertEqual(e[0]["tage"], -3)
        self.assertFalse(e[1]["ueberfaellig"])
        self.assertEqual(e[1]["tage"], 5)

    def test_erledigt_geloescht_und_fremd_fehlen(self):
        from app.services.frist_service import offene_fristen
        ids = {x["letter"].id for x in offene_fristen(self.db, self.a, HEUTE)}
        self.assertNotIn(self.erledigt.id, ids)
        self.assertNotIn(self.geloescht.id, ids)
        self.assertNotIn(self.fremder.id, ids)

    def test_heute_ist_noch_nicht_ueberfaellig(self):
        from app.services.frist_service import offene_fristen
        self.bald.frist_bis = HEUTE
        self.db.commit()
        e = {x["letter"].id: x for x in offene_fristen(self.db, self.a, HEUTE)}
        self.assertFalse(e[self.bald.id]["ueberfaellig"])
        self.assertEqual(e[self.bald.id]["tage"], 0)

    def test_vorschlaege_nur_ohne_frist_und_offen(self):
        from app.services.frist_service import erledigen, offene_vorschlaege
        v = offene_vorschlaege(self.db, self.a, HEUTE)
        self.assertEqual([x["letter"].id for x in v], [self.vorschlag.id])
        self.assertEqual(v[0]["vorschlag"].datum, date(2026, 12, 1))
        # Der Vorschlag setzt nichts.
        self.db.refresh(self.vorschlag)
        self.assertIsNone(self.vorschlag.frist_bis)
        # "Nichts zu tun" heisst erledigt, dann verschwindet er.
        erledigen(self.vorschlag)
        self.db.commit()
        self.assertEqual(offene_vorschlaege(self.db, self.a, HEUTE), [])

    def test_erledigen_ist_idempotent_und_umkehrbar(self):
        from app.services.frist_service import erledigen, wieder_oeffnen
        erledigen(self.bald, datetime(2026, 11, 13, 10, 0))
        erledigen(self.bald, datetime(2026, 11, 14, 10, 0))
        self.assertEqual(self.bald.erledigt_am, datetime(2026, 11, 13, 10, 0))
        wieder_oeffnen(self.bald)
        self.assertIsNone(self.bald.erledigt_am)


class Filter(MitDatenbank):
    def liste(self, **kw):
        from app.services.letter_service import LetterService
        return {i["letter"].id for i in LetterService(self.db).list_all(user_id=self.a, **kw)}

    def test_ohne_filter_alle_eigenen_aktiven(self):
        ids = self.liste()
        self.assertEqual(ids, {self.ueberfaellig.id, self.bald.id, self.erledigt.id,
                               self.ohne_datum.id, self.vorschlag.id})

    def test_absender(self):
        self.assertEqual(self.liste(correspondent_id=self.stadtwerk),
                         {self.ueberfaellig.id, self.erledigt.id})

    def test_kategorie_und_jahr_kombiniert(self):
        self.assertEqual(self.liste(category="Rechnung", jahr=2026),
                         {self.ueberfaellig.id, self.vorschlag.id})
        self.assertEqual(self.liste(category="Rechnung", jahr=2025), {self.erledigt.id})

    def test_jahr_faellt_auf_eingang_zurueck(self):
        self.assertEqual(self.liste(jahr=2024), {self.ohne_datum.id})

    def test_tags_alle_muessen_passen(self):
        self.assertEqual(self.liste(tag_ids_all=[self.wichtig]),
                         {self.ueberfaellig.id, self.bald.id})
        self.assertEqual(self.liste(tag_ids_all=[self.wichtig, self.steuer]), {self.bald.id})

    def test_volltext_mit_filter(self):
        self.assertEqual(self.liste(q="Strom"), {self.ueberfaellig.id, self.erledigt.id})
        self.assertEqual(self.liste(q="Strom", status="offen"), {self.ueberfaellig.id})
        self.assertEqual(self.liste(q="Strom", jahr=2025), {self.erledigt.id})
        # Der fremde Brief enthaelt auch "Strom" und darf nie auftauchen.
        self.assertNotIn(self.fremder.id, self.liste(q="Strom"))

    def test_volltext_praefix_und_rueckfall(self):
        self.assertEqual(self.liste(q="Beitrag"), {self.bald.id})
        # Nur Sonderzeichen: FTS unbrauchbar, der LIKE-Rueckfall darf nicht werfen
        # und bleibt beim eigenen Mandanten.
        self.assertNotIn(self.fremder.id, self.liste(q="%%"))
        self.assertEqual(self.liste(q='"'), set())

    def test_status(self):
        self.assertEqual(self.liste(status="erledigt"), {self.erledigt.id})
        self.assertNotIn(self.erledigt.id, self.liste(status="offen"))

    def test_facetten_zaehlen_nur_eigene_aktive(self):
        from app.services.letter_service import LetterService
        f = LetterService(self.db).facetten(self.a)
        kat = {x["wert"]: x["anzahl"] for x in f["kategorien"]}
        self.assertEqual(kat, {"Rechnung": 3, "Versicherung": 1, "Sonstiges": 1})
        absender = {x["name"]: x["anzahl"] for x in f["absender"]}
        self.assertEqual(absender, {"Stadtwerk Muster": 2, "Kasse Beispiel": 1})
        tags = {x["name"]: x["anzahl"] for x in f["tags"]}
        self.assertEqual(tags, {"wichtig": 2, "steuer": 2})
        jahre = {x["wert"]: x["anzahl"] for x in f["jahre"]}
        self.assertEqual(jahre, {"2026": 3, "2025": 1, "2024": 1})


class Endpunkte(MitDatenbank):
    """Gegen app.main:app, angemeldet als Mandant A ueber eine Sitzung."""

    def setUp(self):
        super().setUp()
        from fastapi.testclient import TestClient
        from app import main as main_modul
        from app.api import routes_letters
        from app.auth import get_current_user
        from app.db import get_db
        from app.models import User

        def _db():
            s = self.Sitzung()
            try:
                yield s
            finally:
                s.close()

        nutzer_a = self.db.get(User, self.a)
        main_modul.app.dependency_overrides[get_db] = _db
        main_modul.app.dependency_overrides[get_current_user] = lambda: nutzer_a
        self.addCleanup(main_modul.app.dependency_overrides.clear)
        main_modul._rate_store.clear()
        alt = routes_letters._heute
        routes_letters._heute = lambda: HEUTE
        self.addCleanup(setattr, routes_letters, "_heute", alt)
        self.client = TestClient(main_modul.app)
        self.addCleanup(self.client.close)

    def test_fristen_uebersicht(self):
        r = self.client.get("/api/letters/fristen")
        self.assertEqual(r.status_code, 200, r.text)
        d = r.json()
        self.assertEqual([x["id"] for x in d["offen"]], [self.ueberfaellig.id, self.bald.id])
        self.assertTrue(d["offen"][0]["ueberfaellig"])
        self.assertEqual([x["id"] for x in d["vorschlaege"]], [self.vorschlag.id])
        self.assertEqual(d["vorschlaege"][0]["vorschlag"]["datum"], "2026-12-01")

    def test_vorschlag_bestaetigen_setzt_erst_dann_die_frist(self):
        r = self.client.get(f"/api/letters/{self.vorschlag.id}/frist-vorschlag")
        self.assertEqual(r.json()["datum"], "2026-12-01")
        self.assertIsNone(self.client.get(f"/api/letters/{self.vorschlag.id}").json()["frist_bis"])
        r = self.client.put(f"/api/letters/{self.vorschlag.id}", json={"frist_bis": "2026-12-01"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["frist_bis"], "2026-12-01")
        # Ein PUT ohne das Feld laesst die Frist stehen ...
        r = self.client.put(f"/api/letters/{self.vorschlag.id}", json={"notes": "geprueft"})
        self.assertEqual(r.json()["frist_bis"], "2026-12-01")
        # ... ein explizites null entfernt sie.
        r = self.client.put(f"/api/letters/{self.vorschlag.id}", json={"frist_bis": None})
        self.assertIsNone(r.json()["frist_bis"])

    def test_erledigt_und_zuruecknehmen(self):
        r = self.client.post(f"/api/letters/{self.bald.id}/erledigt")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIsNotNone(r.json()["erledigt_am"])
        offen = [x["id"] for x in self.client.get("/api/letters/fristen").json()["offen"]]
        self.assertNotIn(self.bald.id, offen)
        r = self.client.delete(f"/api/letters/{self.bald.id}/erledigt")
        self.assertIsNone(r.json()["erledigt_am"])

    def test_fremder_brief_bleibt_zu(self):
        """Der wichtigste Negativfall: Mandant A darf B nicht abhaken."""
        r = self.client.post(f"/api/letters/{self.fremder.id}/erledigt")
        self.assertEqual(r.status_code, 422, r.text)
        s = self.Sitzung()
        try:
            from app.models import Letter
            self.assertIsNone(s.get(Letter, self.fremder.id).erledigt_am)
        finally:
            s.close()

    def test_filter_ueber_die_liste(self):
        r = self.client.get("/api/letters", params={
            "q": "Strom", "correspondent_id": self.stadtwerk, "jahr": 2026, "status": "offen"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual([x["id"] for x in r.json()], [self.ueberfaellig.id])
        self.assertEqual(self.client.get("/api/letters", params={"status": "quatsch"}).status_code, 422)

    def test_facetten_endpunkt(self):
        r = self.client.get("/api/letters/facetten")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual({x["name"] for x in r.json()["absender"]},
                         {"Stadtwerk Muster", "Kasse Beispiel"})

    def _llm_mit_frist(self):
        """Sprachmodell-Attrappe mit Frist, dazu ein Netz, das jeden Aufruf mitschreibt."""
        from unittest import mock
        import httpx
        from app.schemas import FristItem, LlmAnalysisResult
        from app.services.llm_service import LlmService

        async def analyse(_self, _text):
            return LlmAnalysisResult(
                absender="Netz Muster AG", kategorie="Rechnung", zusammenfassung="Erfunden.",
                fristen=[FristItem(typ="zahlung", datum="2026-12-01", beschreibung="zahlen")])

        aufrufe = []

        def mitschreiben(self_, request):
            aufrufe.append(str(request.url))
            return httpx.Response(200, json={})

        for ziel in (mock.patch.object(LlmService, "analyze", analyse),
                     mock.patch.object(httpx.AsyncHTTPTransport, "handle_async_request",
                                       lambda s_, r: _als_async(mitschreiben(s_, r))),
                     mock.patch.object(httpx.HTTPTransport, "handle_request", mitschreiben)):
            ziel.start()
            self.addCleanup(ziel.stop)
        return aufrufe

    def _nur_erlaubte_ziele(self, aufrufe):
        # Erlaubt ist nur der Einbettungsdienst (semantischer Index nach der
        # Analyse). Ohne Konfiguration haette der alte Kalenderweg still
        # "uebersprungen"; deshalb pruefen die Tests zusaetzlich, dass es ihn
        # im Code nicht mehr gibt.
        import importlib.util
        from urllib.parse import urlparse
        self.assertIsNone(importlib.util.find_spec("app.services.kalender_adapter"))
        ziele = {urlparse(a).hostname for a in aufrufe}
        self.assertLessEqual(ziele, {"embedding-service"}, aufrufe)

    def test_analyse_ruft_keinen_kalender_und_setzt_keine_frist(self):
        """Entscheid 2026-11-13: Fristen nur im Briefkasten, erst nach Bestaetigung."""
        import app.api.routes_letters as rl
        aufrufe = self._llm_mit_frist()
        self.assertFalse(hasattr(rl, "KalenderAdapter"))
        r = self.client.post(f"/api/letters/{self.vorschlag.id}/analyze")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual([f["datum"] for f in r.json()["fristen"]], ["2026-12-01"])
        self.assertNotIn("calendar_synced", r.json())
        self._nur_erlaubte_ziele(aufrufe)
        self.assertIsNone(self.client.get(f"/api/letters/{self.vorschlag.id}").json()["frist_bis"])

    def test_scan_hintergrund_ruft_keinen_kalender(self):
        from unittest import mock
        import app.api.routes_letters as rl
        aufrufe = self._llm_mit_frist()
        with mock.patch.object(rl, "SessionLocal", self.Sitzung):
            rl._quick_scan_background(self.vorschlag.id, self.a)
        self._nur_erlaubte_ziele(aufrufe)
        s = self.Sitzung()
        try:
            from app.models import Letter
            brief = s.get(Letter, self.vorschlag.id)
            self.assertEqual(brief.llm_summary, "Erfunden.")  # die Analyse lief wirklich
            self.assertIsNone(brief.frist_bis)
        finally:
            s.close()

    def test_feste_pfade_vor_letter_id(self):
        """Vorher endete /semantic-search als 422, weil /{letter_id} zuerst passte."""
        r = self.client.get("/api/letters/semantic-search", params={"q": "strom"})
        self.assertEqual(r.status_code, 200, r.text)


if __name__ == "__main__":
    unittest.main()
