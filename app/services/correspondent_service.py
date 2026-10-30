"""Correspondent-Service: Sender-Strings zu Correspondent-Objekten auflösen.

Idempotent: get_or_create normalisiert den Sender-Namen (lowercased,
whitespace collapsed, häufige Suffixe wie 'GmbH' bleiben drin) und vergleicht
darüber. Damit landen "Stadtwerke Velbert" und "stadtwerke  velbert" am
selben Correspondent-Eintrag.
"""
from __future__ import annotations

import re
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models import Correspondent, Letter

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_name(raw: str) -> str:
    s = raw.strip().lower()
    s = _WHITESPACE_RE.sub(" ", s)
    return s[:300]


def get_or_create(db: Session, user_id: int, name: str) -> Optional[Correspondent]:
    name = (name or "").strip()
    if not name:
        return None
    norm = normalize_name(name)
    if not norm:
        return None
    existing = db.execute(
        select(Correspondent).where(
            Correspondent.user_id == user_id,
            Correspondent.normalized == norm,
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    c = Correspondent(user_id=user_id, name=name[:300], normalized=norm)
    db.add(c)
    db.flush()  # ID verfügbar machen, ohne commit
    return c


def attach_to_letter(db: Session, letter: Letter, name: str | None) -> Optional[Correspondent]:
    """Setzt letter.correspondent_id basierend auf name. Caller commit-let."""
    if not name:
        return None
    c = get_or_create(db, letter.user_id, name)
    if c is None:
        return None
    letter.correspondent_id = c.id
    return c


def list_with_counts(db: Session, user_id: int) -> list[dict]:
    rows = db.execute(
        select(
            Correspondent.id,
            Correspondent.name,
            Correspondent.normalized,
            func.count(Letter.id).label("letter_count"),
        )
        .outerjoin(
            Letter,
            (Letter.correspondent_id == Correspondent.id) & (Letter.deleted_at.is_(None)),
        )
        .where(Correspondent.user_id == user_id)
        .group_by(Correspondent.id)
        .order_by(func.lower(Correspondent.name))
    ).all()
    return [
        {"id": r.id, "name": r.name, "normalized": r.normalized, "letter_count": r.letter_count}
        for r in rows
    ]


def merge(db: Session, user_id: int, source_id: int, target_id: int) -> int:
    """Merge source → target. Verschiebt alle Letters, löscht source.
    Returns Anzahl verschobener Letter."""
    if source_id == target_id:
        return 0
    src = db.get(Correspondent, source_id)
    tgt = db.get(Correspondent, target_id)
    if not src or src.user_id != user_id or not tgt or tgt.user_id != user_id:
        raise ValueError("correspondent not found or not owned by user")
    letters = db.execute(
        select(Letter).where(Letter.correspondent_id == source_id, Letter.user_id == user_id)
    ).scalars().all()
    for l in letters:
        l.correspondent_id = target_id
    db.delete(src)
    db.commit()
    return len(letters)
