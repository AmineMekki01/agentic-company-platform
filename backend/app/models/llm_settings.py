import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LLMSettings(Base):
    """
    Global configuration for LLM providers.

    Single-row table editable by admins. Controls:
    - Whether Ollama (local) models are enabled
    - The Ollama server URL
    - Which installed Ollama models are selectable by agents
    """
    __tablename__ = "llm_settings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    ollama_enabled: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default="0"
    )
    ollama_base_url: Mapped[str] = mapped_column(
        String(500), nullable=False, server_default="http://ollama:11434/v1"
    )
    ollama_enabled_models: Mapped[list[str]] = mapped_column(
        JSON(), nullable=False, server_default="[]"
    )

    # How much of this tenant's LLM traffic is captured in Langfuse traces : full, masked, off, this for compliance
    tracing_mode: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="full"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
