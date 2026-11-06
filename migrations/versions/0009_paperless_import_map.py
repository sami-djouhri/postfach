"""Add paperless_import_map for idempotent paperless -> briefkasten migration.

Mappt Paperless-Document-IDs auf briefkasten Letter-IDs, damit ein wiederholter
Lauf von scripts/migrate-from-paperless.py keine Duplikate erzeugt.

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-14
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(conn, name: str) -> bool:
    return (
        conn.execute(
            sa.text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:n"),
            {"n": name},
        ).first()
        is not None
    )


def upgrade() -> None:
    conn = op.get_bind()
    if not _has_table(conn, "paperless_import_map"):
        op.execute(
            """
            CREATE TABLE paperless_import_map (
                paperless_doc_id INTEGER PRIMARY KEY,
                letter_id INTEGER NOT NULL,
                imported_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                source_url VARCHAR(255),
                checksum VARCHAR(128),
                FOREIGN KEY(letter_id) REFERENCES letter(id) ON DELETE CASCADE
            )
            """
        )
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_paperless_import_map_letter "
            "ON paperless_import_map(letter_id)"
        )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_paperless_import_map_letter")
    op.execute("DROP TABLE IF EXISTS paperless_import_map")
