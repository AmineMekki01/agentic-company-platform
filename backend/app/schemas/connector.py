from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ConnectorCreate(BaseModel):
    """
    Connector create schema.
    
    This schema represents the connector create data that can be sent
    by clients, including:
    - Connector slug
    - Connector name
    - Connector type
    - Connector credentials
    """
    slug: str
    name: str
    connector_type: str
    credentials: dict[str, Any]


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
