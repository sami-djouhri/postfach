"""Add snoozed_until + paperless_id to letter.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("letter") as batch:
        batch.add_column(sa.Column("snoozed_until", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("paperless_id", sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("letter") as batch:
        batch.drop_column("paperless_id")
        batch.drop_column("snoozed_until")
