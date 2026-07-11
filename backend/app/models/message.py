import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Message(Base):
    """
    Chat message model.

    This model stores individual messages in conversations, including:
    - Message content
    - Message role (user, assistant, system)
    - Agent association
    - Citations and references
    """
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    agent_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    citations: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    tool_calls_log: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    trace_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )

    attachments: Mapped[list["ChatAttachment"]] = relationship(
        "ChatAttachment",
        back_populates="message",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    feedback: Mapped[list["MessageFeedback"]] = relationship(
        "MessageFeedback",
        back_populates="message",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
