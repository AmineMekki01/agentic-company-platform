"""add agent_type and research_config columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "agent_settings",
        sa.Column("agent_type", sa.String(length=20), nullable=False, server_default="standard"),
    )
    op.add_column(
        "agent_settings",
        sa.Column("research_config", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("agent_settings", "research_config")
    op.drop_column("agent_settings", "agent_type")
