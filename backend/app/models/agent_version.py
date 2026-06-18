import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Text, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AgentVersion(Base):
    """
    Immutable snapshot of an agent's configuration at publish time.

    Each time an admin publishes an agent, a new version is created
    from the live config. Versions support rollback and audit history.
    """
    __tablename__ = "agent_versions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_settings_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_settings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer(), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSON(), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    agent: Mapped["AgentSettings"] = relationship(
        back_populates="versions",
        foreign_keys="AgentVersion.agent_settings_id",
    )
