import asyncio
import json
import logging
import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph

from app.agents.context import (
    auto_select_mode,
    get_mode_profile,
    resolve_context_window,
    trim_history,
)
from app.agents.llm import get_chat_model
from app.agents.registry import AgentSpec
from app.agents.state import AgentState
from app.agents.tools import retrieve, web_search
from app.agents.tools_jira import create_jira_ticket

logger = logging.getLogger(__name__)

_TOOL_REGISTRY = {"retrieve": retrieve, "web_search": web_search, "create_jira_ticket": create_jira_ticket}

_FALLBACK_PROMPT = "You are a helpful assistant for an internal company platform."


def _clean_citations(text: str) -> str:
    """Deduplicate adjacent duplicate citations like [1][1] → [1] and [1], [1] → [1]."""
    while True:
        new_text = re.sub(r"(\[\d+\])(?:\s*,\s*|\s*)\1", r"\1", text)
        if new_text == text:
            break
        text = new_text
    return text


async def _expand_query(query: str, model: str = "gpt-5-nano") -> str:
    """Rewrite a vague/short user query into a precise search query for RAG."""
    if not query or len(query.split()) < 3:
        return query
    llm = get_chat_model(model, temperature=0.1)
    prompt = (
        f"Rewrite the following user question into a concise, keyword-rich search query. "
        f"Keep the original meaning but use specific keywords. "
        f"Keep it under 15 words.\n\n"
        f"User question: {query}\nSearch query:"
    )
    response = await llm.ainvoke([SystemMessage(content=prompt)])
    expanded = str(getattr(response, "content", response)).strip()
    return expanded if expanded else query


def _render_template(template: str, variables: dict) -> str:
    """Render {{path.to.var}} placeholders in a template string."""
    def _resolve(path: str) -> str:
        parts = path.split(".")
        val = variables
        for p in parts:
            if isinstance(val, dict) and p in val:
                val = val[p]
            else:
                return ""
        return str(val) if val is not None else ""

    pattern = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")
    return pattern.sub(lambda m: _resolve(m.group(1)), template)


def _resolve_source_expression(source: str | None, variables: dict) -> str:
    """Resolve a variable path such as input.query or step_1.output."""
    if not source:
        return ""
    return _render_template(f"{{{{{source}}}}}", variables)


def _build_step_prompt(node_def: dict, variables: dict, step_id: str) -> str:
    """Build the user-facing prompt for a workflow step."""
    prompt_template = node_def.get("prompt_template")
    if prompt_template:
        return _render_template(str(prompt_template), variables)

    label = node_def.get("label") or step_id
    instructions = str(node_def.get("instructions") or "").strip()
    inputs = node_def.get("inputs") or []
    outputs = node_def.get("outputs") or []
    output_var = node_def.get("output_var", "output")

    lines: list[str] = [f"You are executing the workflow step '{label}'."]
    if instructions:
        lines.append(f"Instructions:\n{instructions}")

    if inputs:
        input_lines = []
        for item in inputs:
            name = str(item.get("name") or "input")
            source = item.get("source") or f"input.{name}"
            value = _resolve_source_expression(source, variables)
            desc = str(item.get("description") or "").strip()
            line = f"- {name}: {value}"
            if desc:
                line += f" ({desc})"
            input_lines.append(line)
        lines.append("Inputs:\n" + "\n".join(input_lines))

    if outputs:
        output_lines = []
        for item in outputs:
            name = str(item.get("name") or "output")
            desc = str(item.get("description") or "").strip()
            line = f"- {name}"
            if desc:
                line += f" ({desc})"
            output_lines.append(line)
        lines.append("Expected outputs:\n" + "\n".join(output_lines))
    else:
        lines.append(f"Expected output: {output_var}")

    lines.append("Respond with the most useful result for this step.")
    return "\n\n".join(lines)


async def _invoke_agent_direct(
    spec: AgentSpec,
    source_ids: list[str] | None,
    model: str | None,
    system_prompt: str | None,
    user_prompt: str,
    registry: dict[str, AgentSpec] | None,
) -> str:
    """Directly invoke an agent LLM (no tool loop) and return its text output."""
    llm = get_chat_model(model or spec.default_model)
    prompt = system_prompt or spec.system_prompt or _FALLBACK_PROMPT
    model_name = model or spec.default_model
    context_window = resolve_context_window(model_name)

    dynamic_prompt = prompt

    system_msg = SystemMessage(content=dynamic_prompt)
    system_tokens = llm.get_num_tokens(system_msg.content or "")

    profile = get_mode_profile("auto")
    history_budget = profile.history_budget_after(context_window, system_tokens, 0)

    messages = [system_msg, HumanMessage(content=user_prompt)]
    trimmed = trim_history(messages, history_budget, llm)
    final_messages = [system_msg] + list(trimmed)[1:] if len(trimmed) > 1 else messages

    logger.info("Workflow direct invoke agent=%s model=%s", spec.slug, model_name)
    response = await llm.ainvoke(final_messages)
    raw_text = str(getattr(response, "content", response))
    return _clean_citations(raw_text)


async def _execute_single_step(
    node_def: dict,
    variables: dict,
    step_id: str,
    registry: dict[str, AgentSpec],
    settings_map: dict[str, dict],
) -> tuple[str, dict]:
    """Execute a single workflow node and return (step_id, step_values)."""
    agent_slug = node_def["agent_slug"]
    inputs = node_def.get("inputs") or []
    outputs = node_def.get("outputs") or []
    output_var = node_def.get("output_var", "output")

    rendered = _build_step_prompt(node_def, variables, step_id)
    logger.info("Workflow step=%s agent=%s prompt_len=%d", step_id, agent_slug, len(rendered))

    sub_spec = registry.get(agent_slug)
    if sub_spec is None:
        result_text = f"[Error: agent '{agent_slug}' not found]"
    else:
        cfg = settings_map.get(agent_slug, {})
        result_text = await _invoke_agent_direct(
            spec=sub_spec,
            source_ids=cfg.get("connected_sources") or [],
            model=cfg.get("model"),
            system_prompt=cfg.get("system_prompt"),
            user_prompt=rendered,
            registry=registry,
        )

    step_values: dict = {output_var: result_text}
    resolved_inputs: dict[str, str] = {}
    for item in inputs:
        name = str(item.get("name") or "input")
        source = item.get("source") or f"input.{name}"
        resolved_inputs[name] = _resolve_source_expression(source, variables)
    if resolved_inputs:
        step_values["inputs"] = resolved_inputs

    resolved_outputs: dict[str, str] = {output_var: result_text}
    for item in outputs:
        name = str(item.get("name") or "output")
        resolved_outputs[name] = result_text
    step_values["outputs"] = resolved_outputs

    logger.warning("Workflow step=%s INPUTS: %r", step_id, resolved_inputs)
    logger.warning("Workflow step=%s OUTPUTS: %r", step_id, list(resolved_outputs.keys()))
    logger.info("Workflow step=%s output_len=%d", step_id, len(result_text))
    return step_id, step_values


async def _execute_workflow(
    workflow_def: dict,
    user_message: str,
    registry: dict[str, AgentSpec],
    settings_map: dict[str, dict],
) -> str:
    """Execute a workflow DAG, running independent nodes in parallel."""
    nodes = {n["id"]: n for n in workflow_def.get("nodes", [])}
    edges = workflow_def.get("edges", [])
    input_schema = workflow_def.get("input_schema", [])

    adj: dict[str, list[str]] = {n_id: [] for n_id in nodes}
    in_degree: dict[str, int] = {n_id: 0 for n_id in nodes}
    for e in edges:
        src, tgt = e.get("source"), e.get("target")
        if src in adj and tgt in in_degree:
            adj[src].append(tgt)
            in_degree[tgt] += 1

    levels: list[list[str]] = []
    remaining = set(nodes.keys())
    while remaining:
        level = [n_id for n_id in remaining if in_degree[n_id] == 0]
        if not level:
            raise ValueError("Workflow contains a cycle")
        levels.append(level)
        for n_id in level:
            remaining.discard(n_id)
            for nxt in adj.get(n_id, []):
                in_degree[nxt] -= 1

    variables: dict = {"input": {}}
    if user_message:
        variables["input"]["query"] = user_message
    if input_schema and user_message:
        variables["input"][input_schema[0]] = user_message
        for name in input_schema[1:]:
            variables["input"].setdefault(name, "")

    for level in levels:
        tasks = [
            _execute_single_step(nodes[sid], variables, sid, registry, settings_map)
            for sid in level
        ]
        results = await asyncio.gather(*tasks)
        for sid, step_values in results:
            variables[sid] = step_values

    final_template = workflow_def.get("output", "")
    if not final_template and levels:
        last_level = levels[-1]
        if len(last_level) == 1:
            last_step = nodes[last_level[0]]
            final_template = f"{{{{{last_level[0]}.{last_step.get('output_var', 'output')}}}}}"
        else:
            parts = []
            for sid in last_level:
                out_var = nodes[sid].get("output_var", "output")
                parts.append(f"{{{{{sid}.{out_var}}}}}")
            final_template = "\n\n".join(parts)
    
    logger.warning("Workflow execution template: %r", final_template)
    logger.warning("Workflow execution variables keys: %r", list(variables.keys()))
    for k, v in variables.items():
        if k != "input":
            logger.warning("Workflow execution variable %s content: %r", k, list(v.keys()) if isinstance(v, dict) else type(v).__name__)

    rendered = _render_template(final_template, variables)
    
    if not rendered.strip() and levels:
        last_level = levels[-1]
        logger.warning("Rendered output was empty. Falling back to last topological level nodes: %s", last_level)
        if len(last_level) == 1:
            last_step = nodes[last_level[0]]
            out_var = last_step.get("output_var") or "output"

            step_vars = variables.get(last_level[0], {})
            if out_var not in step_vars:
                keys = [k for k in step_vars.keys() if k not in ("inputs", "outputs")]
                if keys:
                    out_var = keys[0]
            fallback_template = f"{{{{{last_level[0]}.{out_var}}}}}"
            logger.warning("Using fallback template: %r", fallback_template)
            rendered = _render_template(fallback_template, variables)
        else:
            parts = []
            for sid in last_level:
                out_var = nodes[sid].get("output_var") or "output"
                step_vars = variables.get(sid, {})
                if out_var not in step_vars:
                    keys = [k for k in step_vars.keys() if k not in ("inputs", "outputs")]
                    if keys:
                        out_var = keys[0]
                val = _render_template(f"{{{{{sid}.{out_var}}}}}", variables)
                if val:
                    parts.append(val)
            rendered = "\n\n".join(parts)

    logger.warning("Workflow execution rendered output_len: %d", len(rendered))
    return rendered


def make_agent_node(
    spec: AgentSpec,
    source_ids: list[str] | None = None,
    model: str | None = None,
    system_prompt: str | None = None,
    retrieval_top_k: int = 5,
    registry: dict[str, AgentSpec] | None = None,
    workflow_def: dict | None = None,
    settings_map: dict[str, dict] | None = None,
    agent_type: str = "standard",
    research_config: dict | None = None,
):
    """Build an agent node that reasons and may emit tool_calls (ReAct pattern).

    Args:
        spec: Agent specification
        source_ids: List of source IDs to filter by, or None for all sources
        model: Model to use, or None for default
        system_prompt: System prompt to use, or None for default
        retrieval_top_k: Number of chunks to retrieve (unused here, passed to tools_node)
        workflow_def: Optional workflow definition to execute instead of normal reasoning
        settings_map: Agent settings map for sub-agent invocation in workflows

    Returns:
        Agent node function
    """
    if agent_type == "deep_research":
        from app.agents.deep_research import DeepResearchConfig, run_deep_research

        dr_config = DeepResearchConfig.from_dict(research_config)
        if source_ids and not dr_config.connected_sources:
            dr_config.connected_sources = source_ids

        async def _deep_research_node(state: AgentState) -> dict:
            last_user_msg = ""
            for m in reversed(state["messages"]):
                if getattr(m, "type", None) == "human" or getattr(m, "role", None) == "user":
                    last_user_msg = str(getattr(m, "content", ""))
                    break

            logger.info("Deep research agent=%s starting research", spec.slug)
            report_text = ""
            async for event in run_deep_research(
                user_message=last_user_msg,
                config=dr_config,
                thread_id=f"{spec.slug}-research",
            ):
                if event.get("type") == "report":
                    report_text = event["content"]
                elif event.get("type") == "clarification":
                    question = event.get("question", "")
                    logger.info("Deep research agent=%s clarification needed (SSE mode - auto-answering)", spec.slug)

                    async for event2 in run_deep_research(
                        user_message=last_user_msg,
                        config=dr_config,
                        thread_id=f"{spec.slug}-research-resume",
                        resume_answer="Please proceed with a broad research approach covering all aspects mentioned.",
                    ):
                        if event2.get("type") == "report":
                            report_text = event2["content"]
                        elif event2.get("type") == "error":
                            report_text = f"Deep research failed: {event2.get('detail', 'unknown error')}"
                elif event.get("type") == "error":
                    report_text = f"Deep research failed: {event.get('detail', 'unknown error')}"
                    logger.error("Deep research error: %s", event.get("detail"))

            if not report_text:
                report_text = "Deep research completed but no report was generated."

            logger.info("Deep research agent=%s report_len=%d", spec.slug, len(report_text))
            return {
                "messages": [AIMessage(content=report_text)],
                "response_text": report_text,
                "sources": state.get("sources"),
                "step_count": (state.get("step_count") or 0) + 1,
                "mode": state.get("mode") or "auto",
            }

        _deep_research_node.__name__ = f"{spec.slug}_deep_research"
        return _deep_research_node

    llm = get_chat_model(model or spec.default_model)
    prompt = system_prompt or spec.system_prompt or _FALLBACK_PROMPT
    model_name = model or spec.default_model
    context_window = resolve_context_window(model_name)

    agent_tools = []

    if source_ids:
        agent_tools.append(_TOOL_REGISTRY["retrieve"])
    for t in (spec.tools or []):
        if t in _TOOL_REGISTRY and t != "retrieve":
            agent_tools.append(_TOOL_REGISTRY[t])

    llm_with_tools = llm.bind_tools(agent_tools) if agent_tools else llm

    async def node(state: AgentState) -> dict:

        if workflow_def and workflow_def.get("enabled"):
            last_user_msg = ""
            for m in reversed(state["messages"]):
                if getattr(m, "type", None) == "human" or getattr(m, "role", None) == "user":
                    last_user_msg = str(getattr(m, "content", ""))
                    break
            try:
                result_text = await _execute_workflow(
                    workflow_def=workflow_def,
                    user_message=last_user_msg,
                    registry=registry or {},
                    settings_map=settings_map or {},
                )
                logger.warning("Workflow agent=%s response_text_len=%d preview=%s", spec.slug, len(result_text), result_text[:1000])
                return {
                    "messages": [AIMessage(content=result_text)],
                    "response_text": result_text,
                    "sources": state.get("sources"),
                    "step_count": (state.get("step_count") or 0) + 1,
                    "mode": state.get("mode") or "auto",
                }
            except Exception:
                logger.exception("Workflow execution failed for agent=%s", spec.slug)
                err_text = "Workflow execution failed. Please check the workflow configuration."
                logger.warning("Workflow agent=%s error_text=%s", spec.slug, err_text)
                return {
                    "messages": [AIMessage(content=err_text)],
                    "response_text": err_text,
                    "sources": state.get("sources"),
                    "step_count": (state.get("step_count") or 0) + 1,
                    "mode": state.get("mode") or "auto",
                }

        mode = state.get("mode") or "auto"
        profile = get_mode_profile(mode)

        last_user_msg = ""
        for m in reversed(state["messages"]):
            if getattr(m, "type", None) == "human" or getattr(m, "role", None) == "user":
                last_user_msg = str(getattr(m, "content", ""))
                break

        dynamic_prompt = prompt
        user_allowed = state.get("user_allowed_slugs")
        accessible_names = [registry[slug].name for slug in (user_allowed or []) if slug in registry]
        registry_names = [spec.name for spec in registry.values()]
        logger.info("Agent access names: %s", accessible_names)
        logger.info("Agent registry names: %s", registry_names)
        if user_allowed is not None and spec.is_orchestrator:
            accessible = [slug for slug in user_allowed if slug != spec.slug]
            if accessible:
                lines = "\n".join(f"- @{slug}: {registry[slug].description}" for slug in accessible if slug in registry)
                access_block = (
                    "MANDATORY ACCESS RESTRICTION - You may ONLY mention, route to, or acknowledge the following specialist agents. "
                    "If a user asks about a topic belonging to a specialist NOT on this list, you must NOT mention that specialist or suggest routing to them. "
                    "Instead, answer from your own knowledge if possible, or politely explain you cannot help with that specialist topic.\n\n"
                    f"Allowed specialists:\n{lines}\n\n"
                    "Any reference to specialists outside the Allowed specialists list is strictly forbidden.\n\n"
                    "WHEN the user asks what you can help with, how you can help, or what agents are available, you MUST ALWAYS include a bullet list of the Allowed specialists with a brief description. "
                    "This is non-optional. Do NOT give vague answers like 'hand off to the right expert.' Name the specific agents the user can access.\n\n"
                    "Example of a correct response when asked 'how can you help me':\n"
                    "'I can help with general questions and tasks. You also have access to these specialists:'\n"
                    f"{lines}\n\n"
                )
            else:
                access_block = (
                    "MANDATORY ACCESS RESTRICTION - This user has access to NO specialist agents. "
                    "You must NEVER mention any specialist agent (@it, @hr, @finance, or any other). "
                    "Answer all questions from your own knowledge. If a topic clearly requires a specialist you cannot access, politely explain you don't have access to that specialist and suggest contacting an administrator.\n\n"
                )
            dynamic_prompt = access_block + dynamic_prompt

        history = state.get("orchestrator_history") or []
        if spec.is_orchestrator and history:
            synth_lines = ["\n\n=== CHILD AGENT OUTPUTS ==="]
            for entry in history:
                child = entry.get("agent", "unknown")
                output = entry.get("output", "")[:1500]
                synth_lines.append(f"\n--- @{child} ---\n{output}")
            synth_lines.append(
                "\n=== INSTRUCTIONS ===\n"
                "You are the orchestrator supervisor. The above outputs are from child specialist agents you delegated to.\n"
                "Synthesize their findings into a single, coherent, well-structured final answer for the user.\n"
                "Do not mention internal delegation unless relevant. Provide a polished, complete response.\n"
            )
            dynamic_prompt = dynamic_prompt + "\n".join(synth_lines)
            logger.warning("Agent[%s] synthesizing with %d child outputs", spec.slug, len(history))

        logger.info("Agent[%s] final system prompt length: %d", spec.slug, len(dynamic_prompt))

        system_msg = SystemMessage(content=dynamic_prompt)
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
            system_msg = SystemMessage(content=dynamic_prompt + mode_suffix)
            system_tokens = llm.get_num_tokens(system_msg.content or "")

        retrieval_tokens = 0
        history_budget = profile.history_budget_after(
            context_window, system_tokens, retrieval_tokens
        )

        trimmed_history = trim_history(state["messages"], history_budget, llm)

        messages = [system_msg]
        messages.extend(trimmed_history)

        logger.info(
            "mode=%s agent=%s model=%s window=%s history=%d->%d sys=%d ctx=%d hist_budget=%d step=%s",
            mode, spec.slug, model_name, context_window,
            len(state["messages"]), len(trimmed_history),
            system_tokens, retrieval_tokens, history_budget,
            state.get("step_count", 0),
        )

        response = await llm_with_tools.ainvoke(messages)
        raw_text = str(getattr(response, "content", response))
        cleaned_text = _clean_citations(raw_text)
        if cleaned_text != raw_text and hasattr(response, "content"):
            msg_cls = response.__class__
            kwargs: dict = {"content": cleaned_text}
            for attr in ("tool_calls", "response_metadata", "usage_metadata", "id", "name"):
                if hasattr(response, attr):
                    kwargs[attr] = getattr(response, attr)
            response = msg_cls(**kwargs)
        logger.warning("Agent=%s response_text_len=%d preview=%s", spec.slug, len(raw_text), raw_text[:1000])

        result = {
            "messages": [response],
            "response_text": _clean_citations(raw_text),
            "sources": state.get("sources"),
            "step_count": (state.get("step_count") or 0) + 1,
            "mode": mode,
        }

        orchestrator = state.get("orchestrator_agent")
        if orchestrator and orchestrator != spec.slug:
            history = list(state.get("orchestrator_history") or [])
            history.append({"agent": spec.slug, "output": cleaned_text})
            result["orchestrator_history"] = history
            logger.info("Recorded orchestrator_history entry for child=%s", spec.slug)

        return result

    node.__name__ = f"{spec.slug}_agent"
    return node


def _has_tool_calls(state: AgentState) -> bool:
    """Check if the last message contains tool calls."""
    if not state["messages"]:
        return False
    last = state["messages"][-1]
    tc = getattr(last, "tool_calls", None)
    return bool(tc)


def _extract_mention(text: str, registry: dict[str, AgentSpec]) -> str | None:
    """Look for @slug in user text and return the matched agent slug if valid"""
    idx = text.find("@")
    if idx == -1:
        return None

    slug_chars = []
    for ch in text[idx + 1:]:
        if ch.isalnum() or ch in "_-":
            slug_chars.append(ch)
        else:
            break
    slug = "".join(slug_chars).lower()
    if slug in registry:
        return slug
    return None


async def _llm_route(user_msg: str, current_agent: str, registry: dict[str, AgentSpec]) -> str:
    """Use gpt-5-nano to classify intent and pick the best agent slug."""
    registry_slugs = sorted(registry.keys())
    general_slugs = [s for s, sp in registry.items() if sp.is_router or sp.is_orchestrator]
    general_slug = general_slugs[0] if general_slugs else ""

    agent_lines = "\n".join(
        f"  {slug}: {spec.name or slug} - {spec.description or ''}" for slug, spec in registry.items()
    )

    prompt = (
        "You are a router. Pick the exact agent slug that should handle the user query.\n\n"
        f"Valid slugs (pick one exactly): {registry_slugs}\n\n"
        f"{agent_lines}\n\n"
        "Rules:\n"
        "- Greetings, small talk, broad or cross-domain questions → pick the general/router agent.\n"
        "- Domain-specific questions (IT, HR, finance) → pick the matching specialist.\n"
        "- Short follow-ups ('thanks', 'ok', 'what about it?') → stay with current_agent.\n"
        "- Return ONLY the slug, nothing else. No quotes, no punctuation.\n\n"
        f"current_agent: {current_agent or 'none'}\n"
        f"user: {user_msg}\n\n"
        "slug:"
    )

    llm = get_chat_model("gpt-5-nano", temperature=0.0)
    response = await llm.ainvoke([SystemMessage(content=prompt)])
    text = str(getattr(response, "content", response)).strip().lower()

    if text in registry:
        logger.info("LLM router: %s", text)
        return text

    if current_agent in registry:
        logger.info("LLM router fallback: staying with %s", current_agent)
        return current_agent

    logger.info("LLM router fallback: general %s", general_slug)
    return general_slug if general_slug in registry else ""


async def _orchestrator_delegate(
    user_msg: str,
    orchestrator_slug: str,
    allowed_registry: dict[str, AgentSpec],
    history: list[dict],
) -> str:
    """Ask an LLM whether to delegate to another child or synthesize."""
    agent_lines = "\n".join(
        f"- {slug}: {spec.description}" for slug, spec in allowed_registry.items()
    )
    history_text = ""
    for entry in history:
        child = entry.get("agent", "unknown")
        output = entry.get("output", "")[:800]
        history_text += f"\n--- Child: @{child} ---\n{output}\n"

    prompt = (
        f"You are an orchestrator supervisor ({orchestrator_slug}).\n\n"
        f"Original user request: {user_msg}\n\n"
        f"Child agents already called and their outputs:\n{history_text}\n\n"
        f"Available child agents:\n{agent_lines}\n\n"
        f"Your task: Decide what to do next.\n"
        f"1. If the user request requires more specialist input, return the EXACT agent slug to delegate to.\n"
        f"2. If all necessary information has been gathered, return 'SYNTHESIZE' (all caps).\n"
        f"3. If the query is simple enough to answer directly, return 'SYNTHESIZE'.\n\n"
        f"Return ONLY the agent slug or the word SYNTHESIZE. No explanation."
    )
    llm = get_chat_model("gpt-5-nano", temperature=0.1)
    response = await llm.ainvoke([SystemMessage(content=prompt)])
    text = str(getattr(response, "content", response)).strip().lower()
    if text == "synthesize":
        return "SYNTHESIZE"
    if text in allowed_registry:
        return text
    return "SYNTHESIZE"


def make_router_node(
    registry: dict[str, AgentSpec],
    routes_map: dict[str, list[str]],
    orchestrator_slugs: set[str],
    default_agent: str = "general",
):
    """Build the supervisor/router node that decides which agent handles the turn.

    Supports both simple routing and orchestrator delegation loops.

    Args:
        registry: Full agent registry
        routes_map: Mapping of orchestrator slug -> list of slugs it can route to
        orchestrator_slugs: Set of slugs that are orchestrators
        default_agent: Fallback agent slug
    """

    async def node(state: AgentState) -> dict:
        forced = state.get("forced_agent")
        if forced and forced in registry:
            logger.info("Router: forced_agent=%s", forced)
            return {"current_agent": forced}

        last_user_msg = ""
        for m in reversed(state["messages"]):
            if getattr(m, "type", None) == "human" or getattr(m, "role", None) == "user":
                last_user_msg = str(getattr(m, "content", ""))
                break

        current_agent = state.get("current_agent", default_agent)
        orchestrator = state.get("orchestrator_agent") or current_agent

        if orchestrator not in orchestrator_slugs:
            return {"current_agent": current_agent}

        if orchestrator == "general":
            allowed_slugs = [slug for slug in registry if slug != "general"]
        else:
            allowed_slugs = routes_map.get(orchestrator, [])
        allowed_registry = {slug: registry[slug] for slug in allowed_slugs if slug in registry}

        if orchestrator in registry and orchestrator not in allowed_registry:
            allowed_registry[orchestrator] = registry[orchestrator]

        user_allowed = state.get("user_allowed_slugs")
        if user_allowed is not None:
            allowed_registry = {
                slug: spec for slug, spec in allowed_registry.items() if slug in user_allowed
            }

        history = state.get("orchestrator_history") or []

        if history and current_agent != orchestrator:
            last_child = history[-1].get("agent", "")
            logger.info("Router: returning from child=%s, history_count=%d", last_child, len(history))
            decision = await _orchestrator_delegate(
                last_user_msg, orchestrator, allowed_registry, history
            )
            if decision != "SYNTHESIZE" and decision in allowed_registry:
                logger.info("Router: orchestrator delegating -> %s", decision)
                return {"current_agent": decision}
            else:
                logger.info("Router: orchestrator synthesizing via %s", orchestrator)
                return {"current_agent": orchestrator}

        mention = _extract_mention(last_user_msg, allowed_registry)
        if mention:
            logger.info("Router: @mention detected -> %s", mention)
            return {"current_agent": mention}

        routed = await _llm_route(last_user_msg, current_agent, allowed_registry)
        if routed not in allowed_registry:
            routed = orchestrator

        logger.info("Router: LLM routed -> %s (msg=%r)", routed, last_user_msg[:60])
        return {"current_agent": routed}

    node.__name__ = "router"
    return node


def make_tools_node(agent_settings: dict[str, dict]):
    """Build the shared tools executor node.

    Executes tool calls from the last AI message and returns tool results.
    For retrieve, uses per-agent source_ids from agent_settings.
    """
    async def node(state: AgentState) -> dict:
        last_msg = state["messages"][-1]
        tool_calls = getattr(last_msg, "tool_calls", [])

        if not tool_calls:
            return {}

        current_agent = state.get("current_agent", "general")
        cfg = agent_settings.get(current_agent, {})
        source_ids = cfg.get("connected_sources")
        top_k = cfg.get("retrieval_top_k", 5)

        results: list[str] = []
        new_sources = list(state.get("sources") or [])

        for tc in tool_calls:
            name = tc.get("name")
            args = tc.get("args", {})

            if name == "retrieve":
                query = args.get("query", "")
                llm_sources = args.get("sources")
                resolved_sources = llm_sources if llm_sources is not None else source_ids
                if resolved_sources == []:
                    results.append("No knowledge sources are configured for this agent.")
                else:
                    expanded_query = await _expand_query(query)
                    logger.info("Expanded query: %r -> %r", query, expanded_query)
                    tool_fn = _TOOL_REGISTRY.get("retrieve")
                    result = await tool_fn.ainvoke({"query": expanded_query, "sources": resolved_sources})
                    parsed = json.loads(str(result))

                    offset = state.get("source_offset") or 0
                    if offset:
                        for src in parsed.get("sources", []):
                            src["rank"] = src.get("rank", 0) + offset

                        text = parsed["text"]
                        for src in reversed(parsed.get("sources", [])):
                            old_rank = src["rank"] - offset
                            text = text.replace(f"[{old_rank}]", f"[{src['rank']}]", 1)
                        parsed["text"] = text
                    results.append(parsed["text"])
                    new_sources.extend(parsed.get("sources", []))
                    logger.info("length of retrieved results : %s", len(results))
                    
            elif name == "web_search":
                tool_fn = _TOOL_REGISTRY.get("web_search")
                result = await tool_fn.ainvoke({"query": args.get("query", "")})
                logger.info("Web search result: %s", result)
                results.append(str(result))

            elif name == "create_jira_ticket":
                tool_fn = _TOOL_REGISTRY.get("create_jira_ticket")
                result = await tool_fn.ainvoke({
                    "summary": args.get("summary", ""),
                    "description": args.get("description", ""),
                    "issue_type": args.get("issue_type", "Task"),
                })
                logger.info("Jira ticket result: %s", result)
                results.append(str(result))
            else:
                results.append(f"Error: unknown tool '{name}'")

        tool_messages = []
        for i, tc in enumerate(tool_calls):
            tool_messages.append(ToolMessage(
                content=str(results[i]),
                tool_call_id=tc["id"],
                name=tc["name"],
            ))

        seen = set()
        deduped = []
        for s in new_sources:
            key = (s.get("rank"), s.get("id"))
            if key not in seen:
                seen.add(key)
                deduped.append(s)

        return {"messages": tool_messages, "sources": deduped}

    node.__name__ = "tools"
    return node


def make_reflect_node():
    """Build the reflection/verification node for deep mode."""
    async def node(state: AgentState) -> dict:
        last_assistant = None
        for m in reversed(state["messages"]):
            if getattr(m, "type", None) in ("ai", "assistant"):
                last_assistant = m
                break

        if last_assistant is None:
            return {"reflection_done": True, "_needs_rethink": False}

        sources = state.get("sources", [])
        source_text = "\n".join(
            f"[{s.get('rank')}] {s.get('title')}" for s in sources
        ) if sources else "No sources retrieved."

        prompt = f"""
            You are a verifier. Review this answer and its sources.
            Answer: {last_assistant.content}
            Sources: {source_text}

            Is this answer:
            1. Fully supported by the sources (if sources exist)?
            2. Complete (no missing key information)?
            3. Correctly cited?

            Return ONLY one word: SATISFACTORY or INCOMPLETE.
        """

        llm = get_chat_model("gpt-5-nano", temperature=0.1)
        verdict = await llm.ainvoke([SystemMessage(content=prompt)])
        text = str(getattr(verdict, "content", verdict)).strip().upper()

        if "INCOMPLETE" in text:
            return {
                "messages": [SystemMessage(
                    content="The previous answer was flagged as incomplete. Search for more information and provide a more thorough response with better citations."
                )],
                "reflection_done": True,
                "_needs_rethink": True,
            }

        return {"reflection_done": True, "_needs_rethink": False}

    node.__name__ = "reflect"
    return node


def _route_from_agent(state: AgentState) -> str:
    """Route from an agent node to tools, reflect, router, or END."""
    if _has_tool_calls(state):
        return "tools"

    mode = state.get("mode") or "auto"
    step_count = state.get("step_count") or 0
    if step_count > 8:
        logger.warning("Max steps reached, ending turn")
        return END

    if mode == "deep" and not state.get("reflection_done"):
        return "reflect"

    current_agent = state.get("current_agent")
    orchestrator = state.get("orchestrator_agent")
    if orchestrator and current_agent and current_agent != orchestrator:
        history = state.get("orchestrator_history") or []
        if len(history) < 3:
            logger.info("Routing child %s back to orchestrator router", current_agent)
            return "router"
        else:
            logger.warning("Max orchestrator delegations reached, ending turn")

    return END


def build_graph(
    checkpointer=None,
    agent_registry: dict[str, AgentSpec] | None = None,
    agent_settings: dict[str, dict] | None = None,
    workflows: dict[str, dict] | None = None,
):
    """
    Build the graph.

    Args:
        checkpointer: Checkpointer for state management
        agent_registry: Dictionary of agent specs (slug -> AgentSpec)
        agent_settings: Dictionary of agent runtime settings (slug -> config dict)
        workflows: Dictionary of agent slug -> workflow definition dict

    Returns:
        Compiled graph
    """
    registry = agent_registry or {}
    settings_map = agent_settings or {}
    workflow_map = workflows or {}
    default_agent = "general" if "general" in registry else (next(iter(registry.keys()), "") if registry else "")

    builder = StateGraph(AgentState)

    routes_map: dict[str, list[str]] = {}
    orchestrator_slugs: set[str] = set()
    for slug, spec in registry.items():
        if spec.is_router or spec.is_orchestrator:
            orchestrator_slugs.add(slug)
            routes_map[slug] = spec.routes_to or []

    builder.add_node("router", make_router_node(registry, routes_map=routes_map, orchestrator_slugs=orchestrator_slugs, default_agent=default_agent))
    builder.add_edge(START, "router")

    builder.add_node("tools", make_tools_node(settings_map))
    builder.add_node("reflect", make_reflect_node())

    for slug, spec in registry.items():
        cfg = settings_map.get(slug, {})
        source_ids = cfg.get("connected_sources")

        if source_ids is None:
            source_ids = []
            logger.warning("Agent[%s]: connected_sources was null, resolved to [] (no sources)", slug)
        model = cfg.get("model") or None
        system_prompt = cfg.get("system_prompt") or None
        retrieval_top_k = cfg.get("retrieval_top_k", 5)
        logger.warning(
            "Agent[%s] graph config: model=%s connected_sources=%s retrieval_top_k=%s prompt_override=%s tools=%s",
            slug, model, source_ids, retrieval_top_k, bool(system_prompt), spec.tools,
        )
        agent_type = cfg.get("agent_type") or spec.agent_type or "standard"
        research_config = cfg.get("research_config") or spec.research_config
        builder.add_node(
            slug,
            make_agent_node(
                spec,
                source_ids=source_ids,
                model=model,
                system_prompt=system_prompt,
                retrieval_top_k=retrieval_top_k,
                registry=registry,
                workflow_def=workflow_map.get(slug),
                settings_map=settings_map,
                agent_type=agent_type,
                research_config=research_config,
            ),
        )

        builder.add_conditional_edges(
            slug,
            _route_from_agent,
            {"tools": "tools", "reflect": "reflect", "router": "router", END: END}
        )

    builder.add_conditional_edges(
        "tools",
        lambda state: state.get("current_agent", default_agent),
        {slug: slug for slug in registry}
    )

    builder.add_conditional_edges(
        "reflect",
        lambda state: state.get("current_agent", default_agent) if state.get("_needs_rethink") else END,
        {**{slug: slug for slug in registry}, END: END}
    )

    builder.add_conditional_edges(
        "router",
        lambda state: state.get("current_agent", default_agent),
        {slug: slug for slug in registry},
    )
    return builder.compile(checkpointer=checkpointer)