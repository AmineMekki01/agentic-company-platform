import logging
import re

from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, StateGraph

from app.agents.context import (
    auto_select_mode,
    clamp_retrieval_context,
    get_mode_profile,
    resolve_context_window,
    trim_history,
)
from app.agents.llm import get_chat_model
from app.agents.registry import AgentSpec
from app.agents.state import AgentState
from app.agents.tools import retrieve, web_search
from app.agents.tools_jira import create_jira_ticket
from app.services.rag import RAGService

logger = logging.getLogger(__name__)

_TOOL_REGISTRY = {"retrieve": retrieve, "web_search": web_search, "create_jira_ticket": create_jira_ticket}


async def _retrieve_for_agent(query: str, source_ids: list[str] | None, agent_slug: str = "unknown") -> tuple[str, list[dict]]:
    """Fetch relevant documents for an agent.

    Args:
        query: The search query
        source_ids: List of source IDs to filter by, or None for all sources
        agent_slug: The agent slug for logging
    
    Returns:
        Tuple of (formatted_context, source_metadata_list)
    """
    if source_ids == []:
        logger.warning("Agent[%s] retrieve skipped: connected_sources is empty list (no sources configured)", agent_slug)
        return "", []
    if source_ids is None:
        logger.warning("Agent[%s] retrieve: querying ALL knowledge sources (source_ids=None)", agent_slug)
    else:
        logger.warning("Agent[%s] retrieve: filtering to source_ids=%s (count=%d)", agent_slug, source_ids, len(source_ids))
    rag = RAGService()
    chunks = await rag.retrieve(query, source_ids=source_ids)
    unique_sources = {c.source_id for c in chunks}
    source_summary = {c.source_id: c.source_title for c in chunks}
    if not unique_sources:
        logger.warning(
            "Agent[%s] retrieve query=%r CONFIGURED=%s RESULT: 0 chunks (no matching documents)",
            agent_slug, query, source_ids,
        )
    else:
        logger.warning(
            "Agent[%s] retrieve query=%r CONFIGURED=%s RESULT: %d chunks from %d source(s): %s",
            agent_slug, query, source_ids, len(chunks), len(unique_sources),
            ", ".join(f"{sid[:8]}...={title}" for sid, title in sorted(source_summary.items())),
        )
    if not chunks:
        return "", []
    lines = ["### Retrieved Context\n"]
    sources = []
    for c in chunks:
        lines.append(f"[{c.rank}] {c.source_title}\n{c.text[:1000]}")
        sources.append({"rank": c.rank, "title": c.source_title, "id": c.source_id, "url": c.source_url})
    return "\n\n---\n\n".join(lines), sources


_FALLBACK_PROMPT = "You are a helpful assistant for an internal company platform."


def make_agent_node(
    spec: AgentSpec,
    source_ids: list[str] | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
):
    """
    Build an agent node with adaptive token budget management.
    
    Args:
        spec: Agent specification
        source_ids: List of source IDs to filter by, or None for all sources
        model: Model to use, or None for default
        system_prompt: System prompt to use, or None for default
    
    Returns:
        Agent node function
    """
    llm = get_chat_model(model or spec.default_model)
    prompt = system_prompt or spec.system_prompt or _FALLBACK_PROMPT
    model_name = model or spec.default_model
    context_window = resolve_context_window(model_name)

    async def node(state: AgentState) -> dict:
        """
        Agent node function that processes messages and returns a response.
        
        Args:
            state: The current state of the graph
            
        Returns:
            A dictionary containing the response and sources
        """
        mode = state.get("mode") or "auto"
        profile = get_mode_profile(mode)

        last_user_msg = ""
        for m in reversed(state["messages"]):
            if getattr(m, "type", None) == "human" or getattr(m, "role", None) == "user":
                last_user_msg = str(getattr(m, "content", ""))
                break

        context = ""
        sources: list[dict] = []
        if profile.retrieval_enabled and "retrieve" in spec.tools:
            context, sources = await _retrieve_for_agent(last_user_msg, source_ids, agent_slug=spec.slug)
            retrieval_budget = profile.effective_limits(context_window)["retrieval"]
            context = clamp_retrieval_context(context, retrieval_budget)

        system_msg = SystemMessage(content=prompt)
        system_tokens = llm.get_num_tokens(system_msg.content or "")

        if mode == "auto":
            mode = auto_select_mode(last_user_msg)
            logger.info("Auto-selected mode=%s for query=%r", mode, last_user_msg[:60])

        mode_suffix = ""
        if mode == "quick":
            mode_suffix = (
                "\n\nProvide a quick, concise answer. "
                "Use only the most relevant sources and keep citations minimal."
            )
        elif mode == "mid":
            mode_suffix = (
                "\n\nProvide a balanced, well-reasoned answer. "
                "Use available sources and cite where relevant."
            )
        elif mode == "deep":
            mode_suffix = (
                "\n\nThink step-by-step. Analyze deeply, verify against sources, and cite. "
                "If the first search is insufficient, use the search tool again before answering."
            )
        if mode_suffix:
            system_msg = SystemMessage(content=prompt + mode_suffix)
            system_tokens = llm.get_num_tokens(system_msg.content or "")

        retrieval_tokens = llm.get_num_tokens(context) if context else 0
        history_budget = profile.history_budget_after(
            context_window, system_tokens, retrieval_tokens
        )

        trimmed_history = trim_history(state["messages"], history_budget, llm)

        messages = [system_msg]
        if context:
            messages.append(SystemMessage(content=context))
        messages.extend(trimmed_history)

        logger.info(
            "mode=%s agent=%s model=%s window=%s history=%d->%d sys=%d ctx=%d hist_budget=%d",
            mode, spec.slug, model_name, context_window,
            len(state["messages"]), len(trimmed_history),
            system_tokens, retrieval_tokens, history_budget,
        )

        response = await llm.ainvoke(messages)
        response_text = str(getattr(response, "content", response))
        cited_ranks = {int(m) for m in re.findall(r"\[(\d+)\]", response_text)}
        filtered_sources = [s for s in sources if s["rank"] in cited_ranks] if cited_ranks else sources
        return {"messages": [response], "sources": filtered_sources}

    node.__name__ = f"{spec.slug}_agent"
    return node


def build_graph(checkpointer=None, agent_registry: dict[str, AgentSpec] | None = None, agent_settings: dict[str, dict] | None = None):
    """
    Build the graph.

    Args:
        checkpointer: Checkpointer for state management
        agent_registry: Dictionary of agent specs (slug -> AgentSpec)
        agent_settings: Dictionary of agent runtime settings (slug -> config dict)

    Returns:
        Compiled graph
    """
    registry = agent_registry or {}
    settings_map = agent_settings or {}
    default_agent = next(iter(registry.keys()), "") if registry else ""

    builder = StateGraph(AgentState)
    for slug, spec in registry.items():
        cfg = settings_map.get(slug, {})
        source_ids = cfg.get("connected_sources")

        raw_cfg_sources = source_ids
        if source_ids is None:
            source_ids = None if slug == default_agent else []
            logger.warning("Agent[%s]: connected_sources was null, resolved to %s (first_agent=%s)", slug, source_ids, default_agent)
        elif slug == default_agent and source_ids == []:
            source_ids = None
            logger.warning("Agent[%s]: first agent with empty connected_sources, resolved to None (all sources)", slug)
        model = cfg.get("model") or None
        system_prompt = cfg.get("system_prompt") or None
        logger.warning(
            "Agent[%s] graph config: model=%s connected_sources=%s (raw_cfg=%s) prompt_override=%s tools=%s",
            slug, model, source_ids, raw_cfg_sources, bool(system_prompt), spec.tools,
        )
        builder.add_node(slug, make_agent_node(spec, source_ids=source_ids, model=model, system_prompt=system_prompt))
        builder.add_edge(slug, END)

    builder.add_conditional_edges(
        START,
        lambda state: state.get("current_agent", default_agent),
        {slug: slug for slug in registry},
    )
    return builder.compile(checkpointer=checkpointer)
