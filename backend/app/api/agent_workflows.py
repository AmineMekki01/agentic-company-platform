"""Agent workflow API."""

import uuid

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.api.deps import AdminUser, DbSession
from app.models import AgentSettings, AgentWorkflow
from app.schemas.agent_workflow import AgentWorkflowCreate, AgentWorkflowOut, AgentWorkflowUpdate

router = APIRouter(prefix="/admin/agents", tags=["admin"])


@router.get("/{slug}/workflows", response_model=list[AgentWorkflowOut])
async def list_agent_workflows(slug: str, user: AdminUser, db: DbSession) -> list[AgentWorkflowOut]:
    """List workflows owned by an agent."""
    result = await db.scalars(
        select(AgentWorkflow)
        .where(AgentWorkflow.owner_agent_slug == slug)
        .order_by(AgentWorkflow.created_at)
    )
    return [AgentWorkflowOut.model_validate(w) for w in result.all()]


@router.post("/{slug}/workflows", response_model=AgentWorkflowOut, status_code=201)
async def create_agent_workflow(
    slug: str,
    user: AdminUser,
    db: DbSession,
    request: Request,
    body: AgentWorkflowCreate,
) -> AgentWorkflowOut:
    """Create a workflow for an agent."""
    agent = await db.scalar(select(AgentSettings).where(AgentSettings.slug == slug))
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    row = AgentWorkflow(
        owner_agent_slug=slug,
        name=body.name,
        description=body.description,
        enabled=body.enabled,
        definition=body.definition.model_dump(),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    runtime = getattr(request.app.state, "runtime", None)
    if runtime:
        await runtime.refresh_graph()

    return AgentWorkflowOut.model_validate(row)


@router.get("/{slug}/workflows/{workflow_id}", response_model=AgentWorkflowOut)
async def get_agent_workflow(
    slug: str,
    workflow_id: uuid.UUID,
    user: AdminUser,
    db: DbSession,
) -> AgentWorkflowOut:
    """Get a single workflow."""
    row = await db.scalar(
        select(AgentWorkflow).where(
            AgentWorkflow.id == workflow_id,
            AgentWorkflow.owner_agent_slug == slug,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return AgentWorkflowOut.model_validate(row)


@router.put("/{slug}/workflows/{workflow_id}", response_model=AgentWorkflowOut)
async def update_agent_workflow(
    slug: str,
    workflow_id: uuid.UUID,
    user: AdminUser,
    db: DbSession,
    request: Request,
    body: AgentWorkflowUpdate,
) -> AgentWorkflowOut:
    """Update a workflow."""
    row = await db.scalar(
        select(AgentWorkflow).where(
            AgentWorkflow.id == workflow_id,
            AgentWorkflow.owner_agent_slug == slug,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    data = body.model_dump(exclude_unset=True)
    if "definition" in data:
        data["definition"] = data["definition"].model_dump()
    for key, value in data.items():
        setattr(row, key, value)
    await db.commit()
    await db.refresh(row)

    runtime = getattr(request.app.state, "runtime", None)
    if runtime:
        await runtime.refresh_graph()

    return AgentWorkflowOut.model_validate(row)


@router.delete("/{slug}/workflows/{workflow_id}", status_code=204)
async def delete_agent_workflow(
    slug: str,
    workflow_id: uuid.UUID,
    user: AdminUser,
    db: DbSession,
    request: Request,
) -> None:
    """Delete a workflow."""
    row = await db.scalar(
        select(AgentWorkflow).where(
            AgentWorkflow.id == workflow_id,
            AgentWorkflow.owner_agent_slug == slug,
        )
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    await db.delete(row)
    await db.commit()

    runtime = getattr(request.app.state, "runtime", None)
    if runtime:
        await runtime.refresh_graph()
