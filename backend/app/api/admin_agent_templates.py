"""Admin agent template gallery API."""

import json

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, text

from app.api.deps import AdminUser, DbSession
from app.data.agent_templates import load_all_templates, load_template
from app.models import AgentSettings, AgentWorkflow
from app.schemas.agent_settings import (
    AgentSettingOut,
    AgentTemplateDeployRequest,
    AgentTemplateDetailOut,
    AgentTemplateOut,
)

router = APIRouter(prefix="/admin/agent-templates", tags=["admin"])


@router.get("", response_model=list[AgentTemplateOut])
async def list_agent_templates(user: AdminUser) -> list[AgentTemplateOut]:
    """List all available agent templates (metadata only)."""
    templates = load_all_templates()
    return [
        AgentTemplateOut(
            id=t["id"],
            name=t.get("name", t["id"]),
            description=t.get("description"),
            tags=t.get("tags", []),
        )
        for t in templates
    ]


@router.get("/{template_id}", response_model=AgentTemplateDetailOut)
async def get_agent_template(template_id: str, user: AdminUser) -> AgentTemplateDetailOut:
    """Get a single template with full config for preview."""
    data = load_template(template_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return AgentTemplateDetailOut(
        id=data["id"],
        name=data.get("name", data["id"]),
        description=data.get("description"),
        tags=data.get("tags", []),
        agent_config=data.get("agent_config", {}),
        workflows=data.get("workflows", []),
    )


@router.post("/{template_id}/deploy", response_model=AgentSettingOut, status_code=201)
async def deploy_agent_template(
    template_id: str,
    user: AdminUser,
    db: DbSession,
    body: AgentTemplateDeployRequest,
) -> AgentSettingOut:
    """Create an unpublished agent from a template so the admin can review and publish it later."""
    template = load_template(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    existing = await db.scalar(select(AgentSettings).where(AgentSettings.slug == body.slug))
    if existing:
        raise HTTPException(status_code=409, detail="Agent slug already exists")

    agent_config: dict = dict(template.get("agent_config", {}))
    agent_config["slug"] = body.slug
    if body.name is not None:
        agent_config["name"] = body.name
    if body.description is not None:
        agent_config["description"] = body.description
    if "created_by" not in agent_config or not agent_config["created_by"]:
        agent_config["created_by"] = user.email.strip().lower()
    if "retrieval_enabled" not in agent_config:
        agent_config["retrieval_enabled"] = bool(agent_config.get("connected_sources"))

    tools = agent_config.get("tools") or []
    if isinstance(tools, list):
        agent_config["tools"] = [t for t in tools if t != "retrieve"]

    if agent_config.get("visibility") == "restricted":
        allowed = [str(e).strip().lower() for e in (agent_config.get("allowed_users") or []) if str(e).strip()]
        owner = str(agent_config.get("created_by") or user.email).strip().lower()
        if owner not in allowed:
            allowed.insert(0, owner)
        agent_config["allowed_users"] = allowed

    agent_row = AgentSettings(**agent_config)
    db.add(agent_row)
    await db.flush()
    await db.refresh(agent_row)

    for wf_def in template.get("workflows", []):
        wf_row = AgentWorkflow(
            owner_agent_slug=body.slug,
            name=wf_def.get("name", "Untitled Workflow"),
            description=wf_def.get("description"),
            enabled=wf_def.get("enabled", False),
            definition=wf_def.get("definition", {}),
        )
        db.add(wf_row)

    await db.commit()
    await db.refresh(agent_row)

    result = await db.execute(
        text("""
        SELECT id, slug, name, description, llm_model, system_prompt, retrieval_top_k,
               retrieval_enabled, web_search_enabled, connected_sources, tools, is_orchestrator, is_router,
               routes_to, mode_profile, visibility, created_by, allow_uploads, allowed_users, beta_users,
               created_at, updated_at, draft_config, is_published, published_at, published_version_id
        FROM agent_settings WHERE slug = :slug
        """),
        {"slug": body.slug},
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=500, detail="Failed to load created agent")
    r = dict(row)
    for col in ("connected_sources", "tools", "routes_to", "mode_profile", "allowed_users", "beta_users", "draft_config"):
        val = r.get(col)
        if isinstance(val, str):
            try:
                r[col] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
    return AgentSettingOut.model_validate(r)
