from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SecretCreate(BaseModel):
    slug: str
    name: str
    secret_type: str
    credentials: dict[str, Any]


class SecretUpdate(BaseModel):
    """Partial update. `credentials`, if provided, is merged into the existing
    stored dict (only the keys present are overwritten) - lets an admin rotate
    a single field like api_token without resubmitting everything."""
    name: str | None = None
    credentials: dict[str, Any] | None = None


class SecretOut(BaseModel):
    """List/summary view - non-sensitive credential fields only, never raw ciphertext."""
    id: UUID
    slug: str
    name: str
    secret_type: str
    connector_count: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SecretDetailOut(SecretOut):
    """Single-secret view - includes non-sensitive credential fields for display on edit."""
    non_sensitive_credentials: dict[str, Any] = {}
