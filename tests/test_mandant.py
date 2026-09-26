"""Mandantentrennung ueber ``X-Saganta-Sub``.

Jeder Test prueft **beide** Richtungen: dass der richtige Weg traegt UND dass
der falsche abgewiesen wird. Eine Pruefung, die nur den Erfolgsfall kennt, ist
bei Zugriffsrechten wertlos: sie bleibt gruen, wenn die Sperre ganz fehlt.

Lauf: ``bash run-tests.sh`` (im Container, gegen das installierte Paket).
"""

import unittest
from types import SimpleNamespace

from app import tenant_auth
from app.config import settings
from app.tenant_auth import Mandant, erwartete_signatur, loese_mandant

GEHEIM = "prueflauf-geheimnis"
# Erfundene Kennung. Eine echte hat in einem Test nichts verloren, und
# schon gar nicht in einem Repo, das veroeffentlicht werden soll.
SUB = "KONTO-A-nur-fuer-den-test"
FREMD = "KONTO-B-nur-fuer-den-test"


def anfrage(**header):
    """Minimale Attrappe: loese_mandant liest ausschliesslich request.headers."""
    return SimpleNamespace(headers={k.lower().replace("_", "-"): v for k, v in header.items()})


class Zustand(unittest.TestCase):
    """Die drei Zustaende aus dem Modulkopf von tenant_auth."""

    def setUp(self):
        self._secret = settings.POSTFACH_TENANT_SECRET
        self._enforce = settings.TENANT_HEADER_ENFORCE
        self.addCleanup(self._zuruecksetzen)

    def _zuruecksetzen(self):
        settings.POSTFACH_TENANT_SECRET = self._secret
        settings.TENANT_HEADER_ENFORCE = self._enforce

    def test_ohne_header_bleibt_der_altweg(self):
        """Natives Frontend und Auto-Login duerfen sich nicht aendern."""
        self.assertIsNone(loese_mandant(anfrage()))
        self.assertIsNone(loese_mandant(None))

    def test_ohne_geheimnis_gilt_der_sub_aber_legt_nichts_an(self):
        settings.POSTFACH_TENANT_SECRET = ""
        m = loese_mandant(anfrage(**{"x-saganta-sub": SUB}))
        self.assertEqual(m.sub, SUB)
        self.assertFalse(m.nachgewiesen)
        self.assertFalse(m.darf_anlegen)

    def test_gueltige_signatur_ist_nachgewiesen(self):
        settings.POSTFACH_TENANT_SECRET = GEHEIM
        m = loese_mandant(
            anfrage(
                **{
                    "x-saganta-sub": SUB,
                    "x-saganta-sub-sig": erwartete_signatur(SUB, GEHEIM),
                }
            )
        )
        self.assertTrue(m.nachgewiesen)
        self.assertTrue(m.darf_anlegen)

    def test_beobachtung_laesst_unsigniertes_durch_ohne_nachweis(self):
        settings.POSTFACH_TENANT_SECRET = GEHEIM
        settings.TENANT_HEADER_ENFORCE = 0
        with self.assertLogs(tenant_auth.logger, level="WARNING"):
            m = loese_mandant(anfrage(**{"x-saganta-sub": SUB}))
        self.assertEqual(m.sub, SUB)
        self.assertFalse(m.darf_anlegen)

    def test_erzwingen_lehnt_unsigniertes_ab(self):
        settings.POSTFACH_TENANT_SECRET = GEHEIM
        settings.TENANT_HEADER_ENFORCE = 1
        from fastapi import HTTPException

        with self.assertLogs(tenant_auth.logger, level="WARNING"):
            with self.assertRaises(HTTPException) as f:
                loese_mandant(anfrage(**{"x-saganta-sub": SUB}))
        self.assertEqual(f.exception.status_code, 401)


class SignaturHaengtAmSub(unittest.TestCase):
    """Der Punkt des Verfahrens: eine Signatur ist nicht umhaengbar."""

    def setUp(self):
        self._secret = settings.POSTFACH_TENANT_SECRET
        self._enforce = settings.TENANT_HEADER_ENFORCE
        settings.POSTFACH_TENANT_SECRET = GEHEIM
        settings.TENANT_HEADER_ENFORCE = 1

        def zurueck():
            settings.POSTFACH_TENANT_SECRET = self._secret
            settings.TENANT_HEADER_ENFORCE = self._enforce

        self.addCleanup(zurueck)

    def test_abgefangene_signatur_oeffnet_keinen_fremden_sub(self):
        """Signatur fuer SUB, Header sagt FREMD. Muss scheitern."""
        from fastapi import HTTPException

        with self.assertLogs(tenant_auth.logger, level="WARNING"):
            with self.assertRaises(HTTPException):
                loese_mandant(
                    anfrage(
                        **{
                            "x-saganta-sub": FREMD,
                            "x-saganta-sub-sig": erwartete_signatur(SUB, GEHEIM),
                        }
                    )
                )

    def test_falsches_geheimnis_traegt_nicht(self):
        from fastapi import HTTPException

        with self.assertLogs(tenant_auth.logger, level="WARNING"):
            with self.assertRaises(HTTPException):
                loese_mandant(
                    anfrage(
                        **{
                            "x-saganta-sub": SUB,
                            "x-saganta-sub-sig": erwartete_signatur(SUB, "anderes-geheimnis"),
                        }
                    )
                )

    def test_signatur_ist_je_sub_verschieden(self):
        self.assertNotEqual(
            erwartete_signatur(SUB, GEHEIM), erwartete_signatur(FREMD, GEHEIM)
        )


class AnlegeRecht(unittest.TestCase):
    """darf_anlegen ist die eigentliche Sicherheitsentscheidung."""

    def test_nur_nachgewiesene_duerfen_anlegen(self):
        self.assertTrue(Mandant(sub=SUB, nachgewiesen=True).darf_anlegen)
        self.assertFalse(Mandant(sub=SUB, nachgewiesen=False).darf_anlegen)


if __name__ == "__main__":
    unittest.main()
