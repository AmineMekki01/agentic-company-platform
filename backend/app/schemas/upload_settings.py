from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UploadSettingsOut(BaseModel):
    """Upload settings read schema."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    enabled: bool
    s3_connector_id: UUID | None
    s3_bucket: str
    s3_base_prefix: str
    retention_days: int
    max_file_size_mb: int
    encryption: str


class UploadSettingsUpdate(BaseModel):
    """Upload settings write schema."""

    enabled: bool = False
    s3_connector_id: UUID | None = None
    s3_bucket: str = Field(default="", max_length=255)
    s3_base_prefix: str = Field(default="uploads/", max_length=500)
    retention_days: int = Field(default=30, ge=0, le=365)
    max_file_size_mb: int = Field(default=50, ge=1, le=500)
    encryption: str = Field(default="AES256", pattern="^(AES256|aws:kms)$")
