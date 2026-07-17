import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AgentEvalTest(Base):
    """A single test case (question + expected answer) within a test set."""
    __tablename__ = "agent_eval_tests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    test_set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_eval_test_sets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    expected_answer: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    test_set: Mapped["AgentEvalTestSet"] = relationship("AgentEvalTestSet", back_populates="tests")
    results: Mapped[list["AgentEvalResult"]] = relationship(
        "AgentEvalResult", back_populates="test", cascade="all, delete-orphan"
    )
