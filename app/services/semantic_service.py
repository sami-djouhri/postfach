"""Semantic-Search via sqlite-vec + externer embedding-service.

embedding-service: cc-core/embedding-service:8000 mit `POST /embed`
sqlite-vec: vec0() virtual table mit 384-dim float-vectors

Pipeline-Hook: nach LLM-Analyse wird der kombinierte Text
(title + sender + summary + ocr_text-Head) eingebettet und in letter_vec
gespeichert. Search: User-Query embedden, kNN über vec0() MATCH.
"""
from __future__ import annotations

import json
import logging
import os
import struct
from typing import Iterable, Optional

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Letter

logger = logging.getLogger(__name__)

EMBEDDING_URL = os.environ.get("EMBEDDING_URL", "http://embedding-service:8000")
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"  # info-tag
VECTOR_DIM = 384
OCR_HEAD_CHARS = 1500


def _pack(vec: list[float]) -> bytes:
    if len(vec) != VECTOR_DIM:
        raise ValueError(f"vector dim mismatch: expected {VECTOR_DIM}, got {len(vec)}")
    return struct.pack(f"{VECTOR_DIM}f", *vec)


def _build_text(letter: Letter) -> str:
    parts = [letter.title or ""]
    if letter.sender:
        parts.append(f"Absender: {letter.sender}")
    if letter.category:
        parts.append(f"Kategorie: {letter.category}")
    if letter.llm_summary:
        parts.append(letter.llm_summary)
    if letter.ocr_text:
        parts.append(letter.ocr_text[:OCR_HEAD_CHARS])
    return "\n".join(p for p in parts if p)


def embed_text(text_input: str | list[str], timeout: float = 30) -> list[list[float]]:
    """Synchron embedden: fastembed liefert pro Text ein Vec[384]."""
    payload = {"input": text_input}
    resp = httpx.post(f"{EMBEDDING_URL}/embed", json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    return data["vectors"]


def index_letter(db: Session, letter: Letter) -> bool:
    """Letter (re)indexieren. True bei Erfolg, False bei (loggable) Fehler."""
    try:
        text_to_embed = _build_text(letter)
        if not text_to_embed.strip():
            return False
        vectors = embed_text(text_to_embed)
        if not vectors:
            return False
        vec = vectors[0]
        blob = _pack(vec)
        # Upsert via DELETE + INSERT: vec0 hat kein on-conflict.
        db.execute(text("DELETE FROM letter_vec WHERE rowid=:rid"), {"rid": letter.id})
        db.execute(
            text("INSERT INTO letter_vec(rowid, embedding) VALUES (:rid, :emb)"),
            {"rid": letter.id, "emb": blob},
        )
        db.execute(
            text("""
                INSERT INTO letter_vec_meta(letter_id, model, indexed_at)
                VALUES (:rid, :m, CURRENT_TIMESTAMP)
                ON CONFLICT(letter_id) DO UPDATE SET model=:m, indexed_at=CURRENT_TIMESTAMP
            """),
            {"rid": letter.id, "m": EMBEDDING_MODEL},
        )
        db.commit()
        return True
    except Exception as e:
        logger.warning("semantic index failed for letter %s: %s", letter.id, e)
        db.rollback()
        return False


def search(db: Session, user_id: int, query: str, limit: int = 10) -> list[tuple[int, float]]:
    """k-NN-Suche → (letter_id, distance). Niedriger ist besser."""
    if not query.strip():
        return []
    vectors = embed_text(query)
    if not vectors:
        return []
    blob = _pack(vectors[0])
    rows = db.execute(
        text("""
            SELECT v.rowid, v.distance
            FROM letter_vec v
            JOIN letter l ON l.id = v.rowid
            WHERE v.embedding MATCH :q
              AND l.user_id = :uid
              AND l.deleted_at IS NULL
              AND k = :k
            ORDER BY v.distance
        """),
        {"q": blob, "uid": user_id, "k": limit},
    ).all()
    return [(r[0], float(r[1])) for r in rows]
