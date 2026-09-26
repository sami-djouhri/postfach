import logging
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt as _bcrypt
from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Session as SessionModel
from app.models import User
from app.tenant_auth import Mandant, loese_mandant

logger = logging.getLogger(__name__)


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return _bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_session(db: Session, user_id: int) -> str:
    # Opportunistischer Sweep: get_current_user löscht nur die gerade angefragte
    # abgelaufene Session, sodass sich alte Sessions sonst unbegrenzt ansammeln
    # (waren ~5000). Login ist selten genug, um das hier mitzuerledigen.
    db.execute(delete(SessionModel).where(SessionModel.expires_at < datetime.now(timezone.utc)))
    session_id = uuid.uuid4().hex
    expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.SESSION_EXPIRE_HOURS)
    session = SessionModel(
        session_id=session_id,
        user_id=user_id,
        expires_at=expires_at,
    )
    db.add(session)
    db.commit()
    return session_id


def delete_session(db: Session, session_id: str) -> None:
    session = db.execute(
        select(SessionModel).where(SessionModel.session_id == session_id)
    ).scalar_one_or_none()
    if session:
        db.delete(session)
        db.commit()


def _postfach_zum_sub(db: Session, mandant: Mandant) -> User:
    """Das Postfach zu einem Saganta-Konto, notfalls neu angelegt.

    Anlegen darf nur ein nachgewiesener Sub (siehe ``Mandant.darf_anlegen``).
    Sonst koennte in der Beobachtungsphase jeder, der den Dienst erreicht, mit
    einem erfundenen Header beliebig viele leere Postfaecher erzeugen.
    """
    user = db.execute(select(User).where(User.sub == mandant.sub)).scalar_one_or_none()
    if user:
        return user

    if not mandant.darf_anlegen:
        # Kein Rueckfall auf den Owner. Genau dieser Rueckfall ist der Grund,
        # warum der Auto-Login-Token abgeloest wird: er hat jeden Fremden still
        # in fremde Post gesetzt, statt ihn abzuweisen.
        raise HTTPException(
            status_code=403,
            detail="Kein Postfach fuer dieses Konto, und der Mandant ist nicht nachgewiesen",
        )

    user = User(
        # Kein Passwort-Anmeldeweg fuer diese Zeilen: die Anmeldung liegt bei
        # Saganta. bcrypt kann diesen Platzhalter nie erzeugen, ein Login
        # dagegen scheitert also immer.
        username=f"saganta:{mandant.sub}",
        password_hash="!saganta",
        display_name="Saganta-Konto",
        sub=mandant.sub,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    logger.info("Neues Postfach fuer Saganta-Konto angelegt (sub=%s...)", mandant.sub[:8])
    return user


def get_current_user(
    request: Request,
    session_id: str | None = Cookie(None, alias="session_id"),
    db: Session = Depends(get_db),
) -> User:
    # Vorrang hat der Saganta-Mandant: wo ein geprueftes Konto mitkommt, soll
    # nicht eine nebenher offene Sitzung entscheiden, wessen Post man sieht.
    mandant = loese_mandant(request)
    if mandant is not None:
        return _postfach_zum_sub(db, mandant)

    if not session_id:
        raise HTTPException(status_code=401, detail="Nicht angemeldet")

    session = db.execute(
        select(SessionModel).where(SessionModel.session_id == session_id)
    ).scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=401, detail="Sitzung ungueltig")

    if session.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        db.delete(session)
        db.commit()
        raise HTTPException(status_code=401, detail="Sitzung abgelaufen")

    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Benutzer nicht gefunden")

    return user
