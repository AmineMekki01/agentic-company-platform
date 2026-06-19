import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AgentEvalTest(Base):
    """A single test case for agent evaluation."""
    __tablename__ = "agent_eval_tests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_settings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_answer: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)

    agent: Mapped["AgentSettings"] = relationship("AgentSettings")
    results: Mapped[list["AgentEvalResult"]] = relationship(
        "AgentEvalResult", back_populates="test", cascade="all, delete-orphan"
    )
