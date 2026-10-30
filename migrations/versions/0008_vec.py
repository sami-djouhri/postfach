"""Add letter_vec virtual table for semantic search via sqlite-vec (384 dim).

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-14
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(conn, name):
    return conn.execute(sa.text("SELECT 1 FROM sqlite_master WHERE name=:n"), {"n": name}).first() is not None


def upgrade() -> None:
    conn = op.get_bind()
    if not _has_table(conn, "letter_vec"):
        # vec0 erfordert geladene sqlite-vec extension: passiert in db.py beim connect.
        op.execute("CREATE VIRTUAL TABLE letter_vec USING vec0(embedding float[384])")
    # Separate Metadata-Tabelle: model-version + indexed_at, damit Reindex möglich
    if not _has_table(conn, "letter_vec_meta"):
        op.execute("""
            CREATE TABLE letter_vec_meta (
                letter_id INTEGER PRIMARY KEY,
                model VARCHAR(120) NOT NULL,
                indexed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(letter_id) REFERENCES letter(id) ON DELETE CASCADE
            )
        """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS letter_vec_meta")
    op.execute("DROP TABLE IF EXISTS letter_vec")
