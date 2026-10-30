from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import (
    create_session,
    delete_session,
    get_current_user,
    hash_password,
    hat_passwort_anmeldung,
    verify_password,
)
from app.db import get_db
from app.domain import DomainError
from app.models import Session as SessionModel
from app.models import User
from app.config import settings
from app.schemas import ChangePasswordRequest, LoginRequest, RegisterRequest, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _safe_redirect(target: str) -> str:
    """PF1: Open-Redirect verhindern; nur lokale, relative Pfade zulassen.
    Externe/protokoll-relative Ziele werden auf '/' zurückgesetzt."""
    if not target.startswith("/") or target.startswith("//") or target.startswith("/\\"):
        return "/"
    return target


def _benutzer_aus(user: User) -> UserOut:
    """Die eine Stelle, die ein Konto nach aussen beschreibt.

    Vorher stand dieser Konstruktor dreimal woertlich gleich in dieser Datei.
    Mit ``has_password`` kam ein viertes Feld dazu, und ein in einer der Kopien
    vergessenes Feld faellt nicht auf: die Antwort bleibt gueltig, nur das
    Vorzeichen ist falsch. Bei einem Feld, an dem die Oberflaeche entscheidet,
    ob sie ein Formular zeigt, heisst das ein Formular, das nur 409 kann.
    """
    return UserOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        created_at=user.created_at,
        has_password=hat_passwort_anmeldung(user),
    )


@router.post("/register", response_model=UserOut, status_code=201)
def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    existing = db.execute(
        select(User).where(User.username == body.username)
    ).scalar_one_or_none()
    if existing:
        raise DomainError("Benutzername bereits vergeben")

    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    session_id = create_session(db, user.id)
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=72 * 3600,
        path="/",
    )

    return _benutzer_aus(user)


@router.post("/login", response_model=UserOut)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.execute(
        select(User).where(User.username == body.username)
    ).scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise DomainError("Benutzername oder Passwort falsch")

    session_id = create_session(db, user.id)
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=72 * 3600,
        path="/",
    )

    return _benutzer_aus(user)


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    session_id: str | None = Cookie(None, alias="session_id"),
):
    # PF2: Session server-seitig invalidieren, nicht nur Cookie löschen:
    # sonst bleibt ein kopiertes/gestohlenes Cookie nach Logout gültig.
    if session_id:
        delete_session(db, session_id)
    response.delete_cookie(key="session_id", path="/")
    return None


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return _benutzer_aus(user)


@router.post("/change-password", status_code=204)
def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    session_id: str | None = Cookie(None, alias="session_id"),
):
    """Das eigene Passwort aendern, bestaetigt durch das alte.

    Es gibt bewusst **keinen** "Passwort vergessen"-Weg (Entscheid
    2026-10-03). Der haette einen Mail-Versand und eine Token-Tabelle gebraucht,
    also zwei neue Flaechen fuer einen Dienst mit sehr wenigen Konten.

    Die Reihenfolge der Pruefungen ist nicht beliebig. Zuerst wird gefragt,
    ob dieses Konto ueberhaupt ein Passwort hat: ein ueber Saganta angemeldeter
    Mandant kommt durch ``get_current_user`` herein, **ohne** ein Passwort
    besessen zu haben. Wuerde man ihn direkt gegen ``verify_password`` laufen
    lassen, bekaeme er "Passwort falsch" und wuerde sein Saganta-Passwort
    ausprobieren, bis er aufgibt. Die Meldung muss ihn an die richtige Stelle
    schicken.

    Das neue Passwort darf nicht das alte sein. Sonst meldet der Dienst
    "geaendert", ohne dass sich etwas geaendert hat, und das ist genau die
    Zusage, die man nach einem verlorenen Passwort braucht.
    """
    if not hat_passwort_anmeldung(user):
        raise HTTPException(
            status_code=409,
            detail="Dieses Konto meldet sich ueber Saganta an. Das Passwort wird dort geaendert.",
        )

    if not verify_password(body.current_password, user.password_hash):
        # 401 und nicht 400: es ist eine fehlgeschlagene Authentifizierung,
        # keine ungueltige Eingabe. Die Meldung nennt nicht, welcher der beiden
        # Werte nicht passte.
        raise HTTPException(status_code=401, detail="Aktuelles Passwort falsch")

    if verify_password(body.new_password, user.password_hash):
        raise DomainError("Das neue Passwort ist das alte")

    user.password_hash = hash_password(body.new_password)

    # Alle anderen Sitzungen beenden, die eigene behalten. Ein Passwortwechsel
    # ist der Griff, mit dem man einen fremden Zugriff beendet; bleiben die alten
    # Sitzungen gueltig (72 h), hat er genau das nicht getan. Die eigene bleibt,
    # weil ein Wechsel, der einen aus der App wirft, wie ein Fehler aussieht.
    stmt = delete(SessionModel).where(SessionModel.user_id == user.id)
    if session_id:
        stmt = stmt.where(SessionModel.session_id != session_id)
    db.execute(stmt)
    db.commit()
    return None


@router.get("/token-login")
def token_login(
    token: str = Query(...),
    redirect: str = Query("/"),
    db: Session = Depends(get_db),
):
    """Auto-Login via Service-Token (für saganta-edge Bridge).

    nginx rewrited den ersten Request auf calendar/mail.home.arpa auf diesen
    Endpoint mit dem SAGANTA_SESSION_TOKEN. Wir validieren den Token und legen
    eine Session für den konfigurierten Service-User (SAGANTA_SESSION_USER) an.
    """
    if not settings.SAGANTA_SESSION_TOKEN:
        raise HTTPException(status_code=403, detail="saganta auto-login disabled")
    if token != settings.SAGANTA_SESSION_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")
    user = db.execute(
        select(User).where(User.username == settings.SAGANTA_SESSION_USER)
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail=f"service user not found: {settings.SAGANTA_SESSION_USER}")
    session_id = create_session(db, user.id)
    resp = RedirectResponse(url=_safe_redirect(redirect), status_code=302)
    resp.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        samesite="lax",
        max_age=settings.SESSION_EXPIRE_HOURS * 3600,
        path="/",
    )
    return resp
