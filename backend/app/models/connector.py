import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Connector(Base):
    """
    Named external connector that references a reusable Secret for credentials.

    Connector types:
    - Notion
    - S3
    - Jira
    - Google Drive
    """
    __tablename__ = "connectors"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    connector_type: Mapped[str] = mapped_column(
        Enum("notion", "s3", "jira", "gdrive", name="connector_type"),
        nullable=False,
    )
    secret_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("secrets.id"), nullable=True
    )
    config: Mapped[dict[str, Any] | None] = mapped_column(JSON(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    secret: Mapped["Secret"] = relationship(lazy="selectin")

    @property
    def secret_name(self) -> str | None:
        return self.secret.name if self.secret else None
