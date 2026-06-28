from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SkillCreate(BaseModel):
    name: str
    description: str
    content: str = ""
    scope: str = "shared"
    agent_slug: str | None = None
    is_enabled: bool = True


class SkillUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    content: str | None = None
    is_enabled: bool | None = None


class SkillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str
    content: str
    scope: str
    agent_slug: str | None
    is_enabled: bool
    created_by: str | None
    created_at: datetime
    updated_at: datetime


class AgentSkillAssign(BaseModel):
    skill_id: UUID


class AgentSkillBatchUpdate(BaseModel):
    assign: list[UUID] = []
    unassign: list[UUID] = []
