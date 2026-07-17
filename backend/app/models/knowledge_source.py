import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class KnowledgeSource(Base):
    """
    Knowledge source model for document ingestion
    
    This model stores configuration for knowledge sources that can be used by agents,
    including:
    - Source type (notion, s3)
    - Configuration settings
    - Sync status
    - Connection to external connectors
    """
    __tablename__ = "knowledge_sources"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_knowledge_sources_tenant_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[str] = mapped_column(
        Enum("notion", "s3", "gdrive", name="knowledge_source_type"),
        nullable=False,
    )
    config: Mapped[dict[str, Any] | None] = mapped_column(
        JSON(), nullable=True, server_default="{}"
    )
    status: Mapped[str] = mapped_column(
        Enum("pending", "syncing", "ready", "error", name="knowledge_source_status"),
        nullable=False,
        default="pending",
    )
    last_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    chunk_count: Mapped[int] = mapped_column(nullable=False, default=0)
    connector_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("connectors.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    connector: Mapped["Connector"] = relationship("Connector")
