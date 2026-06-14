"""Admin agent settings API."""

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select, text

from app.agents.context import MODEL_CONTEXT_WINDOWS
from app.api.deps import AdminUser, DbSession
from app.models import AgentSettings
from app.schemas.agent_settings import AgentSettingCreate, AgentSettingOut, AgentSettingUpdate

router = APIRouter(prefix="/admin/agents", tags=["admin"])

_AGENT_SETTING_COLUMNS = """
SELECT id, slug, name, description, llm_model, system_prompt, retrieval_top_k,
       retrieval_enabled, web_search_enabled, connected_sources, tools, is_orchestrator,
       routes_to, mode_profile, visibility, created_by, allowed_users, created_at, updated_at
FROM agent_settings
"""


async def _fetch_agent_settings(db: DbSession, slug: str | None = None) -> list[dict]:
    query = _AGENT_SETTING_COLUMNS
    params: dict[str, str] = {}
    if slug is not None:
        query += " WHERE slug = :slug"
        params["slug"] = slug
    else:
        query += " ORDER BY slug"
    result = await db.execute(text(query), params)
    return list(result.mappings().all())

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
    rows = await _fetch_agent_settings(db)
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
    rows = await _fetch_agent_settings(db, slug=slug)
    if not rows:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentSettingOut.model_validate(rows[0])


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
    data = body.model_dump(exclude_unset=True)
    data["retrieval_enabled"] = bool(data.get("connected_sources"))
    data["created_by"] = (data.get("created_by") or user.email).strip().lower()
    if data.get("visibility") == "restricted":
        allowed_users = [str(email).strip().lower() for email in (data.get("allowed_users") or []) if str(email).strip()]
        if data["created_by"] not in allowed_users:
            allowed_users.insert(0, data["created_by"])
        data["allowed_users"] = allowed_users
    row = AgentSettings(**data)
    db.add(row)
    await db.commit()
    await db.refresh(row)

    runtime = getattr(request.app.state, "runtime", None)
    if runtime:
        await runtime.refresh_graph()

    created = await _fetch_agent_settings(db, slug=body.slug)
    if not created:
        raise HTTPException(status_code=500, detail="Failed to load created agent")
    return AgentSettingOut.model_validate(created[0])


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
    data = body.model_dump(exclude_unset=True)

    if "connected_sources" in data:
        data["retrieval_enabled"] = bool(data["connected_sources"])
    if "created_by" in data and data["created_by"] is not None:
        data["created_by"] = data["created_by"].strip().lower()
    final_visibility = data.get("visibility", row.visibility)
    final_owner = data.get("created_by") or row.created_by or user.email
    if final_visibility == "restricted":
        allowed_users = [str(email).strip().lower() for email in (data.get("allowed_users") or row.allowed_users or []) if str(email).strip()]
        final_owner = final_owner.strip().lower()
        if final_owner not in allowed_users:
            allowed_users.insert(0, final_owner)
        data["allowed_users"] = allowed_users
    for key, value in data.items():
        setattr(row, key, value)
    await db.commit()
    await db.refresh(row)

    runtime = getattr(request.app.state, "runtime", None)
    if runtime:
        await runtime.refresh_graph()

    updated = await _fetch_agent_settings(db, slug=slug)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to load updated agent")
    return AgentSettingOut.model_validate(updated[0])


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
