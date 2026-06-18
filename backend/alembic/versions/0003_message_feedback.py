"""add message feedback and tool_calls_log

Revision ID: 0003
Revises: 0001
down_revision: 0001
Create Date: 2026-06-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add tool_calls_log to messages
    op.add_column("messages", sa.Column("tool_calls_log", sa.JSON(), nullable=True))

    # Create message_feedback table
    op.create_table(
        "message_feedback",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "message_id",
            sa.Uuid(),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent_id", sa.String(length=50), nullable=False),
        sa.Column("thumbs_up", sa.Boolean(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "screenshot_attachment_id",
            sa.Uuid(),
            sa.ForeignKey("chat_attachments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("conversation_snapshot", sa.JSON(), nullable=True),
        sa.Column("tool_calls_log", sa.JSON(), nullable=True),
        sa.Column("retrieved_sources", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_message_feedback_agent_id", "message_feedback", ["agent_id"])
    op.create_index("ix_message_feedback_thumbs_up", "message_feedback", ["thumbs_up"])
    op.create_index("ix_message_feedback_conversation_id", "message_feedback", ["conversation_id"])
    op.create_index("ix_message_feedback_message_id", "message_feedback", ["message_id"])
    op.create_index("ix_message_feedback_user_id", "message_feedback", ["user_id"])
    op.create_unique_constraint(
        "uq_message_feedback_message_user",
        "message_feedback",
        ["message_id", "user_id"],
    )


def downgrade() -> None:
    op.drop_table("message_feedback")
    op.drop_column("messages", "tool_calls_log")
