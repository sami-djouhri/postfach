from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import (
    create_session,
    delete_session,
    get_current_user,
    hash_password,
    verify_password,
)
from app.db import get_db
from app.domain import DomainError
from app.models import User
from app.config import settings
from app.schemas import LoginRequest, RegisterRequest, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _safe_redirect(target: str) -> str:
    """PF1: Open-Redirect verhindern; nur lokale, relative Pfade zulassen.
    Externe/protokoll-relative Ziele werden auf '/' zurückgesetzt."""
    if not target.startswith("/") or target.startswith("//") or target.startswith("/\\"):
        return "/"
    return target


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

    return UserOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        created_at=user.created_at,
    )


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

    return UserOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        created_at=user.created_at,
    )


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
    return UserOut(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        created_at=user.created_at,
    )


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
