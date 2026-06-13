"""Admin agent settings API."""

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.agents.context import MODEL_CONTEXT_WINDOWS
from app.api.deps import AdminUser, DbSession
from app.models import AgentSettings
from app.schemas.agent_settings import AgentSettingCreate, AgentSettingOut, AgentSettingUpdate

router = APIRouter(prefix="/admin/agents", tags=["admin"])

@router.get("/models", response_model=list[str])
async def list_models(user: AdminUser) -> list[str]:
    """Return available LLM model names."""
    models = [k for k in MODEL_CONTEXT_WINDOWS.keys() if k != "default"]

    if "gpt-5.4-nano" in models:
        models.remove("gpt-5.4-nano")
        models.insert(0, "gpt-5.4-nano")
    return models

@router.get("", response_model=list[AgentSettingOut])
async def list_agent_settings(user: AdminUser, db: DbSession) -> list[AgentSettingOut]:
    """
    List all agent settings.

    Args:
        user: Admin user
        db: Database session

    Returns:
        List of agent settings
    """
    result = await db.scalars(select(AgentSettings).order_by(AgentSettings.slug))
    rows = result.all()
    return [AgentSettingOut.model_validate(r) for r in rows]


@router.get("/{slug}", response_model=AgentSettingOut)
async def get_agent_setting(slug: str, user: AdminUser, db: DbSession) -> AgentSettingOut:
    """
    Get a single agent setting.
    
    Args:
        slug: Agent slug
        user: Admin user
        db: Database session
        
    Returns:
        Agent setting
    """
    row = await db.scalar(select(AgentSettings).where(AgentSettings.slug == slug))
    if row is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentSettingOut.model_validate(row)


@router.post("", response_model=AgentSettingOut, status_code=201)
async def create_agent_setting(
    user: AdminUser,
    db: DbSession,
    request: Request,
    body: AgentSettingCreate,
) -> AgentSettingOut:
    """
    Create a new agent setting.

    Args:
        user: Admin user
        db: Database session
        request: FastAPI request to access runtime
        body: Agent setting creation data

    Returns:
        Created agent setting

    Raises:
        HTTPException: If slug already exists
    """
    existing = await db.scalar(select(AgentSettings).where(AgentSettings.slug == body.slug))
    if existing:
        raise HTTPException(status_code=409, detail="Agent slug already exists")
    row = AgentSettings(**body.model_dump(exclude_unset=True))
    db.add(row)
    await db.commit()
    await db.refresh(row)

    runtime = getattr(request.app.state, "runtime", None)
    if runtime:
        await runtime.refresh_graph()

    return AgentSettingOut.model_validate(row)


@router.put("/{slug}", response_model=AgentSettingOut)
async def update_agent_setting(
    slug: str,
    user: AdminUser,
    db: DbSession,
    request: Request,
    body: AgentSettingUpdate,
) -> AgentSettingOut:
    """
    Update agent settings.

    Args:
        slug: Agent slug
        user: Admin user
        db: Database session
        request: FastAPI request to access runtime
        body: Agent setting update data

    Returns:
        Updated agent setting
    """
    row = await db.scalar(select(AgentSettings).where(AgentSettings.slug == slug))
    if row is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    await db.commit()
    await db.refresh(row)

    runtime = getattr(request.app.state, "runtime", None)
    if runtime:
        await runtime.refresh_graph()

    return AgentSettingOut.model_validate(row)


@router.delete("/{slug}", status_code=204)
async def delete_agent_setting(
    slug: str,
    user: AdminUser,
    db: DbSession,
    request: Request,
) -> None:
    """
    Delete an agent setting.

    Args:
        slug: Agent slug
        user: Admin user
        db: Database session
        request: FastAPI request to access runtime

    Raises:
        HTTPException: If agent not found
    """
    row = await db.scalar(select(AgentSettings).where(AgentSettings.slug == slug))
    if row is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    await db.delete(row)
    await db.commit()

    runtime = getattr(request.app.state, "runtime", None)
    if runtime:
        await runtime.refresh_graph()
