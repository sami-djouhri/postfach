"""Frist und Erledigt-Zeitpunkt am Brief (letter.frist_bis, letter.erledigt_am).

Zwei Spalten, beide nullable, keine Ruecksetzung bestehender Daten:

* ``frist_bis`` (Datum): bis wann am Brief etwas zu tun ist. Gesetzt wird sie
  NUR vom Nutzer. Analyse und Texterkennung duerfen eine Frist vorschlagen
  (``app/services/frist_service.py``), uebernommen wird sie erst mit einem
  ausdruecklichen ``PUT``. Ein Vorschlag, der sich selbst eintraegt, waere
  eine erfundene Frist, die wie eine bestaetigte aussieht.
* ``erledigt_am`` (Zeitpunkt): wann der Brief abgehakt wurde. ``NULL`` heisst
  offen. Ein Zeitpunkt statt eines Schalters, damit "erledigt" eine Auskunft
  traegt und sich zuruecknehmen laesst, ohne etwas zu verlieren.

Der Teilindex deckt genau die eine Abfrage, fuer die es die Spalten gibt: die
offenen Fristen oben in der Uebersicht.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-13
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _hat_spalte(conn, tabelle: str, spalte: str) -> bool:
    return spalte in {r[1] for r in conn.exec_driver_sql(f"PRAGMA table_info({tabelle})")}


def upgrade() -> None:
    conn = op.get_bind()
    if not _hat_spalte(conn, "letter", "frist_bis"):
        op.add_column("letter", sa.Column("frist_bis", sa.Date(), nullable=True))
    if not _hat_spalte(conn, "letter", "erledigt_am"):
        op.add_column("letter", sa.Column("erledigt_am", sa.DateTime(), nullable=True))
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_letter_frist_offen ON letter (user_id, frist_bis) "
        "WHERE frist_bis IS NOT NULL AND erledigt_am IS NULL"
    )


def downgrade() -> None:
    conn = op.get_bind()
    # Erst der Index: SQLite verweigert DROP COLUMN auf eine indizierte Spalte.
    op.execute("DROP INDEX IF EXISTS ix_letter_frist_offen")
    if _hat_spalte(conn, "letter", "erledigt_am"):
        op.drop_column("letter", "erledigt_am")
    if _hat_spalte(conn, "letter", "frist_bis"):
        op.drop_column("letter", "frist_bis")
