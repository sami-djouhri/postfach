"""Add correspondent + letter.correspondent_id (idempotent)."""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(conn, name):
    return conn.execute(sa.text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:n"), {"n": name}).first() is not None


def _has_column(conn, table, col):
    rows = conn.execute(sa.text(f"PRAGMA table_info({table})")).all()
    return any(r[1] == col for r in rows)


def upgrade() -> None:
    conn = op.get_bind()
    if not _has_table(conn, "correspondent"):
        op.execute("""
            CREATE TABLE correspondent (
                id INTEGER NOT NULL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                name VARCHAR(300) NOT NULL,
                normalized VARCHAR(300) NOT NULL,
                address TEXT,
                contact_info TEXT,
                notes TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_correspondent_user_norm UNIQUE (user_id, normalized),
                FOREIGN KEY(user_id) REFERENCES user(id) ON DELETE CASCADE
            )
        """)
        op.execute("CREATE INDEX IF NOT EXISTS ix_correspondent_normalized ON correspondent(normalized)")
    if not _has_column(conn, "letter", "correspondent_id"):
        op.execute("ALTER TABLE letter ADD COLUMN correspondent_id INTEGER REFERENCES correspondent(id) ON DELETE SET NULL")
        op.execute("CREATE INDEX IF NOT EXISTS ix_letter_correspondent_id ON letter(correspondent_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_letter_correspondent_id")
    op.execute("DROP TABLE IF EXISTS correspondent")
