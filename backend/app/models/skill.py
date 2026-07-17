import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, ForeignKeyConstraint, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Skill(Base):
    __tablename__ = "skills"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "agent_slug"],
            ["agent_settings.tenant_id", "agent_settings.slug"],
            ondelete="CASCADE",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text(), nullable=False)
    content: Mapped[str] = mapped_column(Text(), nullable=False, server_default="")
    scope: Mapped[str] = mapped_column(String(20), nullable=False, server_default="shared")
    agent_slug: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean(), nullable=False, server_default="1")
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
