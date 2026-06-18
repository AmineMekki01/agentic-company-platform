"""drop redundant feedback_id from feedback_attachments

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the redundant FK and column
    op.drop_constraint(
        "feedback_attachments_feedback_id_fkey",
        "feedback_attachments",
        type_="foreignkey",
    )
    op.drop_index("ix_feedback_attachments_feedback_id", "feedback_attachments")
    op.drop_column("feedback_attachments", "feedback_id")


def downgrade() -> None:
    op.add_column(
        "feedback_attachments",
        sa.Column("feedback_id", sa.Uuid(), nullable=True),
    )
    op.create_index(
        "ix_feedback_attachments_feedback_id",
        "feedback_attachments",
        ["feedback_id"],
        unique=False,
    )
    op.create_foreign_key(
        "feedback_attachments_feedback_id_fkey",
        "feedback_attachments",
        "message_feedback",
        ["feedback_id"],
        ["id"],
        ondelete="CASCADE",
    )
