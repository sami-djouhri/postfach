"""Search-Service mit FTS5-Backed Volltext-Suche.

FTS5 macht echte Token-Suche statt LIKE-Patterns: schnell auch bei >10k Briefen,
versteht "Stromrechnung Velbert" als zwei Token (AND-verknüpft), unterstützt
Phrasen mit "..." und Prefix-Matching mit `wort*`.

Fallback auf LIKE wenn FTS5-Query syntaktisch ungültig (z.B. einzelnes Sonderzeichen).
Soft-deleted Letters werden gefiltert.
"""
from __future__ import annotations

import logging
import re

from sqlalchemy import or_, select, text
from sqlalchemy.orm import Session, joinedload

from app.models import Letter

logger = logging.getLogger(__name__)

# FTS5-Operators die wir aus Userinput rausnehmen, damit eingehende Quotes/Stars
# nicht versehentlich Syntax produzieren. Nutzer-Phrasen via " " bleiben erhalten.
_BAD_CHARS_RE = re.compile(r"[^\w\s\"*-]", flags=re.UNICODE)


def _sanitize_fts(q: str) -> str:
    q = _BAD_CHARS_RE.sub(" ", q).strip()
    # Einzeltoken: Prefix-Match → bessere UX bei "Strom" → findet "Stromrechnung"
    tokens = q.split()
    if not tokens:
        return ""
    if len(tokens) == 1 and not tokens[0].endswith("*") and '"' not in tokens[0]:
        return tokens[0] + "*"
    return " ".join(tokens)


class SearchService:
    def __init__(self, db: Session):
        self.db = db

    def search(self, user_id: int, query: str, skip: int = 0, limit: int = 50) -> list[Letter]:
        sanitized = _sanitize_fts(query)
        if sanitized:
            try:
                rowids = [
                    r[0] for r in self.db.execute(
                        text("SELECT rowid FROM letter_fts WHERE letter_fts MATCH :q ORDER BY rank LIMIT :lim OFFSET :off"),
                        {"q": sanitized, "lim": limit, "off": skip},
                    ).all()
                ]
                if rowids:
                    stmt = (
                        select(Letter)
                        .where(
                            Letter.id.in_(rowids),
                            Letter.user_id == user_id,
                            Letter.deleted_at.is_(None),
                        )
                        .options(joinedload(Letter.tags), joinedload(Letter.files))
                    )
                    results = self.db.execute(stmt).unique().scalars().all()
                    # Order der FTS-Rank-Sortierung beibehalten
                    order = {rid: i for i, rid in enumerate(rowids)}
                    return sorted(results, key=lambda l: order.get(l.id, 1 << 30))
                return []
            except Exception as e:
                logger.warning("FTS5 search fail, fallback LIKE: %s", e)
        # Fallback LIKE
        pattern = f"%{query}%"
        stmt = (
            select(Letter)
            .where(
                Letter.user_id == user_id,
                Letter.deleted_at.is_(None),
                or_(
                    Letter.title.ilike(pattern),
                    Letter.sender.ilike(pattern),
                    Letter.ocr_text.ilike(pattern),
                    Letter.notes.ilike(pattern),
                    Letter.llm_summary.ilike(pattern),
                ),
            )
            .options(joinedload(Letter.tags), joinedload(Letter.files))
            .order_by(Letter.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return self.db.execute(stmt).unique().scalars().all()
