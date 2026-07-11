import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AgentEmotionState(Base):
    """Per-user-per-agent emotional state (8 Plutchik dimensions + baselines)."""

    __tablename__ = "agent_emotion_states"
    __table_args__ = (
        UniqueConstraint("user_id", "agent_slug", name="uq_emotion_user_agent"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    agent_slug: Mapped[str] = mapped_column(String(50), nullable=False)

    joy: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.3", default=0.3)
    trust: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.3", default=0.3)
    fear: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.1", default=0.1)
    surprise: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.1", default=0.1)
    sadness: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.1", default=0.1)
    disgust: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.1", default=0.1)
    anger: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.1", default=0.1)
    anticipation: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.3", default=0.3)

    joy_baseline: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.3", default=0.3)
    trust_baseline: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.3", default=0.3)
    fear_baseline: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.1", default=0.1)
    surprise_baseline: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.1", default=0.1)
    sadness_baseline: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.1", default=0.1)
    disgust_baseline: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.1", default=0.1)
    anger_baseline: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.1", default=0.1)
    anticipation_baseline: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.3", default=0.3)

    last_interaction_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
