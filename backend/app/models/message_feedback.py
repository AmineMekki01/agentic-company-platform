import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MessageFeedback(Base):
    """
    User feedback on an AI assistant message.

    Stores thumbs up/down ratings, optional comments and screenshots,
    plus a full snapshot of the conversation and tool context at the
    time feedback was submitted. This data can later be used to improve
    retrieval ranking or fine-tune models.
    """
    __tablename__ = "message_feedback"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    thumbs_up: Mapped[bool] = mapped_column(nullable=False, index=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    screenshot_attachment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("feedback_attachments.id", ondelete="SET NULL"), nullable=True
    )
    conversation_snapshot: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True
    )
    tool_calls_log: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True
    )
    retrieved_sources: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True
    )
    conversation_actions: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    message: Mapped["Message"] = relationship("Message", back_populates="feedback")
    user: Mapped["User"] = relationship("User")
    screenshot: Mapped["FeedbackAttachment | None"] = relationship(
        "FeedbackAttachment", uselist=False, foreign_keys=[screenshot_attachment_id]
    )
