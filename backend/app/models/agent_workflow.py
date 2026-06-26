import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentWorkflow(Base):
    """
    Agent-to-agent workflow definition.

    Stores DAG-based workflows owned by a parent agent. When enabled, the
    parent agent's normal LLM execution is replaced by executing the
    workflow steps sequentially, invoking sub-agents with rendered prompts.
    """
    __tablename__ = "agent_workflows"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    owner_agent_slug: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    enabled: Mapped[bool] = mapped_column(nullable=False, server_default="0")
    definition: Mapped[dict[str, Any]] = mapped_column(JSON(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
