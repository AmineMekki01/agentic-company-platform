import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, String, func
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
    ollama_enabled: Mapped[bool] = mapped_column(
        Boolean(), nullable=False, server_default="0"
    )
    ollama_base_url: Mapped[str] = mapped_column(
        String(500), nullable=False, server_default="http://ollama:11434/v1"
    )
    ollama_enabled_models: Mapped[list[str]] = mapped_column(
        JSON(), nullable=False, server_default="[]"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
