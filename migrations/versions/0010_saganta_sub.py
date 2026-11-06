"""Postfach an das Saganta-Konto binden koennen (user.sub).

Der Briefkasten hatte seine Mandantentrennung ueber ``letter.user_id`` von
Anfang an, und sie traegt. Was fehlte, war eine gemeinsame Identitaet mit dem
Rest der Suite: die Anmeldung lief entweder ueber die eigene Nutzertabelle oder
ueber ``SAGANTA_SESSION_TOKEN``, und der meldet **jeden** Aufrufer als denselben
Nutzer an. Solange es einen Nutzer gibt, faellt das nicht auf. Mit dem zweiten
sehen beide dieselbe Post.

Diese Migration legt nur die Spalte an. **Die Zuordnung selbst passiert nicht
hier**, sondern sichtbar mit ``scripts/postfach-binden.py``. Der Grund steht dort
ausfuehrlich: eine Migration braeuchte die Kennung eines konkreten Menschen aus
der Umgebung oder aus dem Quelltext, und beides ist fuer einen Dienst falsch, der
veroeffentlicht werden soll.

Solange nichts gebunden ist, aendert sich nichts: ohne ``X-Saganta-Sub`` laeuft
alles wie bisher ueber die Sitzungs-Anmeldung.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _hat_spalte(conn, tabelle: str, spalte: str) -> bool:
    return spalte in {r[1] for r in conn.exec_driver_sql(f"PRAGMA table_info({tabelle})")}


def upgrade() -> None:
    conn = op.get_bind()
    if _hat_spalte(conn, "user", "sub"):
        return

    op.add_column("user", sa.Column("sub", sa.String(length=64), nullable=True))
    # Teil-Index: mehrere Alt-Konten ohne Saganta-Konto sind erlaubt, zwei
    # Postfaecher am selben Saganta-Konto nicht. SQLite laesst in einem
    # gewoehnlichen UNIQUE-Index zwar beliebig viele NULL zu, der WHERE-Zusatz
    # macht die Absicht aber lesbar, statt sie einer Datenbank-Eigenheit zu
    # ueberlassen.
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_user_sub ON user (sub) WHERE sub IS NOT NULL"
    )


def downgrade() -> None:
    conn = op.get_bind()
    op.execute("DROP INDEX IF EXISTS ix_user_sub")
    if _hat_spalte(conn, "user", "sub"):
        op.drop_column("user", "sub")
