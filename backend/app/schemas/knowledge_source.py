from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class KnowledgeSourceCreate(BaseModel):
    """
    Knowledge source create schema.
    
    This schema represents the knowledge source create data that can be sent
    by clients, including:
    - Knowledge source slug
    - Knowledge source name
    - Knowledge source type
    - Knowledge source configuration
    - Knowledge source connector ID
    """
    slug: str
    name: str
    source_type: str
    config: dict[str, Any] | None = None
    connector_id: UUID | None = None


class KnowledgeSourceOut(BaseModel):
    """
    Knowledge source output schema.
    
    This schema represents the knowledge source data that can be returned to clients,
    including:
    - Knowledge source ID
    - Knowledge source slug
    - Knowledge source name
    - Knowledge source type
    - Knowledge source configuration
    - Knowledge source status
    - Knowledge source last sync timestamp
    - Knowledge source chunk count
    - Knowledge source connector ID
    - Knowledge source creation timestamp
    """
    id: UUID
    slug: str
    name: str
    source_type: str
    config: dict[str, Any] | None
    status: str
    last_sync_at: datetime | None
    chunk_count: int
    connector_id: UUID | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

