from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class ModelOption(BaseModel):
    """A selectable LLM model option with provider metadata."""
    name: str
    provider: str
    label: str


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
    is_orchestrator: bool
    is_router: bool
    routes_to: list[str] | None
    mode_profile: dict[str, Any] | None
    visibility: str
    created_by: str | None
    allow_uploads: bool
    allowed_users: list[str] | None
    beta_users: list[str] | None
    agent_type: str = "standard"
    research_config: dict[str, Any] | None = None
    memory_enabled: bool = False
    emotions_enabled: bool = False
    episodes_enabled: bool = False
    created_at: datetime
    updated_at: datetime
    draft_config: dict[str, Any] | None = None
    is_published: bool = False
    published_at: datetime | None = None
    published_version_id: UUID | None = None

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
    is_orchestrator: bool = False
    is_router: bool = False
    routes_to: list[str] | None = None
    mode_profile: dict[str, Any] | None = None
    visibility: str | None = "all"
    created_by: str | None = None
    allow_uploads: bool = True
    allowed_users: list[str] | None = None
    beta_users: list[str] | None = None
    agent_type: str = "standard"
    research_config: dict[str, Any] | None = None
    memory_enabled: bool = False
    emotions_enabled: bool = False
    episodes_enabled: bool = False


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
    is_orchestrator: bool = False
    is_router: bool = False
    routes_to: list[str] | None = None
    mode_profile: dict[str, Any] | None = None
    visibility: str | None = "all"
    created_by: str | None = None
    allow_uploads: bool = True
    allowed_users: list[str] | None = None
    beta_users: list[str] | None = None
    agent_type: str = "standard"
    research_config: dict[str, Any] | None = None
    memory_enabled: bool = False
    emotions_enabled: bool = False
    episodes_enabled: bool = False


class AgentVersionOut(BaseModel):
    """
    Agent version output schema.

    Represents an immutable published snapshot of an agent configuration.
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    agent_settings_id: UUID
    version_number: int
    notes: str | None
    created_by: str | None
    created_at: datetime


class AgentPublishRequest(BaseModel):
    """Request body for publishing an agent draft."""
    notes: str | None = None


class AgentDraftSave(BaseModel):
    """
    Agent draft save schema.

    Same fields as AgentSettingUpdate but all optional for partial auto-save.
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
    is_orchestrator: bool = False
    is_router: bool = False
    routes_to: list[str] | None = None
    mode_profile: dict[str, Any] | None = None
    visibility: str | None = "all"
    created_by: str | None = None
    allow_uploads: bool = True
    allowed_users: list[str] | None = None
    beta_users: list[str] | None = None
    agent_type: str = "standard"
    research_config: dict[str, Any] | None = None
    memory_enabled: bool = False
    emotions_enabled: bool = False
    episodes_enabled: bool = False


class AgentTemplateOut(BaseModel):
    """Lightweight template metadata for gallery listing."""

    id: str
    name: str
    description: str | None
    tags: list[str] = []

    model_config = ConfigDict(from_attributes=True)


class AgentTemplateDetailOut(BaseModel):
    """Full template payload for preview / deploy."""

    id: str
    name: str
    description: str | None
    tags: list[str] = []
    agent_config: dict[str, Any]
    workflows: list[dict[str, Any]] = []

    model_config = ConfigDict(from_attributes=True)


class AgentTemplateDeployRequest(BaseModel):
    """Override fields when deploying a template."""

    slug: str
    name: str | None = None
    description: str | None = None
