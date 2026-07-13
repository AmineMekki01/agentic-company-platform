from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ConnectorCreate(BaseModel):
    """
    Connector create schema.

    Connectors reference a Secret for credentials rather than storing their
    own - `secret_id` must point to a Secret whose secret_type matches
    connector_type.
    """
    slug: str
    name: str
    connector_type: str
    secret_id: UUID
    config: dict[str, Any] | None = None


class ConnectorUpdate(BaseModel):
    """Partial update - rename, re-point to a different secret, or change config."""
    name: str | None = None
    secret_id: UUID | None = None
    config: dict[str, Any] | None = None


class ConnectorOut(BaseModel):
    """
    Connector output schema.

    This schema represents the connector data that can be returned to clients,
    including:
    - Connector ID
    - Connector slug
    - Connector name
    - Connector type
    - Connector creation timestamp
    """
    id: UUID
    slug: str
    name: str
    connector_type: str
    secret_id: UUID | None
    secret_name: str | None = None
    config: dict[str, Any] | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotionResource(BaseModel):
    """
    Notion resource schema.
    
    This schema represents a Notion resource (database or page) that can be
    returned to clients, including:
    - Resource ID
    - Resource name
    - Resource type
    - Resource URL
    """
    id: str
    name: str
    type: str
    url: str | None = None


class S3Bucket(BaseModel):
    """
    S3 bucket schema.
    
    This schema represents an S3 bucket that can be returned to clients,
    including:
    - Bucket name
    - Bucket creation date
    """
    name: str
    created_at: datetime | None = None


class GDriveResource(BaseModel):
    """
    Google Drive resource schema.
    
    This schema represents a Google Drive resource (folder or file) that can be
    returned to clients, including:
    - Resource ID
    - Resource name
    - Resource type (folder or file)
    - MIME type
    - Resource URL
    """
    id: str
    name: str
    type: str
    mime_type: str | None = None
    url: str | None = None
