"""Echtheitspruefung des ``X-Saganta-Sub``-Headers.

Uebernommen aus ``kalender/backend/tenant_auth.py``, damit es im Haus **ein**
Verfahren gibt und nicht zwei, die sich langsam auseinanderentwickeln. Gleiche
Header, gleiche Signatur, gleiche drei Zustaende. Nur das Geheimnis ist ein
eigenes (``POSTFACH_TENANT_SECRET``): wer den Kalender lesen darf, soll damit
nicht automatisch die Post lesen duerfen.

**Das Problem, das hier adressiert wird:** Der Briefkasten kannte bisher nur zwei
Wege herein, und beide melden denselben Menschen an. Die Sitzungs-Anmeldung ueber
``session_id`` (eigene Nutzertabelle, eigenes Passwort) und der Auto-Login-Token
``SAGANTA_SESSION_TOKEN``, der **jeden** Aufrufer als ``SAGANTA_SESSION_USER``
anmeldet. Solange es genau einen Nutzer gibt, faellt das nicht auf. Mit dem
zweiten sehen beide dieselbe Post.

Der Absender schickt ``X-Saganta-Sub`` plus
``X-Saganta-Sub-Sig: hex(HMAC-SHA256(secret, sub))``. Die Signatur haengt an
genau diesem Sub, eine abgefangene laesst sich nicht auf einen fremden umhaengen,
und das Geheimnis wandert nie ueber die Leitung.

Drei Zustaende:

1. **Kein Geheimnis konfiguriert** (Auslieferungszustand): der Header wird
   akzeptiert, aber nur fuer einen Sub, den es hier schon gibt. Neue Postfaecher
   entstehen so nicht, siehe ``darf_anlegen``.
2. **Geheimnis gesetzt, ``TENANT_HEADER_ENFORCE=0``** (Beobachtung): Unsigniertes
   wird akzeptiert und protokolliert. So sieht man vor dem Scharfschalten, welcher
   Absender noch nachziehen muss.
3. **Geheimnis gesetzt, ``TENANT_HEADER_ENFORCE=1``**: Unsigniertes gibt 401.

**Unberuehrt in allen drei Zustaenden:** Aufrufe *ohne* ``X-Saganta-Sub``. Das
sind das native Frontend und der Auto-Login-Token, die weiter ueber die
Sitzungs-Anmeldung laufen. Sie fallen weg, wenn der Sub-Weg traegt.
"""

import hashlib
import hmac
import logging
from dataclasses import dataclass

from fastapi import HTTPException, status

from app.config import settings

logger = logging.getLogger(__name__)

SUB_HEADER = "x-saganta-sub"
SIG_HEADER = "x-saganta-sub-sig"


@dataclass(frozen=True)
class Mandant:
    """Ergebnis der Header-Pruefung.

    ``darf_anlegen`` ist die eigentliche Sicherheitsentscheidung: nur ein
    **nachgewiesener** Sub darf sich ein neues, leeres Postfach anlegen lassen.
    Ohne diese Trennung koennte in Zustand 1 und 2 jeder, der den Dienst
    erreicht, mit einem frei erfundenen Header beliebig viele Postfaecher
    erzeugen. Ein bestehendes fremdes Postfach oeffnet er damit nicht, aber
    Muell anlegen ist auch kein erlaubter Zustand.
    """

    sub: str
    nachgewiesen: bool

    @property
    def darf_anlegen(self) -> bool:
        return self.nachgewiesen


def erwartete_signatur(sub: str, secret: str) -> str:
    """Die Signatur, die ein Absender fuer diesen Sub mitschicken muss."""
    return hmac.new(secret.encode("utf-8"), sub.encode("utf-8"), hashlib.sha256).hexdigest()


def loese_mandant(request) -> Mandant | None:
    """Mandant fuer diesen Request, oder ``None`` fuer den headerlosen Altweg.

    Wirft 401 nur im Erzwingen-Modus.
    """
    if request is None:
        return None

    sub = request.headers.get(SUB_HEADER)
    if not sub:
        # Headerloser Pfad: natives Frontend und Auto-Login-Token. Unveraendert.
        return None

    secret = settings.POSTFACH_TENANT_SECRET
    if not secret:
        # Noch kein Geheimnis vergeben: wie bisher, ohne Rauschen. Der Sub gilt,
        # legt aber nichts Neues an.
        return Mandant(sub=sub, nachgewiesen=False)

    mitgeschickt = request.headers.get(SIG_HEADER, "")
    if mitgeschickt and hmac.compare_digest(mitgeschickt, erwartete_signatur(sub, secret)):
        return Mandant(sub=sub, nachgewiesen=True)

    grund = "ohne Signatur" if not mitgeschickt else "mit falscher Signatur"
    if settings.TENANT_HEADER_ENFORCE:
        logger.warning("Mandanten-Header %s abgelehnt (sub=%s...)", grund, sub[:8])
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "X-Saganta-Sub ohne gueltige Signatur",
        )
    logger.warning(
        "Mandanten-Header %s akzeptiert (Beobachtungsphase, sub=%s...). Absender nachziehen, "
        "bevor TENANT_HEADER_ENFORCE=1 gesetzt wird",
        grund,
        sub[:8],
    )
    return Mandant(sub=sub, nachgewiesen=False)
