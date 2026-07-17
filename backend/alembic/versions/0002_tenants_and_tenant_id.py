"""tenants table, tenant_id columns, tenant-zero backfill

Revision ID: 0002_tenants_and_tenant_id
Revises: 0001
"""
import uuid

import sqlalchemy as sa
from alembic import op

from app.core.config import settings

revision = "0002_tenants_and_tenant_id"
down_revision = "0001"
branch_labels = None
depends_on = None

DEFAULT_TENANT_ID = settings.default_tenant_id

OWNED = [
    "users", "agent_settings", "agent_versions", "agent_workflows", "agent_skills",
    "skills", "agent_memories", "agent_emotion_states", "agent_episodes",
    "agent_eval_tests", "agent_eval_test_sets", "agent_eval_runs", "agent_eval_results",
    "agent_eval_schedules", "conversations", "conversation_folders", "messages",
    "chat_attachments", "message_feedback", "feedback_attachments", "connectors",
    "secrets", "knowledge_sources", "token_usage", "token_budgets", "upload_settings",
]


def upgrade() -> None:
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

    # llm_settings.tenant_id (unique — one settings row per tenant)
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


def downgrade() -> None:
    for table in OWNED:
        op.drop_constraint(f"fk_{table}_tenant", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_tenant_id", table)
        op.drop_column(table, "tenant_id")
    op.drop_constraint("fk_llm_settings_tenant", "llm_settings", type_="foreignkey")
    op.drop_constraint("uq_llm_settings_tenant", "llm_settings", type_="unique")
    op.drop_column("llm_settings", "tenant_id")
    op.drop_table("tenants")
