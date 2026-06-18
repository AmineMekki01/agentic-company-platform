"""create feedback_attachments table

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create feedback_attachments table
    op.create_table(
        "feedback_attachments",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "feedback_id",
            sa.Uuid(),
            sa.ForeignKey("message_feedback.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("s3_bucket", sa.String(255), nullable=False),
        sa.Column("s3_key", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Drop existing FK from message_feedback to chat_attachments
    op.drop_constraint(
        "message_feedback_screenshot_attachment_id_fkey",
        "message_feedback",
        type_="foreignkey",
    )

    # Create new FK from message_feedback to feedback_attachments
    op.create_foreign_key(
        "fk_message_feedback_screenshot",
        "message_feedback",
        "feedback_attachments",
        ["screenshot_attachment_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Drop new FK
    op.drop_constraint("fk_message_feedback_screenshot", "message_feedback", type_="foreignkey")

    # Recreate old FK to chat_attachments
    op.create_foreign_key(
        "message_feedback_screenshot_attachment_id_fkey",
        "message_feedback",
        "chat_attachments",
        ["screenshot_attachment_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_table("feedback_attachments")
