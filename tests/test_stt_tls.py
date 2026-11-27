"""STT ueber eine eigene CA: STT_CA_FILE ergaenzt den Systemspeicher.

Beide Richtungen: ohne Datei bleibt es bei der Vorgabe (True), mit Datei
kommt ein Kontext zurueck, der die zusaetzliche Wurzel kennt, und eine
fehlende Datei faellt laut auf statt still auf den Systemspeicher zurueck.

Lauf: ``bash run-tests.sh``
"""

import os
import ssl
import tempfile
import unittest

# Selbst signierte Testwurzel (CN "Testwurzel Briefkasten"), nur das
# Zertifikat, der Schluessel wurde nach dem Erzeugen verworfen.
_WURZEL_PEM = """-----BEGIN CERTIFICATE-----
MIIBmjCCAT+gAwIBAgIUJeHpwRQJpd2CmZcwlrlxJnynqqswCgYIKoZIzj0EAwIw
ITEfMB0GA1UEAwwWVGVzdHd1cnplbCBCcmllZmthc3RlbjAgFw0yNjExMjEyMzM0
MjhaGA8yMTI2MTAyODIzMzQyOFowITEfMB0GA1UEAwwWVGVzdHd1cnplbCBCcmll
Zmthc3RlbjBZMBMGByqGSM49AgEGCCqGSM49AwEHA0IABDC386RUESOxwDOnMQis
pZVdjTWh6J1KCKuJqB5B7TWXI88V/tyaJweMoz5dOXKaXO9W3YT6QggieJ3kDdhb
iAujUzBRMB0GA1UdDgQWBBTRGAgJPf2Jkq/ilfMxjHlQbpoKUjAfBgNVHSMEGDAW
gBTRGAgJPf2Jkq/ilfMxjHlQbpoKUjAPBgNVHRMBAf8EBTADAQH/MAoGCCqGSM49
BAMCA0kAMEYCIQC6+l6vrXdvjEm8+A0cJwRfMLYpO/Xf57H9zuHGYAfOMgIhAPvX
GZM14jAp+p8xzZ8izWMqTAnKBblpo+IKyyVC7KQu
-----END CERTIFICATE-----
"""


class SttVerifyTest(unittest.TestCase):
    def setUp(self):
        from app.config import settings
        self.settings = settings
        self.alt = settings.STT_CA_FILE

    def tearDown(self):
        self.settings.STT_CA_FILE = self.alt

    def test_ohne_datei_systemspeicher(self):
        from app.api.routes_letters import _stt_verify
        self.settings.STT_CA_FILE = ""
        self.assertIs(_stt_verify(), True)

    def test_mit_datei_kennt_der_kontext_die_wurzel(self):
        from app.api.routes_letters import _stt_verify
        with tempfile.TemporaryDirectory() as d:
            pfad = os.path.join(d, "wurzel.crt")
            with open(pfad, "w") as f:
                f.write(_WURZEL_PEM)
            self.settings.STT_CA_FILE = pfad
            ctx = _stt_verify()
        self.assertIsInstance(ctx, ssl.SSLContext)
        namen = [dict(x[0] for x in c["subject"]).get("commonName")
                 for c in ctx.get_ca_certs()]
        self.assertIn("Testwurzel Briefkasten", namen)
        self.assertEqual(ctx.verify_mode, ssl.CERT_REQUIRED)

    def test_fehlende_datei_faellt_auf(self):
        from app.api.routes_letters import _stt_verify
        self.settings.STT_CA_FILE = "/gibt/es/nicht.crt"
        with self.assertRaises(OSError):
            _stt_verify()


if __name__ == "__main__":
    unittest.main()
