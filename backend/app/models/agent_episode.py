import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentEpisode(Base):
    """Significant interaction snapshots with emotion snapshots."""

    __tablename__ = "agent_episodes"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    agent_slug: Mapped[str] = mapped_column(String(50), nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    emotion_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    significance_score: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.5")
    trigger: Mapped[str] = mapped_column(String(50), nullable=False, server_default="high_emotion")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
