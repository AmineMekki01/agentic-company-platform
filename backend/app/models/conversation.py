import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Conversation(Base):
    """
    Chat conversation model.
    
    This model stores conversation metadata for each user, including:
    - Conversation title
    - User association
    - Optional folder for organization
    - Creation and update timestamps
    """
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    folder_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversation_folders.id", ondelete="SET NULL"), index=True, nullable=True
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    entry_agent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    folder: Mapped["ConversationFolder"] = relationship(
        "ConversationFolder", back_populates="conversations"
    )
