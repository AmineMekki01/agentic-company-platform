import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Secret(Base):
    """
    Reusable, typed credential record referenced by one or more Connectors.

    Credentials are stored as Fernet-encrypted JSON. Sensitive fields (per
    app.services.secret_schemas.SECRET_TYPE_SCHEMAS) are never returned to
    clients once saved - only non-sensitive fields are revealed on read.
    """
    __tablename__ = "secrets"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    secret_type: Mapped[str] = mapped_column(
        Enum("s3", "gdrive", "notion", "jira", "custom", name="secret_type"),
        nullable=False,
    )
    credentials_encrypted: Mapped[str] = mapped_column(Text(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
