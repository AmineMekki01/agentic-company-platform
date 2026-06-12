from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class AgentSettingOut(BaseModel):
    """
    Agent setting output schema.
    
    This schema represents the agent settings configuration that can be returned
    to clients, including:
    - Agent identifier
    - Configuration settings
    - Retrieval and search settings
    - Connected knowledge sources
    - Mode-specific profiles
    """
    id: UUID
    slug: str
    name: str | None
    description: str | None
    llm_model: str | None
    system_prompt: str | None
    retrieval_top_k: int
    retrieval_enabled: bool
    web_search_enabled: bool
    connected_sources: list[Any] | None
    tools: list[str] | None
    mode_profile: dict[str, Any] | None

    model_config = ConfigDict(from_attributes=True)


class AgentSettingUpdate(BaseModel):
    """
    Agent setting update schema.
    
    This schema represents the agent settings configuration that can be updated
    by clients, including:
    - Configuration settings
    - Retrieval and search settings
    - Connected knowledge sources
    - Mode-specific profiles
    """
    name: str | None = None
    description: str | None = None
    llm_model: str | None = None
    system_prompt: str | None = None
    retrieval_top_k: int = Field(default=5, ge=1, le=20)
    retrieval_enabled: bool = True
    web_search_enabled: bool = False
    connected_sources: list[str] | None = None
    tools: list[str] | None = None
    mode_profile: dict[str, Any] | None = None


class AgentSettingCreate(BaseModel):
    """
    Agent setting creation schema.

    This schema represents the agent settings configuration that can be created
    by admin users, including:
    - Required slug identifier
    - Optional initial configuration
    """
    slug: str
    name: str | None = None
    description: str | None = None
    llm_model: str | None = None
    system_prompt: str | None = None
    retrieval_top_k: int = Field(default=5, ge=1, le=20)
    retrieval_enabled: bool = True
    web_search_enabled: bool = False
    connected_sources: list[str] | None = None
    tools: list[str] | None = None
    mode_profile: dict[str, Any] | None = None
