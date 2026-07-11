"""Admin agent settings API."""

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select, text

from app.agents.context import MODEL_CONTEXT_WINDOWS
from app.api.deps import AdminUser, DbSession
from app.core.config import settings
from app.models import AgentSettings, AgentSkill, AgentVersion, Connector, LLMSettings, Skill, UploadSettings
from app.schemas.agent_settings import (
    AgentDraftSave,
    AgentPublishRequest,
    AgentSettingCreate,
    AgentSettingOut,
    AgentSettingUpdate,
    AgentVersionOut,
    ModelOption,
)

router = APIRouter(prefix="/admin/agents", tags=["admin"])

_AGENT_SETTING_COLUMNS = """
SELECT id, slug, name, description, llm_model, system_prompt, retrieval_top_k,
       retrieval_enabled, web_search_enabled, connected_sources, tools, is_orchestrator, is_router,
       routes_to, mode_profile, visibility, created_by, allow_uploads, allowed_users, beta_users,
       agent_type, research_config, memory_enabled, emotions_enabled, episodes_enabled,
       created_at, updated_at, draft_config, is_published, published_at, published_version_id
FROM agent_settings
"""


_JSON_COLUMNS = frozenset({
    "connected_sources", "tools", "routes_to", "mode_profile",
    "allowed_users", "beta_users", "research_config", "draft_config",
})


async def _fetch_agent_settings(db: DbSession, slug: str | None = None) -> list[dict]:
    query = _AGENT_SETTING_COLUMNS
    params: dict[str, str] = {}
    if slug is not None:
        query += " WHERE slug = :slug"
        params["slug"] = slug
    else:
        query += " ORDER BY slug"
    result = await db.execute(text(query), params)
    rows = []
    for row in result.mappings().all():
        r = dict(row)
        for col in _JSON_COLUMNS:
            val = r.get(col)
            if isinstance(val, str):
                try:
                    r[col] = json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    pass
        rows.append(r)
    return rows

async def _get_llm_settings(db: DbSession) -> LLMSettings | None:
    return await db.scalar(select(LLMSettings))


@router.get("/models", response_model=list[ModelOption])
async def list_models(user: AdminUser, db: DbSession) -> list[ModelOption]:
    """Return available LLM model options grouped by provider."""
    options: list[ModelOption] = []

    cloud_models = [k for k in MODEL_CONTEXT_WINDOWS if not k.startswith("ollama/")]
    if "gpt-5.4-nano" in cloud_models:
        cloud_models.remove("gpt-5.4-nano")
        cloud_models.insert(0, "gpt-5.4-nano")
    for m in cloud_models:
        options.append(ModelOption(name=m, provider="openai", label=m))

    llm_settings = await _get_llm_settings(db)
    if llm_settings and llm_settings.ollama_enabled:
        for model_name in llm_settings.ollama_enabled_models:
            label = model_name[len("ollama/"):] if model_name.startswith("ollama/") else model_name
            options.append(ModelOption(name=model_name, provider="ollama", label=label))

    return options

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
    await _validate_upload_settings(db, data.get("allow_uploads", True))
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
    if "allow_uploads" in data:
        await _validate_upload_settings(db, data["allow_uploads"])

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

    if not row.is_published and draft_data:
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


async def _validate_upload_settings(db: DbSession, allow_uploads: bool) -> None:
    """Raise if uploads are enabled for an agent but global settings are missing."""
    if not allow_uploads:
        return
    settings = await db.scalar(select(UploadSettings))
    if settings is None or not settings.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File uploads are not globally enabled. Go to Upload Settings first.",
        )
    if not settings.s3_connector_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No S3 connector assigned in Upload Settings.",
        )
    connector = await db.get(Connector, settings.s3_connector_id)
    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assigned S3 connector does not exist. Check Upload Settings.",
        )
    if not settings.s3_bucket or not settings.s3_bucket.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="S3 bucket is not configured in Upload Settings.",
        )


async def _next_version_number(db: DbSession, agent_id: str) -> int:
    result = await db.execute(
        text("SELECT COALESCE(MAX(version_number), 0) FROM agent_versions WHERE agent_settings_id = :aid OR agent_settings_id = :aid_hex"),
        {"aid": agent_id, "aid_hex": agent_id.replace("-", "")},
    )
    return (result.scalar() or 0) + 1


@router.get("/{slug}/versions", response_model=list[AgentVersionOut])
async def list_agent_versions(
    slug: str, user: AdminUser, db: DbSession
) -> list[AgentVersionOut]:
    """List version history for an agent (newest first)."""
    row = await db.scalar(select(AgentSettings).where(AgentSettings.slug == slug))
    if row is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    result = await db.execute(
        text("""
            SELECT id, agent_settings_id, version_number, config, notes, created_by, created_at
            FROM agent_versions
            WHERE agent_settings_id = :aid OR agent_settings_id = :aid_hex
            ORDER BY version_number DESC
        """),
        {"aid": str(row.id), "aid_hex": row.id.hex},
    )
    versions = []
    for r in result.mappings().all():
        d = dict(r)
        if isinstance(d.get("config"), str):
            try:
                import json
                d["config"] = json.loads(d["config"])
            except (json.JSONDecodeError, TypeError):
                pass
        versions.append(AgentVersionOut.model_validate(d))
    return versions


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
    if "allow_uploads" in data:
        await _validate_upload_settings(db, data["allow_uploads"])
    if "connected_sources" in data:
        data["retrieval_enabled"] = bool(data["connected_sources"])
    if "created_by" in data and data["created_by"] is not None:
        data["created_by"] = data["created_by"].strip().lower()

    existing_draft = dict(row.draft_config or {})
    existing_draft.update(data)

    filtered_draft: dict[str, Any] = {}
    for key, value in existing_draft.items():
        if key in ("draft_config", "is_published", "published_at", "published_version_id"):
            continue
        if hasattr(row, key):
            live_value = getattr(row, key)

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
        "agent_type": row.agent_type,
        "research_config": row.research_config,
        "memory_enabled": row.memory_enabled,
        "emotions_enabled": row.emotions_enabled,
        "episodes_enabled": row.episodes_enabled,
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
        if "allow_uploads" in draft:
            await _validate_upload_settings(db, draft["allow_uploads"])
        if "connected_sources" in draft:
            draft["retrieval_enabled"] = bool(draft["connected_sources"])

        if "skill_ids" in draft:
            existing_links = (await db.execute(
                select(AgentSkill).where(AgentSkill.agent_slug == slug)
            )).scalars().all()
            for link in existing_links:
                await db.delete(link)
            for sid in draft["skill_ids"]:
                db.add(AgentSkill(agent_slug=slug, skill_id=sid))

        for key, value in draft.items():
            if key == "skill_ids":
                continue
            if hasattr(row, key):
                setattr(row, key, value)
        row.draft_config = None

    await _validate_upload_settings(db, row.allow_uploads)
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

    version_row = await db.execute(
        text("""
            SELECT id, agent_settings_id, version_number, config, notes, created_by, created_at
            FROM agent_versions WHERE id = :vid OR id = :vid_hex
        """),
        {"vid": str(version_id), "vid_hex": str(version_id).replace("-", "")},
    )
    vdata = version_row.mappings().first()
    if vdata is None or str(vdata["agent_settings_id"]).replace("-", "") != str(row.id).replace("-", ""):
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
        "agent_type": row.agent_type,
        "research_config": row.research_config,
        "memory_enabled": row.memory_enabled,
        "emotions_enabled": row.emotions_enabled,
        "episodes_enabled": row.episodes_enabled,
    }

    version_num = await _next_version_number(db, str(row.id))
    new_version = AgentVersion(
        agent_settings_id=row.id,
        version_number=version_num,
        config=current_config,
        notes=f"Rollback to v{vdata['version_number']}",
        created_by=user.email,
    )
    db.add(new_version)
    await db.flush()

    config = vdata["config"]
    if isinstance(config, str):
        config = json.loads(config)
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
    version_row = await db.execute(
        text("""
            SELECT id, agent_settings_id, version_number, config, notes, created_by, created_at
            FROM agent_versions WHERE id = :vid OR id = :vid_hex
        """),
        {"vid": str(version_id), "vid_hex": str(version_id).replace("-", "")},
    )
    vdata = version_row.mappings().first()
    if vdata is None or str(vdata["agent_settings_id"]).replace("-", "") != str(row.id).replace("-", ""):
        raise HTTPException(status_code=404, detail="Version not found")
    config = vdata["config"]
    if isinstance(config, str):
        config = json.loads(config)
    return _VersionConfigOut(
        id=str(vdata["id"]),
        version_number=vdata["version_number"],
        config=config,
        notes=vdata["notes"],
        created_by=vdata["created_by"],
        created_at=vdata["created_at"],
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
    from app.agents.runtime import build_graph_config
    from langchain_core.messages import HumanMessage

    row = await db.scalar(select(AgentSettings).where(AgentSettings.slug == slug))
    if row is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    registry, settings_map, workflows = await build_graph_config(db, slug=slug)
    graph = build_graph(checkpointer=None, agent_registry=registry, agent_settings=settings_map, workflows=workflows)

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
