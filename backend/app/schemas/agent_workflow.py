from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkflowPosition(BaseModel):
    """Canvas position for a workflow node."""

    x: float = 0
    y: float = 0


class WorkflowInput(BaseModel):
    """Declared input for a workflow node."""

    name: str
    source: str | None = None
    description: str | None = None


class WorkflowOutput(BaseModel):
    """Declared output for a workflow node."""

    name: str
    description: str | None = None


class WorkflowNode(BaseModel):
    """A single node in a workflow DAG."""
    id: str
    agent_slug: str
    label: str | None = None
    instructions: str | None = None
    inputs: list[WorkflowInput] = Field(default_factory=list)
    outputs: list[WorkflowOutput] = Field(default_factory=list)
    prompt_template: str | None = None
    output_var: str = "output"
    position: WorkflowPosition | None = None


class WorkflowEdge(BaseModel):
    """A directed edge between two workflow nodes."""
    id: str
    source: str
    target: str


class WorkflowDefinition(BaseModel):
    """The full workflow DAG definition."""
    input_schema: list[str]
    nodes: list[WorkflowNode]
    edges: list[WorkflowEdge]
    output: str


class AgentWorkflowOut(BaseModel):
    """Agent workflow response schema."""
    id: UUID
    owner_agent_slug: str
    name: str
    description: str | None
    enabled: bool
    definition: WorkflowDefinition
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentWorkflowCreate(BaseModel):
    """Agent workflow creation schema."""
    name: str
    description: str | None = None
    enabled: bool = False
    definition: WorkflowDefinition


class AgentWorkflowUpdate(BaseModel):
    """Agent workflow update schema."""
    name: str | None = None
    description: str | None = None
    enabled: bool | None = None
    definition: WorkflowDefinition | None = None
