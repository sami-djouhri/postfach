"""Add account + letter.account_id (idempotent)."""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(conn, name):
    return conn.execute(sa.text("SELECT 1 FROM sqlite_master WHERE type='table' AND name=:n"), {"n": name}).first() is not None


def _has_column(conn, table, col):
    rows = conn.execute(sa.text(f"PRAGMA table_info({table})")).all()
    return any(r[1] == col for r in rows)


def upgrade() -> None:
    conn = op.get_bind()
    if not _has_table(conn, "account"):
        op.execute("""
            CREATE TABLE account (
                id INTEGER NOT NULL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                correspondent_id INTEGER,
                name VARCHAR(200) NOT NULL,
                kind VARCHAR(60),
                contract_number VARCHAR(120),
                monthly_amount NUMERIC,
                start_date VARCHAR(10),
                end_date VARCHAR(10),
                notice_period_months INTEGER,
                notice_deadline VARCHAR(10),
                notes TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES user(id) ON DELETE CASCADE,
                FOREIGN KEY(correspondent_id) REFERENCES correspondent(id) ON DELETE SET NULL
            )
        """)
        op.execute("CREATE INDEX IF NOT EXISTS ix_account_user_id ON account(user_id)")
    if not _has_column(conn, "letter", "account_id"):
        op.execute("ALTER TABLE letter ADD COLUMN account_id INTEGER REFERENCES account(id) ON DELETE SET NULL")
        op.execute("CREATE INDEX IF NOT EXISTS ix_letter_account_id ON letter(account_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_letter_account_id")
    op.execute("DROP INDEX IF EXISTS ix_account_user_id")
    op.execute("DROP TABLE IF EXISTS account")
