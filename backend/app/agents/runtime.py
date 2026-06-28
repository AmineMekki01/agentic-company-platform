import logging
import uuid
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from sqlalchemy import select

from app.agents.graph import build_graph
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

    async def _load_agent_skills(self, session) -> dict[str, list[dict]]:
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
            logger.exception("Checkpointer setup failed at startup — will retry on first request")
            return

        agent_registry: dict[str, AgentSpec] = {}
        agent_settings: dict[str, dict] = {}
        workflows: dict[str, dict] = {}
        try:
            async with async_session_factory() as session:
                agent_registry = await self._load_agent_registry(session)
                skills_map = await self._load_agent_skills(session)
                result = await session.scalars(select(AgentSettings))
                for row in result.all():
                    raw_sources = row.connected_sources
                    sources = await self._normalize_sources(session, raw_sources)
                    agent_settings[row.slug] = {
                        "model": row.llm_model,
                        "system_prompt": row.system_prompt,
                        "retrieval_top_k": row.retrieval_top_k,
                        "connected_sources": sources,
                        "agent_type": row.agent_type if row.agent_type else "standard",
                        "research_config": row.research_config,
                        "skills": skills_map.get(row.slug, []),
                    }
                    logger.warning(
                        "Agent config loaded: slug=%s connected_sources=%s (raw=%s)",
                        row.slug,
                        sources,
                        raw_sources,
                    )
                wf_result = await session.scalars(select(AgentWorkflow).where(AgentWorkflow.enabled == True))
                for wf in wf_result.all():
                    definition = dict(wf.definition)
                    definition["enabled"] = wf.enabled
                    workflows[wf.owner_agent_slug] = definition
                    logger.warning("Workflow loaded for agent=%s name=%s", wf.owner_agent_slug, wf.name)
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
                agent_registry = await self._load_agent_registry(session)
                skills_map = await self._load_agent_skills(session)
                for slug, spec in agent_registry.items():
                    agent_row = await session.scalar(select(AgentSettings).where(AgentSettings.slug == slug))
                    if agent_row:
                        raw_sources = agent_row.connected_sources
                        sources = await self._normalize_sources(session, raw_sources)
                        agent_settings[slug] = {
                            "model": agent_row.llm_model,
                            "system_prompt": agent_row.system_prompt,
                            "retrieval_top_k": agent_row.retrieval_top_k,
                            "connected_sources": sources,
                            "agent_type": agent_row.agent_type if agent_row.agent_type else "standard",
                            "research_config": agent_row.research_config,
                            "skills": skills_map.get(slug, []),
                        }
                        logger.warning(
                            "Agent config refreshed: slug=%s connected_sources=%s (raw=%s)",
                            slug,
                            sources,
                            raw_sources,
                        )
                wf_result = await session.scalars(select(AgentWorkflow).where(AgentWorkflow.enabled == True))
                for wf in wf_result.all():
                    definition = dict(wf.definition)
                    definition["enabled"] = wf.enabled
                    workflows[wf.owner_agent_slug] = definition
                    logger.warning("Workflow refreshed for agent=%s name=%s", wf.owner_agent_slug, wf.name)
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
        logger.warning("Runtime graph is None but pool is open — attempting lazy rebuild")
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
