"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=True),
        sa.Column("last_name", sa.String(length=100), nullable=True),
        sa.Column("occupation", sa.String(length=100), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="user"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # conversations
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])

    # messages
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "conversation_id",
            sa.Uuid(),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("agent_id", sa.String(length=50), nullable=True),
        sa.Column("citations", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    # agent_settings
    op.create_table(
        "agent_settings",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("slug", sa.String(length=50), nullable=False, unique=True),
        sa.Column("name", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("llm_model", sa.String(length=100), nullable=True, server_default="gpt-5.4-nano"),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("retrieval_top_k", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("retrieval_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("web_search_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("connected_sources", sa.JSON(), nullable=True, server_default="[]"),
        sa.Column("tools", sa.JSON(), nullable=True, server_default="[]"),
        sa.Column("mode_profile", sa.JSON(), nullable=True),
        sa.Column("is_orchestrator", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("routes_to", sa.JSON(), nullable=True),
        sa.Column("visibility", sa.String(length=20), nullable=False, server_default="all"),
        sa.Column("allowed_users", sa.JSON(), nullable=True, server_default="[]"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # connectors
    op.create_table(
        "connectors",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("slug", sa.String(length=50), nullable=False, unique=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("connector_type", sa.Enum("notion", "s3", "sharepoint", "jira", name="connector_type"), nullable=False),
        sa.Column("credentials_encrypted", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # knowledge_sources
    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("slug", sa.String(length=50), nullable=False, unique=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "source_type",
            sa.Enum("notion", "s3", name="knowledge_source_type"),
            nullable=False,
        ),
        sa.Column("config", sa.JSON(), nullable=True, server_default="{}"),
        sa.Column(
            "status",
            sa.Enum("pending", "syncing", "ready", "error", name="knowledge_source_status"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("connector_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_foreign_key(
        "fk_knowledge_sources_connector",
        "knowledge_sources",
        "connectors",
        ["connector_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_table("knowledge_sources")
    op.execute("DROP TYPE IF EXISTS knowledge_source_status")
    op.execute("DROP TYPE IF EXISTS knowledge_source_type")
    op.drop_table("connectors")
    op.execute("DROP TYPE IF EXISTS connector_type")
    op.drop_table("agent_settings")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_conversations_user_id", table_name="conversations")
    op.drop_table("conversations")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
