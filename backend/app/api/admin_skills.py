"""Admin skills API."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select

from app.api.deps import AdminUser, DbSession
from app.models import AgentSkill, Skill
from app.schemas.skill import AgentSkillAssign, AgentSkillBatchUpdate, SkillCreate, SkillOut, SkillUpdate

router = APIRouter(tags=["admin"])


async def _refresh_runtime(request: Request) -> None:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime:
        await runtime.refresh_graph()


@router.get("/admin/skills", response_model=list[SkillOut])
async def list_all_skills(user: AdminUser, db: DbSession):
    result = await db.execute(select(Skill).order_by(Skill.created_at.desc()))
    return result.scalars().all()


@router.post("/admin/skills", response_model=SkillOut, status_code=status.HTTP_201_CREATED)
async def create_skill(user: AdminUser, db: DbSession, request: Request, body: SkillCreate):
    skill = Skill(
        name=body.name,
        description=body.description,
        content=body.content,
        scope=body.scope,
        agent_slug=body.agent_slug,
        is_enabled=body.is_enabled,
        created_by=user.email,
    )
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    await _refresh_runtime(request)
    return skill


@router.put("/admin/skills/{skill_id}", response_model=SkillOut)
async def update_skill(user: AdminUser, db: DbSession, request: Request, skill_id: UUID, body: SkillUpdate):
    skill = await db.get(Skill, skill_id)
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(skill, field, value)
    await db.commit()
    await db.refresh(skill)
    await _refresh_runtime(request)
    return skill


@router.delete("/admin/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(user: AdminUser, db: DbSession, request: Request, skill_id: UUID):
    skill = await db.get(Skill, skill_id)
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    await db.delete(skill)
    await db.commit()
    await _refresh_runtime(request)


@router.get("/admin/agents/{slug}/skills", response_model=list[SkillOut])
async def list_agent_skills(user: AdminUser, db: DbSession, slug: str):
    per_agent = await db.execute(
        select(Skill).where(Skill.agent_slug == slug, Skill.scope == "agent").order_by(Skill.created_at.desc())
    )
    assigned_ids = await db.execute(
        select(AgentSkill.skill_id).where(AgentSkill.agent_slug == slug)
    )
    assigned_id_list = [row[0] for row in assigned_ids]
    shared_skills = []
    if assigned_id_list:
        shared_result = await db.execute(
            select(Skill).where(Skill.id.in_(assigned_id_list)).order_by(Skill.created_at.desc())
        )
        shared_skills = shared_result.scalars().all()
    return list(per_agent.scalars().all()) + shared_skills


@router.post("/admin/agents/{slug}/skills", response_model=SkillOut, status_code=status.HTTP_201_CREATED)
async def create_agent_skill(user: AdminUser, db: DbSession, request: Request, slug: str, body: SkillCreate):
    skill = Skill(
        name=body.name,
        description=body.description,
        content=body.content,
        scope="agent",
        agent_slug=slug,
        is_enabled=body.is_enabled,
        created_by=user.email,
    )
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    await _refresh_runtime(request)
    return skill


@router.put("/admin/agents/{slug}/skills/{skill_id}", response_model=SkillOut)
async def update_agent_skill(user: AdminUser, db: DbSession, request: Request, slug: str, skill_id: UUID, body: SkillUpdate):
    skill = await db.get(Skill, skill_id)
    if not skill or skill.agent_slug != slug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(skill, field, value)
    await db.commit()
    await db.refresh(skill)
    await _refresh_runtime(request)
    return skill


@router.delete("/admin/agents/{slug}/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent_skill(user: AdminUser, db: DbSession, request: Request, slug: str, skill_id: UUID):
    skill = await db.get(Skill, skill_id)
    if not skill or skill.agent_slug != slug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    await db.delete(skill)
    await db.commit()
    await _refresh_runtime(request)


@router.post("/admin/agents/{slug}/skills/{skill_id}/toggle", response_model=SkillOut)
async def toggle_agent_skill(user: AdminUser, db: DbSession, request: Request, slug: str, skill_id: UUID):
    import logging as _log
    _logger = _log.getLogger("app.api.admin_skills")

    skill = await db.get(Skill, skill_id)
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")

    if skill.scope == "agent" and skill.agent_slug != slug:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found for this agent")

    if skill.scope == "shared":
        assigned = await db.execute(
            select(AgentSkill).where(AgentSkill.agent_slug == slug, AgentSkill.skill_id == skill_id)
        )
        if not assigned.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared skill not assigned to this agent")

    skill.is_enabled = not skill.is_enabled
    await db.commit()
    await db.refresh(skill)
    _logger.info("SKILL TOGGLE | agent=%s skill=%s scope=%s is_enabled=%s", slug, skill.name, skill.scope, skill.is_enabled)
    await _refresh_runtime(request)
    return skill


@router.post("/admin/agents/{slug}/skills/assign", response_model=SkillOut)
async def assign_shared_skill(user: AdminUser, db: DbSession, request: Request, slug: str, body: AgentSkillAssign):
    skill = await db.get(Skill, body.skill_id)
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not found")
    if skill.scope != "shared":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only shared skills can be assigned")
    existing = await db.execute(
        select(AgentSkill).where(AgentSkill.agent_slug == slug, AgentSkill.skill_id == body.skill_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Skill already assigned")
    db.add(AgentSkill(agent_slug=slug, skill_id=body.skill_id))
    await db.commit()
    await _refresh_runtime(request)
    return skill


@router.delete("/admin/agents/{slug}/skills/{skill_id}/unassign", status_code=status.HTTP_204_NO_CONTENT)
async def unassign_shared_skill(user: AdminUser, db: DbSession, request: Request, slug: str, skill_id: UUID):
    result = await db.execute(
        select(AgentSkill).where(AgentSkill.agent_slug == slug, AgentSkill.skill_id == skill_id)
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill not assigned to this agent")
    await db.delete(link)
    await db.commit()
    await _refresh_runtime(request)


@router.post("/admin/agents/{slug}/skills/batch", response_model=list[SkillOut])
async def batch_update_agent_skills(
    user: AdminUser, db: DbSession, request: Request, slug: str, body: AgentSkillBatchUpdate
):
    """Batch assign and/or unassign shared skills for an agent. Single graph refresh."""
    import logging as _log
    _logger = _log.getLogger("app.api.admin_skills")

    for skill_id in body.assign:
        existing = await db.execute(
            select(AgentSkill).where(AgentSkill.agent_slug == slug, AgentSkill.skill_id == skill_id)
        )
        if not existing.scalar_one_or_none():
            db.add(AgentSkill(agent_slug=slug, skill_id=skill_id))

    for skill_id in body.unassign:
        result = await db.execute(
            select(AgentSkill).where(AgentSkill.agent_slug == slug, AgentSkill.skill_id == skill_id)
        )
        link = result.scalar_one_or_none()
        if link:
            await db.delete(link)

    await db.commit()
    _logger.info(
        "SKILL BATCH | agent=%s assigned=%d unassigned=%d",
        slug, len(body.assign), len(body.unassign),
    )
    await _refresh_runtime(request)

    return await list_agent_skills(user, db, slug)
