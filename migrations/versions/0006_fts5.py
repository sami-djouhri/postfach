"""Add FTS5 virtual table letter_fts + sync triggers.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-14

"""
from typing import Sequence, Union

from alembic import op


revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# FTS5 ist in SQLite-Default-Builds (Debian python3-Image, hier python:3.13-slim) aktiv.
# `content='letter'` macht es zu einer "contentless"-FTS5 (External Content Table):
# der Inhalt liegt im normalen `letter`-Table, FTS5 hält nur den Index. Wir müssen
# Triggers für INSERT/UPDATE/DELETE auf letter selbst pflegen.


def upgrade() -> None:
    op.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS letter_fts USING fts5(
            title, sender, ocr_text, llm_summary, notes,
            content='letter', content_rowid='id', tokenize='unicode61'
        )
    """)
    op.execute("""
        CREATE TRIGGER IF NOT EXISTS letter_ai AFTER INSERT ON letter BEGIN
            INSERT INTO letter_fts(rowid, title, sender, ocr_text, llm_summary, notes)
            VALUES (new.id, new.title, new.sender, new.ocr_text, new.llm_summary, new.notes);
        END
    """)
    op.execute("""
        CREATE TRIGGER IF NOT EXISTS letter_ad AFTER DELETE ON letter BEGIN
            INSERT INTO letter_fts(letter_fts, rowid, title, sender, ocr_text, llm_summary, notes)
            VALUES ('delete', old.id, old.title, old.sender, old.ocr_text, old.llm_summary, old.notes);
        END
    """)
    op.execute("""
        CREATE TRIGGER IF NOT EXISTS letter_au AFTER UPDATE ON letter BEGIN
            INSERT INTO letter_fts(letter_fts, rowid, title, sender, ocr_text, llm_summary, notes)
            VALUES ('delete', old.id, old.title, old.sender, old.ocr_text, old.llm_summary, old.notes);
            INSERT INTO letter_fts(rowid, title, sender, ocr_text, llm_summary, notes)
            VALUES (new.id, new.title, new.sender, new.ocr_text, new.llm_summary, new.notes);
        END
    """)
    # Backfill existierende Briefe: idempotent via DELETE first.
    op.execute("INSERT INTO letter_fts(letter_fts) VALUES('delete-all')")
    op.execute("""
        INSERT INTO letter_fts(rowid, title, sender, ocr_text, llm_summary, notes)
        SELECT id, title, sender, ocr_text, llm_summary, notes FROM letter
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS letter_au")
    op.execute("DROP TRIGGER IF EXISTS letter_ad")
    op.execute("DROP TRIGGER IF EXISTS letter_ai")
    op.execute("DROP TABLE IF EXISTS letter_fts")
