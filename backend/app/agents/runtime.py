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
from app.models import AgentSettings, AgentWorkflow, KnowledgeSource

logger = logging.getLogger(__name__)


class AgentRuntime:
    """Holds the compiled LangGraph and its checkpointer resources."""

    def __init__(self) -> None:
        self.graph = None
        self.agent_registry: dict[str, AgentSpec] = {}
        self._pool: AsyncConnectionPool | None = None

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
                default_model=row.llm_model or "gpt-5-nano",
                tools=row.tools or [],
                is_orchestrator=row.is_orchestrator if row.is_orchestrator is not None else False,
                routes_to=row.routes_to or [],
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
            max_size=5,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
                "row_factory": dict_row,
            },
        )
        await self._pool.open()
        checkpointer = AsyncPostgresSaver(self._pool)
        await checkpointer.setup()

        agent_registry: dict[str, AgentSpec] = {}
        agent_settings: dict[str, dict] = {}
        workflows: dict[str, dict] = {}
        try:
            async with async_session_factory() as session:
                agent_registry = await self._load_agent_registry(session)
                result = await session.scalars(select(AgentSettings))
                for row in result.all():
                    raw_sources = row.connected_sources
                    sources = await self._normalize_sources(session, raw_sources)
                    agent_settings[row.slug] = {
                        "model": row.llm_model,
                        "system_prompt": row.system_prompt,
                        "retrieval_top_k": row.retrieval_top_k,
                        "connected_sources": sources,
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
        self.graph = build_graph(checkpointer, agent_registry=agent_registry, agent_settings=agent_settings, workflows=workflows)
        logger.info("Agent graph refreshed with settings for %d agents", len(agent_registry))

    async def shutdown(self) -> None:
        """Close the database connection pool."""
        if self._pool is not None:
            await self._pool.close()


def get_runtime(request: Request) -> AgentRuntime:
    """
    Get the agent runtime from the request state.
    
    Args:
        request: FastAPI request object
        
    Returns:
        AgentRuntime instance
        
    Raises:
        HTTPException: If the runtime is not ready
    """
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None or runtime.graph is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent runtime is not ready",
        )
    return runtime


RuntimeDep = Annotated[AgentRuntime, Depends(get_runtime)]
