"""Add analysis_status to letter.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("letter") as batch:
        batch.add_column(
            sa.Column(
                "analysis_status",
                sa.String(length=20),
                nullable=False,
                server_default="none",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("letter") as batch:
        batch.drop_column("analysis_status")
