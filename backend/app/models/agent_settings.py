import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, JSON, DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AgentSettings(Base):
    """
    Per-agent runtime configuration model.
    
    This model stores configuration settings for each agent, including:
    - LLM model selection
    - System prompts
    - Retrieval settings
    - Web search settings
    - Connected knowledge sources
    - Mode-specific profiles
    - Draft/publish versioning support
    """
    __tablename__ = "agent_settings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_agent_settings_tenant_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(
        String(100), nullable=True, server_default="gpt-5.4-nano"
    )
    system_prompt: Mapped[str | None] = mapped_column(Text(), nullable=True)
    retrieval_top_k: Mapped[int] = mapped_column(nullable=False, server_default="5")
    retrieval_enabled: Mapped[bool] = mapped_column(nullable=False, server_default="1")
    web_search_enabled: Mapped[bool] = mapped_column(nullable=False, server_default="0")
    web_search_max_results: Mapped[int] = mapped_column(nullable=False, server_default="5")
    jira_tickets_limit: Mapped[int] = mapped_column(nullable=False, server_default="20")
    connected_sources: Mapped[list[Any] | None] = mapped_column(JSON(), nullable=True, server_default="[]")
    tools: Mapped[list[str] | None] = mapped_column(JSON(), nullable=True, server_default="[]")
    is_orchestrator: Mapped[bool] = mapped_column(nullable=False, server_default="0")
    is_router: Mapped[bool] = mapped_column(nullable=False, server_default="0")
    routes_to: Mapped[list[str] | None] = mapped_column(JSON(), nullable=True)
    mode_profile: Mapped[dict[str, Any] | None] = mapped_column(JSON(), nullable=True)
    visibility: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="all"
    )
    created_by: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    allow_uploads: Mapped[bool] = mapped_column(nullable=False, server_default="1")
    allowed_users: Mapped[list[str] | None] = mapped_column(
        JSON(), nullable=True, server_default="[]"
    )
    beta_users: Mapped[list[str] | None] = mapped_column(
        JSON(), nullable=True, server_default="[]"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    agent_type: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="standard"
    )
    research_config: Mapped[dict[str, Any] | None] = mapped_column(JSON(), nullable=True)
    draft_config: Mapped[dict[str, Any] | None] = mapped_column(JSON(), nullable=True)
    memory_enabled: Mapped[bool] = mapped_column(nullable=False, server_default="0")
    emotions_enabled: Mapped[bool] = mapped_column(nullable=False, server_default="0")
    episodes_enabled: Mapped[bool] = mapped_column(nullable=False, server_default="0")
    is_published: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default="0")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_versions.id", ondelete="SET NULL"), nullable=True
    )

    versions: Mapped[list["AgentVersion"]] = relationship(
        back_populates="agent",
        order_by="AgentVersion.version_number.desc()",
        lazy="selectin",
        foreign_keys="AgentVersion.agent_settings_id",
        cascade="all, delete-orphan",
    )