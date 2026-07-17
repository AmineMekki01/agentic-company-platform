"""initial schema — multi-tenant foundation (tables, default tenant, RLS)

Consolidated single migration for the pre-deployment dev database. Creates every
table, seeds the default tenant, applies composite per-tenant uniqueness and
foreign keys, and enables Row-Level Security. Later real migrations build on top.

Revision ID: 0001
Revises:
"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.core.config import settings
from app.db.rls import apply_rls, remove_rls

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_TENANT_ID = settings.default_tenant_id

OWNED = [
    "users", "agent_settings", "agent_versions", "agent_workflows", "agent_skills",
    "skills", "agent_memories", "agent_emotion_states", "agent_episodes",
    "agent_eval_tests", "agent_eval_test_sets", "agent_eval_runs", "agent_eval_results",
    "agent_eval_schedules", "conversations", "conversation_folders", "messages",
    "chat_attachments", "message_feedback", "feedback_attachments", "connectors",
    "secrets", "knowledge_sources", "token_usage", "token_budgets", "upload_settings",
]

NOT_NULL = [
    "users", "agent_settings", "agent_versions", "agent_workflows", "agent_skills",
    "skills", "agent_memories", "agent_emotion_states", "agent_episodes",
    "agent_eval_tests", "agent_eval_test_sets", "agent_eval_runs", "agent_eval_results",
    "agent_eval_schedules", "conversations", "conversation_folders", "messages",
    "chat_attachments", "message_feedback", "feedback_attachments", "connectors",
    "secrets", "knowledge_sources", "token_usage", "token_budgets", "upload_settings",
    "llm_settings",
]

SLUG_TABLES = ["agent_settings", "connectors", "knowledge_sources", "secrets"]


def upgrade() -> None:
    # ===== base tables =====
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
        sa.Column("entry_agent", sa.String(length=50), nullable=True),
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
        sa.Column("tool_calls_log", sa.JSON(), nullable=True),
        sa.Column("trace_url", sa.String(length=500), nullable=True),
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
        sa.Column("web_search_max_results", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("jira_tickets_limit", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("connected_sources", sa.JSON(), nullable=True, server_default="[]"),
        sa.Column("tools", sa.JSON(), nullable=True, server_default="[]"),
        sa.Column("mode_profile", sa.JSON(), nullable=True),
        sa.Column("is_orchestrator", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_router", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("routes_to", sa.JSON(), nullable=True),
        sa.Column("visibility", sa.String(length=20), nullable=False, server_default="all"),
        sa.Column("agent_type", sa.String(length=20), nullable=False, server_default="standard"),
        sa.Column("research_config", sa.JSON(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("allow_uploads", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("allowed_users", sa.JSON(), nullable=True, server_default="[]"),
        sa.Column("draft_config", sa.JSON(), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_version_id", sa.Uuid(), nullable=True),
        sa.Column("beta_users", sa.JSON(), nullable=True, server_default="[]"),
        sa.Column("memory_enabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("emotions_enabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("episodes_enabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION agent_settings_set_updated_at()
        RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_agent_settings_updated_at
        BEFORE UPDATE ON agent_settings
        FOR EACH ROW
        EXECUTE FUNCTION agent_settings_set_updated_at();
        """
    )

    # agent_versions
    op.create_table(
        "agent_versions",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "agent_settings_id",
            sa.Uuid(),
            sa.ForeignKey("agent_settings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_agent_versions_agent_settings_id",
        "agent_versions",
        ["agent_settings_id"],
    )
    op.create_index(
        "ix_agent_versions_version_number",
        "agent_versions",
        ["agent_settings_id", "version_number"],
        unique=True,
    )

    # FK from agent_settings to agent_versions
    op.create_foreign_key(
        "fk_agent_settings_published_version",
        "agent_settings",
        "agent_versions",
        ["published_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # secrets
    op.create_table(
        "secrets",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("slug", sa.String(length=50), nullable=False, unique=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("secret_type", sa.Enum("s3", "gdrive", "notion", "jira", "custom", name="secret_type"), nullable=False),
        sa.Column("credentials_encrypted", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # connectors
    op.create_table(
        "connectors",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("slug", sa.String(length=50), nullable=False, unique=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("connector_type", sa.Enum("notion", "s3", "jira", "gdrive", name="connector_type"), nullable=False),
        sa.Column("secret_id", sa.Uuid(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_foreign_key(
        "fk_connectors_secret",
        "connectors",
        "secrets",
        ["secret_id"],
        ["id"],
    )

    # knowledge_sources
    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("slug", sa.String(length=50), nullable=False, unique=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column(
            "source_type",
            sa.Enum("notion", "s3", "gdrive", name="knowledge_source_type"),
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

    # upload_settings
    op.create_table(
        "upload_settings",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("s3_connector_id", sa.Uuid(), nullable=True),
        sa.Column("s3_bucket", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("s3_base_prefix", sa.String(length=500), nullable=False, server_default="uploads/"),
        sa.Column("retention_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("max_file_size_mb", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("encryption", sa.String(length=20), nullable=False, server_default="AES256"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "fk_upload_settings_connector",
        "upload_settings",
        "connectors",
        ["s3_connector_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # chat_attachments
    op.create_table(
        "chat_attachments",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
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
        sa.Column("message_id", sa.Uuid(), nullable=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("s3_bucket", sa.String(length=255), nullable=False),
        sa.Column("s3_key", sa.Text(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("retention_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_chat_attachments_conversation_id", "chat_attachments", ["conversation_id"])
    op.create_index("ix_chat_attachments_user_id", "chat_attachments", ["user_id"])
    op.create_index("ix_chat_attachments_message_id", "chat_attachments", ["message_id"])
    op.create_foreign_key(
        "fk_chat_attachments_message",
        "chat_attachments",
        "messages",
        ["message_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "agent_workflows",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "owner_agent_slug",
            sa.String(length=50),
            sa.ForeignKey("agent_settings.slug", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("definition", sa.JSON(), nullable=False),
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
    op.create_index(
        "ix_agent_workflows_owner_agent_slug",
        "agent_workflows",
        ["owner_agent_slug"],
    )

    op.create_table(
        "conversation_folders",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("color", sa.String(length=7), nullable=True),
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
    op.create_index(
        "ix_conversation_folders_user_id",
        "conversation_folders",
        ["user_id"],
    )

    op.add_column(
        "conversations",
        sa.Column(
            "folder_id",
            sa.Uuid(),
            sa.ForeignKey("conversation_folders.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_conversations_folder_id",
        "conversations",
        ["folder_id"],
    )

    # message_feedback
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
        sa.Column("agent_id", sa.String(length=50), nullable=True),
        sa.Column("thumbs_up", sa.Boolean(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("screenshot_attachment_id", sa.Uuid(), nullable=True),
        sa.Column("conversation_snapshot", sa.JSON(), nullable=True),
        sa.Column("tool_calls_log", sa.JSON(), nullable=True),
        sa.Column("retrieved_sources", sa.JSON(), nullable=True),
        sa.Column("conversation_actions", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_message_feedback_message_id", "message_feedback", ["message_id"])
    op.create_index("ix_message_feedback_conversation_id", "message_feedback", ["conversation_id"])
    op.create_index("ix_message_feedback_user_id", "message_feedback", ["user_id"])

    # feedback_attachments
    op.create_table(
        "feedback_attachments",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "feedback_id",
            sa.Uuid(),
            sa.ForeignKey("message_feedback.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=True),
        sa.Column("s3_bucket", sa.String(length=255), nullable=False),
        sa.Column("s3_key", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # agent_eval_test_sets
    op.create_table(
        "agent_eval_test_sets",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "agent_id",
            sa.Uuid(),
            sa.ForeignKey("agent_settings.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # agent_eval_tests
    op.create_table(
        "agent_eval_tests",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "test_set_id",
            sa.Uuid(),
            sa.ForeignKey("agent_eval_test_sets.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("expected_answer", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # agent_eval_runs
    op.create_table(
        "agent_eval_runs",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "agent_id",
            sa.Uuid(),
            sa.ForeignKey("agent_settings.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("thresholds", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=False),
        sa.Column(
            "config_source",
            sa.String(length=20),
            nullable=False,
            server_default="published",
        ),
        sa.Column(
            "agent_version_id",
            sa.Uuid(),
            sa.ForeignKey("agent_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # agent_eval_results
    op.create_table(
        "agent_eval_results",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "run_id",
            sa.Uuid(),
            sa.ForeignKey("agent_eval_runs.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "test_id",
            sa.Uuid(),
            sa.ForeignKey("agent_eval_tests.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("actual_answer", sa.Text(), nullable=True),
        sa.Column("retrieved_contexts", sa.JSON(), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("metric_passes", sa.JSON(), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("passed", sa.Boolean(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("trace_url", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # agent_eval_schedules
    op.create_table(
        "agent_eval_schedules",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column(
            "agent_id",
            sa.Uuid(),
            sa.ForeignKey("agent_settings.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("frequency", sa.String(length=20), nullable=False),
        sa.Column("interval", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("test_set_ids", sa.JSON(), nullable=True),
        sa.Column("thresholds", sa.JSON(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.String(length=255), nullable=False),
    )

    # llm_settings
    op.create_table(
        "llm_settings",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("ollama_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "ollama_base_url",
            sa.String(length=500),
            nullable=False,
            server_default="http://ollama:11434/v1",
        ),
        sa.Column(
            "ollama_enabled_models",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # token_usage
    op.create_table(
        "token_usage",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("agent_slug", sa.String(50), nullable=False, index=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False, index=True),
    )

    # token_budgets
    op.create_table(
        "token_budgets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("scope", sa.String(10), nullable=False),
        sa.Column("scope_id", sa.String(255), nullable=False),
        sa.Column("monthly_cost_limit_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("scope", "scope_id", name="uq_token_budgets_scope_scope_id"),
    )

    # skills
    op.create_table(
        "skills",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("scope", sa.String(length=20), nullable=False, server_default="shared"),
        sa.Column(
            "agent_slug",
            sa.String(length=50),
            sa.ForeignKey("agent_settings.slug", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.String(length=255), nullable=True),
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

    # agent_skills
    op.create_table(
        "agent_skills",
        sa.Column(
            "agent_slug",
            sa.String(length=50),
            sa.ForeignKey("agent_settings.slug", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "skill_id",
            sa.Uuid(),
            sa.ForeignKey("skills.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
    )

    # agent_emotion_states
    op.create_table(
        "agent_emotion_states",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_slug", sa.String(length=50), nullable=False),
        sa.Column("joy", sa.Float(), nullable=False, server_default="0.3"),
        sa.Column("trust", sa.Float(), nullable=False, server_default="0.3"),
        sa.Column("fear", sa.Float(), nullable=False, server_default="0.1"),
        sa.Column("surprise", sa.Float(), nullable=False, server_default="0.1"),
        sa.Column("sadness", sa.Float(), nullable=False, server_default="0.1"),
        sa.Column("disgust", sa.Float(), nullable=False, server_default="0.1"),
        sa.Column("anger", sa.Float(), nullable=False, server_default="0.1"),
        sa.Column("anticipation", sa.Float(), nullable=False, server_default="0.3"),
        sa.Column("joy_baseline", sa.Float(), nullable=False, server_default="0.3"),
        sa.Column("trust_baseline", sa.Float(), nullable=False, server_default="0.3"),
        sa.Column("fear_baseline", sa.Float(), nullable=False, server_default="0.1"),
        sa.Column("surprise_baseline", sa.Float(), nullable=False, server_default="0.1"),
        sa.Column("sadness_baseline", sa.Float(), nullable=False, server_default="0.1"),
        sa.Column("disgust_baseline", sa.Float(), nullable=False, server_default="0.1"),
        sa.Column("anger_baseline", sa.Float(), nullable=False, server_default="0.1"),
        sa.Column("anticipation_baseline", sa.Float(), nullable=False, server_default="0.3"),
        sa.Column("last_interaction_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("user_id", "agent_slug", name="uq_emotion_user_agent"),
    )

    op.create_table(
        "agent_episodes",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_slug", sa.String(length=50), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("emotion_snapshot", sa.JSON(), nullable=False),
        sa.Column("significance_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("trigger", sa.String(length=50), nullable=False, server_default="high_emotion"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_agent_episodes_user_agent", "agent_episodes", ["user_id", "agent_slug"])

    op.create_table(
        "agent_memories",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_slug", sa.String(length=50), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("importance_score", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("tags", sa.JSON(), nullable=True, server_default="[]"),
        sa.Column("embedding", sa.JSON(), nullable=True),
        sa.Column("qdrant_point_id", sa.String(length=255), nullable=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_message_id", sa.Uuid(), nullable=True),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("access_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("decay_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_agent_memories_user_agent", "agent_memories", ["user_id", "agent_slug"])
    op.create_index("ix_agent_memories_user_category", "agent_memories", ["user_id", "category"])

    # ===== tenants + tenant_id columns + default tenant =====
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("slug", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.bulk_insert(
        sa.table(
            "tenants",
            sa.column("id", sa.Uuid()), sa.column("slug", sa.String),
            sa.column("name", sa.String), sa.column("status", sa.String),
        ),
        [{"id": uuid.UUID(DEFAULT_TENANT_ID), "slug": "default", "name": "Default", "status": "active"}],
    )

    # llm_settings.tenant_id (unique - one settings row per tenant)
    op.add_column("llm_settings", sa.Column("tenant_id", sa.Uuid(), nullable=True))
    op.execute(f"UPDATE llm_settings SET tenant_id = '{DEFAULT_TENANT_ID}'")
    op.create_unique_constraint("uq_llm_settings_tenant", "llm_settings", ["tenant_id"])
    op.create_foreign_key(
        "fk_llm_settings_tenant", "llm_settings", "tenants",
        ["tenant_id"], ["id"], ondelete="CASCADE",
    )

    for table in OWNED:
        op.add_column(table, sa.Column("tenant_id", sa.Uuid(), nullable=True))
        op.execute(f"UPDATE {table} SET tenant_id = '{DEFAULT_TENANT_ID}'")
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])
        op.create_foreign_key(
            f"fk_{table}_tenant", table, "tenants",
            ["tenant_id"], ["id"], ondelete="CASCADE",
        )

    # ===== NOT NULL + composite uniques + composite slug FKs =====
    for table in NOT_NULL:
        op.alter_column(table, "tenant_id", nullable=False)

    # Drop the FKs that target agent_settings.slug before dropping that unique.
    op.drop_constraint("agent_skills_agent_slug_fkey", "agent_skills", type_="foreignkey")
    op.drop_constraint("skills_agent_slug_fkey", "skills", type_="foreignkey")
    op.drop_constraint("agent_workflows_owner_agent_slug_fkey", "agent_workflows", type_="foreignkey")

    # Global slug uniques -> composite (tenant_id, slug)
    for table in SLUG_TABLES:
        op.drop_constraint(f"{table}_slug_key", table, type_="unique")
        op.create_unique_constraint(f"uq_{table}_tenant_slug", table, ["tenant_id", "slug"])

    # Recreate the slug FKs as composite (tenant_id, slug) -> agent_settings(tenant_id, slug)
    op.create_foreign_key(
        "fk_agent_skills_agent", "agent_skills", "agent_settings",
        ["tenant_id", "agent_slug"], ["tenant_id", "slug"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_skills_agent", "skills", "agent_settings",
        ["tenant_id", "agent_slug"], ["tenant_id", "slug"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_agent_workflows_agent", "agent_workflows", "agent_settings",
        ["tenant_id", "owner_agent_slug"], ["tenant_id", "slug"], ondelete="CASCADE",
    )

    # ===== Row-Level Security =====
    apply_rls(op.execute)

    # ===== per-tenant tracing_mode =====
    op.add_column(
        "llm_settings",
        sa.Column("tracing_mode", sa.String(10), nullable=False, server_default="full"),
    )



def downgrade() -> None:
    # ===== undo tracing_mode =====
    op.drop_column("llm_settings", "tracing_mode")

    # ===== undo Row-Level Security =====
    remove_rls(op.execute)

    # ===== undo constraints =====
    op.drop_constraint("fk_agent_workflows_agent", "agent_workflows", type_="foreignkey")
    op.drop_constraint("fk_skills_agent", "skills", type_="foreignkey")
    op.drop_constraint("fk_agent_skills_agent", "agent_skills", type_="foreignkey")

    for table in SLUG_TABLES:
        op.drop_constraint(f"uq_{table}_tenant_slug", table, type_="unique")
        op.create_unique_constraint(f"{table}_slug_key", table, ["slug"])

    op.create_foreign_key(
        "skills_agent_slug_fkey", "skills", "agent_settings",
        ["agent_slug"], ["slug"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "agent_skills_agent_slug_fkey", "agent_skills", "agent_settings",
        ["agent_slug"], ["slug"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "agent_workflows_owner_agent_slug_fkey", "agent_workflows", "agent_settings",
        ["owner_agent_slug"], ["slug"], ondelete="CASCADE",
    )

    for table in NOT_NULL:
        op.alter_column(table, "tenant_id", nullable=True)

    # ===== undo tenants + tenant_id =====
    for table in OWNED:
        op.drop_constraint(f"fk_{table}_tenant", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_tenant_id", table)
        op.drop_column(table, "tenant_id")
    op.drop_constraint("fk_llm_settings_tenant", "llm_settings", type_="foreignkey")
    op.drop_constraint("uq_llm_settings_tenant", "llm_settings", type_="unique")
    op.drop_column("llm_settings", "tenant_id")
    op.drop_table("tenants")

    # ===== drop base tables =====
    op.drop_column("agent_settings", "episodes_enabled")
    op.drop_column("agent_settings", "emotions_enabled")
    op.drop_column("agent_settings", "memory_enabled")
    op.drop_index("ix_agent_memories_user_category", table_name="agent_memories")
    op.drop_index("ix_agent_memories_user_agent", table_name="agent_memories")
    op.drop_table("agent_memories")
    op.drop_index("ix_agent_episodes_user_agent", table_name="agent_episodes")
    op.drop_table("agent_episodes")
    op.drop_table("agent_emotion_states")
    op.drop_table("agent_skills")
    op.drop_table("skills")
    op.drop_table("llm_settings")
    op.drop_table("token_budgets")
    op.drop_table("token_usage")
    op.drop_table("agent_eval_schedules")
    op.drop_table("agent_eval_results")
    op.drop_table("agent_eval_runs")
    op.drop_table("agent_eval_tests")
    op.drop_table("agent_eval_test_sets")
    op.drop_table("feedback_attachments")
    op.drop_index("ix_message_feedback_user_id", table_name="message_feedback")
    op.drop_index("ix_message_feedback_conversation_id", table_name="message_feedback")
    op.drop_index("ix_message_feedback_message_id", table_name="message_feedback")
    op.drop_table("message_feedback")
    op.drop_index("ix_conversations_folder_id", table_name="conversations")
    op.drop_column("conversations", "folder_id")
    op.drop_index("ix_conversation_folders_user_id", table_name="conversation_folders")
    op.drop_table("conversation_folders")
    op.drop_index("ix_agent_workflows_owner_agent_slug", table_name="agent_workflows")
    op.drop_table("agent_workflows")
    op.drop_constraint("fk_chat_attachments_message", "chat_attachments", type_="foreignkey")
    op.drop_index("ix_chat_attachments_message_id", table_name="chat_attachments")
    op.drop_index("ix_chat_attachments_user_id", table_name="chat_attachments")
    op.drop_index("ix_chat_attachments_conversation_id", table_name="chat_attachments")
    op.drop_table("chat_attachments")
    op.drop_constraint("fk_upload_settings_connector", "upload_settings", type_="foreignkey")
    op.drop_table("upload_settings")
    op.drop_table("knowledge_sources")
    op.execute("DROP TYPE IF EXISTS knowledge_source_status")
    op.execute("DROP TYPE IF EXISTS knowledge_source_type")
    op.drop_table("connectors")
    op.execute("DROP TYPE IF EXISTS connector_type")
    op.drop_table("secrets")
    op.execute("DROP TYPE IF EXISTS secret_type")
    op.drop_constraint("fk_agent_settings_published_version", "agent_settings", type_="foreignkey")
    op.drop_index("ix_agent_versions_version_number", table_name="agent_versions")
    op.drop_index("ix_agent_versions_agent_settings_id", table_name="agent_versions")
    op.drop_table("agent_versions")
    op.execute("DROP TRIGGER IF EXISTS trg_agent_settings_updated_at ON agent_settings")
    op.execute("DROP FUNCTION IF EXISTS agent_settings_set_updated_at()")
    op.drop_table("agent_settings")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_conversations_user_id", table_name="conversations")
    op.drop_table("conversations")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

