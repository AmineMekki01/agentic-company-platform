"""Admin agent settings API."""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select, text

from app.agents.context import MODEL_CONTEXT_WINDOWS
from app.api.deps import AdminUser, DbSession
from app.models import AgentSettings, AgentVersion
from app.schemas.agent_settings import (
    AgentDraftSave,
    AgentPublishRequest,
    AgentSettingCreate,
    AgentSettingOut,
    AgentSettingUpdate,
    AgentVersionOut,
)

router = APIRouter(prefix="/admin/agents", tags=["admin"])

_AGENT_SETTING_COLUMNS = """
SELECT id, slug, name, description, llm_model, system_prompt, retrieval_top_k,
       retrieval_enabled, web_search_enabled, connected_sources, tools, is_orchestrator, is_router,
       routes_to, mode_profile, visibility, created_by, allow_uploads, allowed_users, beta_users,
       created_at, updated_at, draft_config, is_published, published_at, published_version_id
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

    If the agent is published, changes are saved to draft_config only.
    If unpublished, changes go directly to live fields.

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

    live_fields = {"beta_users", "visibility", "allowed_users"}
    live_data = {k: v for k, v in data.items() if k in live_fields}
    draft_data = {k: v for k, v in data.items() if k not in live_fields}

    for key, value in live_data.items():
        setattr(row, key, value)

    if row.is_published and draft_data:
        existing_draft = dict(row.draft_config or {})
        existing_draft.update(draft_data)
        row.draft_config = existing_draft
    elif not row.is_published:
        for key, value in draft_data.items():
            setattr(row, key, value)

    await db.commit()
    await db.refresh(row)

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


async def _next_version_number(db: DbSession, agent_id: str) -> int:
    result = await db.scalar(
        select(func.max(AgentVersion.version_number)).where(
            AgentVersion.agent_settings_id == agent_id
        )
    )
    return (result or 0) + 1


@router.get("/{slug}/versions", response_model=list[AgentVersionOut])
async def list_agent_versions(
    slug: str, user: AdminUser, db: DbSession
) -> list[AgentVersionOut]:
    """List version history for an agent (newest first)."""
    row = await db.scalar(select(AgentSettings).where(AgentSettings.slug == slug))
    if row is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    result = await db.scalars(
        select(AgentVersion)
        .where(AgentVersion.agent_settings_id == row.id)
        .order_by(AgentVersion.version_number.desc())
    )
    return [AgentVersionOut.model_validate(v) for v in result.all()]


@router.post("/{slug}/draft", response_model=AgentSettingOut)
async def save_agent_draft(
    slug: str,
    user: AdminUser,
    db: DbSession,
    body: AgentDraftSave,
) -> AgentSettingOut:
    """Auto-save draft configuration for a published agent."""
    row = await db.scalar(select(AgentSettings).where(AgentSettings.slug == slug))
    if row is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    data = body.model_dump(exclude_unset=True)
    if "connected_sources" in data:
        data["retrieval_enabled"] = bool(data["connected_sources"])
    if "created_by" in data and data["created_by"] is not None:
        data["created_by"] = data["created_by"].strip().lower()

    # Merge incoming data with existing draft
    existing_draft = dict(row.draft_config or {})
    existing_draft.update(data)

    # Only keep fields that differ from live values (prevent phantom drafts)
    filtered_draft: dict[str, Any] = {}
    for key, value in existing_draft.items():
        if key in ("draft_config", "is_published", "published_at", "published_version_id"):
            continue
        if hasattr(row, key):
            live_value = getattr(row, key)
            # Normalize for comparison (lists/None)
            if live_value is None and (value is None or value == []):
                continue
            if live_value == value:
                continue
        filtered_draft[key] = value

    row.draft_config = filtered_draft if filtered_draft else None
    await db.commit()
    await db.refresh(row)

    updated = await _fetch_agent_settings(db, slug=slug)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to load updated agent")
    return AgentSettingOut.model_validate(updated[0])


@router.post("/{slug}/publish", response_model=AgentSettingOut)
async def publish_agent(
    slug: str,
    user: AdminUser,
    db: DbSession,
    request: Request,
    body: AgentPublishRequest,
) -> AgentSettingOut:
    """
    Publish an agent.

    - Snapshots current live config as a new version.
    - If draft exists, copies draft to live fields.
    - Sets is_published = true.
    """
    row = await db.scalar(select(AgentSettings).where(AgentSettings.slug == slug))
    if row is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    live_config = {
        "name": row.name,
        "description": row.description,
        "llm_model": row.llm_model,
        "system_prompt": row.system_prompt,
        "retrieval_top_k": row.retrieval_top_k,
        "retrieval_enabled": row.retrieval_enabled,
        "web_search_enabled": row.web_search_enabled,
        "connected_sources": row.connected_sources,
        "tools": row.tools,
        "is_orchestrator": row.is_orchestrator,
        "routes_to": row.routes_to,
        "mode_profile": row.mode_profile,
        "visibility": row.visibility,
        "created_by": row.created_by,
        "allow_uploads": row.allow_uploads,
        "allowed_users": row.allowed_users,
    }

    if row.is_published or row.published_version_id is not None:
        version_num = await _next_version_number(db, str(row.id))
        version = AgentVersion(
            agent_settings_id=row.id,
            version_number=version_num,
            config=live_config,
            notes=body.notes,
            created_by=user.email,
        )
        db.add(version)
        await db.flush()
        row.published_version_id = version.id

    if row.draft_config:
        draft = row.draft_config
        if "connected_sources" in draft:
            draft["retrieval_enabled"] = bool(draft["connected_sources"])
        for key, value in draft.items():
            if hasattr(row, key):
                setattr(row, key, value)
        row.draft_config = None

    row.is_published = True
    row.published_at = func.now()
    await db.commit()
    await db.refresh(row)

    runtime = getattr(request.app.state, "runtime", None)
    if runtime:
        await runtime.refresh_graph()

    updated = await _fetch_agent_settings(db, slug=slug)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to load updated agent")
    return AgentSettingOut.model_validate(updated[0])


@router.post("/{slug}/restore/{version_id}", response_model=AgentSettingOut)
async def restore_agent_version(
    slug: str,
    version_id: str,
    user: AdminUser,
    db: DbSession,
    request: Request,
) -> AgentSettingOut:
    """
    Rollback an agent to a previous version.

    Overwrites live config with the version snapshot and creates a new
    version entry so history is preserved.
    """
    row = await db.scalar(select(AgentSettings).where(AgentSettings.slug == slug))
    if row is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    version = await db.get(AgentVersion, version_id)
    if version is None or str(version.agent_settings_id) != str(row.id):
        raise HTTPException(status_code=404, detail="Version not found")

    current_config = {
        "name": row.name,
        "description": row.description,
        "llm_model": row.llm_model,
        "system_prompt": row.system_prompt,
        "retrieval_top_k": row.retrieval_top_k,
        "retrieval_enabled": row.retrieval_enabled,
        "web_search_enabled": row.web_search_enabled,
        "connected_sources": row.connected_sources,
        "tools": row.tools,
        "is_orchestrator": row.is_orchestrator,
        "routes_to": row.routes_to,
        "mode_profile": row.mode_profile,
        "visibility": row.visibility,
        "created_by": row.created_by,
        "allow_uploads": row.allow_uploads,
        "allowed_users": row.allowed_users,
    }

    version_num = await _next_version_number(db, str(row.id))
    new_version = AgentVersion(
        agent_settings_id=row.id,
        version_number=version_num,
        config=current_config,
        notes=f"Rollback to v{version.version_number}",
        created_by=user.email,
    )
    db.add(new_version)
    await db.flush()

    config = version.config
    for key, value in config.items():
        if hasattr(row, key):
            setattr(row, key, value)

    row.published_version_id = new_version.id
    row.draft_config = None
    await db.commit()
    await db.refresh(row)

    runtime = getattr(request.app.state, "runtime", None)
    if runtime:
        await runtime.refresh_graph()

    updated = await _fetch_agent_settings(db, slug=slug)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to load updated agent")
    return AgentSettingOut.model_validate(updated[0])


@router.post("/{slug}/discard-draft", response_model=AgentSettingOut)
async def discard_agent_draft(
    slug: str,
    user: AdminUser,
    db: DbSession,
) -> AgentSettingOut:
    """Discard the current draft and revert to the published live config."""
    row = await db.scalar(select(AgentSettings).where(AgentSettings.slug == slug))
    if row is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    row.draft_config = None
    await db.commit()
    await db.refresh(row)

    updated = await _fetch_agent_settings(db, slug=slug)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to load updated agent")
    return AgentSettingOut.model_validate(updated[0])


class _VersionConfigOut(BaseModel):
    """Full version config for diff view."""
    id: str
    version_number: int
    config: dict
    notes: str | None
    created_by: str | None
    created_at: datetime


@router.get("/{slug}/versions/{version_id}", response_model=_VersionConfigOut)
async def get_agent_version(
    slug: str,
    version_id: str,
    user: AdminUser,
    db: DbSession,
) -> _VersionConfigOut:
    """Get a specific version with full config for diff view."""
    row = await db.scalar(select(AgentSettings).where(AgentSettings.slug == slug))
    if row is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    version = await db.get(AgentVersion, version_id)
    if version is None or str(version.agent_settings_id) != str(row.id):
        raise HTTPException(status_code=404, detail="Version not found")
    return _VersionConfigOut(
        id=str(version.id),
        version_number=version.version_number,
        config=version.config,
        notes=version.notes,
        created_by=version.created_by,
        created_at=version.created_at,
    )


class _TestDraftRequest(BaseModel):
    content: str
    mode: str = "auto"


class _TestDraftResponse(BaseModel):
    response: str


@router.post("/{slug}/test-draft", response_model=_TestDraftResponse)
async def test_agent_draft(
    slug: str,
    user: AdminUser,
    db: DbSession,
    body: _TestDraftRequest,
) -> _TestDraftResponse:
    """
    Test the agent's draft config by running it through the actual agent graph.

    This builds a temporary graph with draft overrides and invokes it, so tools,
    retrieval, routing, and orchestration are all tested with the draft settings.
    """
    from app.agents.graph import build_graph
    from app.agents.registry import AgentSpec
    from langchain_core.messages import HumanMessage

    row = await db.scalar(select(AgentSettings).where(AgentSettings.slug == slug))
    if row is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    draft = row.draft_config or {}
    system_prompt = draft.get("system_prompt") or row.system_prompt
    model_name = draft.get("llm_model") or row.llm_model
    tools = draft.get("tools") if "tools" in draft else row.tools
    is_orchestrator = draft.get("is_orchestrator") if "is_orchestrator" in draft else row.is_orchestrator
    routes_to = draft.get("routes_to") if "routes_to" in draft else row.routes_to
    connected_sources = draft.get("connected_sources") if "connected_sources" in draft else row.connected_sources
    retrieval_top_k = draft.get("retrieval_top_k") if "retrieval_top_k" in draft else row.retrieval_top_k

    all_agents = await db.scalars(select(AgentSettings))
    registry: dict[str, AgentSpec] = {}
    settings_map: dict[str, dict] = {}
    for a in all_agents.all():
        if a.slug == slug:
            registry[a.slug] = AgentSpec(
                slug=a.slug,
                name=draft.get("name") or a.name or a.slug,
                description=draft.get("description") or a.description or "",
                system_prompt=system_prompt,
                default_model=model_name or "gpt-5-nano",
                tools=tools or [],
                is_orchestrator=bool(is_orchestrator),
                routes_to=routes_to or [],
            )
            settings_map[a.slug] = {
                "model": model_name,
                "system_prompt": system_prompt,
                "retrieval_top_k": retrieval_top_k or 5,
                "connected_sources": connected_sources or [],
            }
        else:
            registry[a.slug] = AgentSpec(
                slug=a.slug,
                name=a.name or a.slug,
                description=a.description or "",
                system_prompt=a.system_prompt,
                default_model=a.llm_model or "gpt-5-nano",
                tools=a.tools or [],
                is_orchestrator=bool(a.is_orchestrator),
                routes_to=a.routes_to or [],
            )
            settings_map[a.slug] = {
                "model": a.llm_model,
                "system_prompt": a.system_prompt,
                "retrieval_top_k": a.retrieval_top_k or 5,
                "connected_sources": a.connected_sources or [],
            }

    graph = build_graph(checkpointer=None, agent_registry=registry, agent_settings=settings_map)

    input_state = {
        "messages": [HumanMessage(content=body.content)],
        "current_agent": slug,
        "orchestrator_agent": slug,
        "forced_agent": None,
        "mode": body.mode,
        "step_count": 0,
        "reflection_done": False,
        "_needs_rethink": False,
        "sources": [],
        "source_offset": 0,
        "user_allowed_slugs": list(registry.keys()),
    }

    result = await graph.ainvoke(input_state)
    response_text = result.get("response_text", "") if isinstance(result, dict) else ""
    return _TestDraftResponse(response=response_text)
