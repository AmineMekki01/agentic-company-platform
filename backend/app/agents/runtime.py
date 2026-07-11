import logging
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from sqlalchemy import select

from app.agents.graph import build_graph, get_builtin_chat_spec, CHAT_AGENT_SLUG
from app.agents.registry import AgentSpec
from app.core.config import settings
from app.db.session import async_session_factory
from app.models import AgentSettings, AgentSkill, AgentWorkflow, KnowledgeSource, Skill

logger = logging.getLogger(__name__)


class AgentRuntime:
    """Holds the compiled LangGraph and its checkpointer resources."""

    def __init__(self) -> None:
        self.graph = None
        self.agent_registry: dict[str, AgentSpec] = {}
        self._pool: AsyncConnectionPool | None = None
        self._checkpointer = None

    @property
    def checkpointer(self):
        """Return the current checkpointer (or None if not initialized)."""
        if self._checkpointer is not None:
            return self._checkpointer
        if self._pool is not None:
            self._checkpointer = AsyncPostgresSaver(self._pool)
            return self._checkpointer
        return None

    async def _normalize_sources(self, session, sources: list[str] | None) -> list[str] | None:
        """
        Resolve any slugs in connected_sources to knowledge_source UUIDs.
        Drop values that can't be resolved.
        
        Args:
            session: Database session
            sources: List of source IDs (UUIDs or slugs)
            
        Returns:
            List of normalized source IDs (UUIDs only)
        """
        if not sources:
            return sources
        
        normalized: list[str] = []

        for s in sources:
            try:
                uuid.UUID(s)
                normalized.append(s)
                continue
            except ValueError:
                pass

            ks = await session.scalar(select(KnowledgeSource).where(KnowledgeSource.slug == s))
            if ks:
                normalized.append(str(ks.id))
        return normalized if normalized else None

    async def _load_agent_skills(
        self,
        session,
        draft_slug: str | None = None,
        draft_skill_ids: list[str] | None = None,
    ) -> dict[str, list[dict]]:
        """Load enabled skills for each agent (per-agent + assigned shared)."""
        skills_map: dict[str, list[dict]] = {}

        per_agent_result = await session.execute(
            select(Skill).where(Skill.scope == "agent", Skill.is_enabled == True)
        )
        for skill in per_agent_result.scalars().all():
            if not skill.agent_slug:
                continue
            skills_map.setdefault(skill.agent_slug, []).append({
                "name": skill.name,
                "description": skill.description,
                "content": skill.content,
            })

        if draft_slug and draft_skill_ids is not None:
            draft_uuids = [str(sid) for sid in draft_skill_ids]
            shared_result = await session.execute(
                select(Skill).where(
                    Skill.scope == "shared",
                    Skill.is_enabled == True,
                    Skill.id.in_([uuid.UUID(sid) for sid in draft_uuids if sid]),
                )
            )
            for skill in shared_result.scalars().all():
                skills_map.setdefault(draft_slug, []).append({
                    "name": skill.name,
                    "description": skill.description,
                    "content": skill.content,
                })

            non_draft_result = await session.execute(
                select(AgentSkill, Skill)
                .join(Skill, AgentSkill.skill_id == Skill.id)
                .where(Skill.scope == "shared", Skill.is_enabled == True)
                .where(AgentSkill.agent_slug != draft_slug)
            )
            for link, skill in non_draft_result.all():
                skills_map.setdefault(link.agent_slug, []).append({
                    "name": skill.name,
                    "description": skill.description,
                    "content": skill.content,
                })
        else:
            shared_result = await session.execute(
                select(AgentSkill, Skill)
                .join(Skill, AgentSkill.skill_id == Skill.id)
                .where(Skill.scope == "shared", Skill.is_enabled == True)
            )
            for link, skill in shared_result.all():
                skills_map.setdefault(link.agent_slug, []).append({
                    "name": skill.name,
                    "description": skill.description,
                    "content": skill.content,
                })

        for agent_slug, agent_skill_list in skills_map.items():
            logger.info("Skills loaded for agent=%s: %s", agent_slug, [s["name"] for s in agent_skill_list])

        return skills_map

    async def _load_agent_registry(self, session) -> dict[str, AgentSpec]:
        """Build the agent registry from DB settings."""
        registry: dict[str, AgentSpec] = {}
        result = await session.scalars(select(AgentSettings))
        for row in result.all():
            registry[row.slug] = AgentSpec(
                slug=row.slug,
                name=row.name or row.slug,
                description=row.description or "",
                system_prompt=row.system_prompt,
                default_model=row.llm_model or "gpt-5.4-nano",
                tools=row.tools or [],
                is_orchestrator=row.is_orchestrator if row.is_orchestrator is not None else False,
                is_router=row.is_router if row.is_router is not None else False,
                routes_to=row.routes_to or [],
                agent_type=row.agent_type if row.agent_type else "standard",
                research_config=row.research_config,
            )

        if CHAT_AGENT_SLUG not in registry:
            chat_spec = get_builtin_chat_spec()
            registry[CHAT_AGENT_SLUG] = chat_spec
            logger.info("Injected built-in chat agent fallback (not found in DB)")

        return registry

    async def startup(self) -> None:
        """
        Initialize the runtime resources.

        This method should be called once at application startup.
        """
        conninfo = settings.database_url.replace("+asyncpg", "")
        self._pool = AsyncConnectionPool(
            conninfo,
            open=False,
            max_size=settings.checkpointer_pool_size,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
                "row_factory": dict_row,
            },
        )
        await self._pool.open()
        try:
            checkpointer = AsyncPostgresSaver(self._pool)
            await checkpointer.setup()
        except Exception:
            logger.exception("Checkpointer setup failed at startup - will retry on first request")
            return

        agent_registry: dict[str, AgentSpec] = {}
        agent_settings: dict[str, dict] = {}
        workflows: dict[str, dict] = {}
        try:
            async with async_session_factory() as session:
                agent_registry, agent_settings, workflows = await build_graph_config(session)
        except Exception:
            logger.exception("Failed to load agent settings at startup")

        self.agent_registry = agent_registry
        self.graph = build_graph(checkpointer, agent_registry=agent_registry, agent_settings=agent_settings, workflows=workflows)

    async def refresh_graph(self) -> None:
        """Rebuild the graph with the latest agent settings from the DB."""
        agent_registry: dict[str, AgentSpec] = {}
        agent_settings: dict[str, dict] = {}
        workflows: dict[str, dict] = {}
        try:
            async with async_session_factory() as session:
                agent_registry, agent_settings, workflows = await build_graph_config(session)
        except Exception:
            logger.exception("Failed to reload agent settings during refresh")

        self.agent_registry = agent_registry
        checkpointer = AsyncPostgresSaver(self._pool)
        await checkpointer.setup()
        self.graph = build_graph(checkpointer, agent_registry=agent_registry, agent_settings=agent_settings, workflows=workflows)
        logger.info("Agent graph refreshed with settings for %d agents", len(agent_registry))

    async def shutdown(self) -> None:
        """Close the database connection pool."""
        if self._pool is not None:
            await self._pool.close()


async def build_graph_config(
    session,
    slug: str | None = None,
) -> tuple[dict[str, AgentSpec], dict[str, dict], dict[str, dict]]:
    """
    Build (registry, settings_map, workflows) from the DB.
    """
    from app.models import AgentSettings as _AS

    result = await session.scalars(select(_AS))
    rows = result.all()

    draft_skill_ids: list[str] | None = None
    if slug:
        draft_row = next((r for r in rows if r.slug == slug and r.draft_config), None)
        if draft_row and "skill_ids" in draft_row.draft_config:
            draft_skill_ids = draft_row.draft_config["skill_ids"]

    skills_map = await AgentRuntime()._load_agent_skills(
        session,
        draft_slug=slug if draft_skill_ids is not None else None,
        draft_skill_ids=draft_skill_ids,
    )

    workflows: dict[str, dict] = {}
    wf_result = await session.scalars(select(AgentWorkflow).where(AgentWorkflow.enabled == True))
    for wf in wf_result.all():
        definition = dict(wf.definition)
        definition["enabled"] = wf.enabled
        workflows[wf.owner_agent_slug] = definition

    registry: dict[str, AgentSpec] = {}
    settings_map: dict[str, dict] = {}

    for row in rows:
        draft = row.draft_config if (slug and row.slug == slug and row.draft_config) else None

        def _val(key: str, fallback):
            if draft and key in draft:
                return draft[key]
            return fallback

        name = _val("name", row.name or row.slug)
        description = _val("description", row.description or "")
        system_prompt = _val("system_prompt", row.system_prompt)
        model_name = _val("llm_model", row.llm_model)
        tools = _val("tools", row.tools) if (draft and "tools" in draft) else row.tools
        is_orchestrator = _val("is_orchestrator", row.is_orchestrator) if (draft and "is_orchestrator" in draft) else row.is_orchestrator
        is_router = _val("is_router", row.is_router) if (draft and "is_router" in draft) else row.is_router
        routes_to = _val("routes_to", row.routes_to) if (draft and "routes_to" in draft) else row.routes_to
        connected_sources = _val("connected_sources", row.connected_sources) if (draft and "connected_sources" in draft) else row.connected_sources
        retrieval_top_k = _val("retrieval_top_k", row.retrieval_top_k)
        agent_type = _val("agent_type", row.agent_type) if (draft and "agent_type" in draft) else (row.agent_type or "standard")
        research_config = _val("research_config", row.research_config) if (draft and "research_config" in draft) else row.research_config
        memory_enabled = _val("memory_enabled", row.memory_enabled) if (draft and "memory_enabled" in draft) else (row.memory_enabled if row.memory_enabled is not None else False)
        emotions_enabled = _val("emotions_enabled", row.emotions_enabled) if (draft and "emotions_enabled" in draft) else (row.emotions_enabled if row.emotions_enabled is not None else False)
        episodes_enabled = _val("episodes_enabled", row.episodes_enabled) if (draft and "episodes_enabled" in draft) else (row.episodes_enabled if row.episodes_enabled is not None else False)

        registry[row.slug] = AgentSpec(
            slug=row.slug,
            name=name,
            description=description,
            system_prompt=system_prompt,
            default_model=model_name or "gpt-5.4-nano",
            tools=tools or [],
            is_orchestrator=bool(is_orchestrator),
            is_router=bool(is_router) if is_router is not None else False,
            routes_to=routes_to or [],
            agent_type=agent_type,
            research_config=research_config,
        )

        raw_sources = connected_sources
        sources = await AgentRuntime()._normalize_sources(session, raw_sources)
        settings_map[row.slug] = {
            "model": model_name,
            "system_prompt": system_prompt,
            "retrieval_top_k": retrieval_top_k or 5,
            "connected_sources": sources,
            "agent_type": agent_type,
            "research_config": research_config,
            "skills": skills_map.get(row.slug, []),
            "memory_enabled": bool(memory_enabled),
            "emotions_enabled": bool(emotions_enabled),
            "episodes_enabled": bool(episodes_enabled),
        }

        if slug and row.slug == slug and draft:
            logger.info("build_graph_config: agent=%s using DRAFT config (draft keys=%s)", row.slug, list(draft.keys()))
        else:
            logger.debug("build_graph_config: agent=%s using published config", row.slug)

    if CHAT_AGENT_SLUG not in registry:
        chat_spec = get_builtin_chat_spec()
        registry[CHAT_AGENT_SLUG] = chat_spec
        settings_map[CHAT_AGENT_SLUG] = {
            "model": chat_spec.default_model,
            "system_prompt": chat_spec.system_prompt,
            "retrieval_top_k": 5,
            "connected_sources": [],
            "agent_type": "standard",
            "research_config": None,
            "skills": [],
            "memory_enabled": True,
            "emotions_enabled": True,
            "episodes_enabled": True,
        }
        logger.info("build_graph_config: injected built-in chat agent fallback")

    return registry, settings_map, workflows


async def get_runtime(request: Request) -> AgentRuntime:
    """
    Get the agent runtime from the request state.
    If the graph failed to build at startup but the connection pool is open, attempt a lazy rebuild before returning 503.
    """
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent runtime is not ready",
        )
    if runtime.graph is None and runtime._pool is not None:
        logger.warning("Runtime graph is None but pool is open - attempting lazy rebuild")
        try:
            await runtime.refresh_graph()
        except Exception:
            logger.exception("Lazy runtime rebuild failed")
    if runtime.graph is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent runtime is not ready",
        )
    return runtime


RuntimeDep = Annotated[AgentRuntime, Depends(get_runtime)]
