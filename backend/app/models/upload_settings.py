import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UploadSettings(Base):
    """
    Global configuration for chat file uploads.

    Single-row table editable by admins. Controls:
    - Whether uploads are enabled
    - S3 destination (bucket + prefix) via a Connector reference
    - Retention policy, size limits, encryption
    """
    __tablename__ = "upload_settings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    enabled: Mapped[bool] = mapped_column(nullable=False, server_default="0")

    s3_connector_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("connectors.id", ondelete="SET NULL"), nullable=True
    )

    s3_bucket: Mapped[str] = mapped_column(String(255), nullable=False, server_default="")
    s3_base_prefix: Mapped[str] = mapped_column(
        String(500), nullable=False, server_default="uploads/"
    )

    retention_days: Mapped[int] = mapped_column(nullable=False, server_default="30")
    max_file_size_mb: Mapped[int] = mapped_column(nullable=False, server_default="50")

    encryption: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="AES256"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    connector: Mapped["Connector"] = relationship("Connector")
