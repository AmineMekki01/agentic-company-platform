"""Deep Research agent - 3-tier multi-agent research subgraph.

Architecture:
    clarify_with_user → write_research_brief → research_supervisor → final_report_generation

The supervisor subgraph delegates to parallel researcher subgraphs, each doing
ReAct-style search loops with configurable search tools (web search, internal KB, or both).
"""

import asyncio
import logging
import operator
from functools import partial
from dataclasses import dataclass, field
from typing import Annotated, Any, AsyncIterator

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    get_buffer_string,
)
from langchain_core.tools import tool
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from app.agents.deep_research_prompts import (
    CLARIFY_INSTRUCTIONS,
    COMPRESS_PROMPT,
    FINAL_REPORT_PROMPT,
    RESEARCHER_PROMPT,
    RESEARCH_BRIEF_PROMPT,
    SUPERVISOR_PROMPT,
)
from app.agents.llm import get_chat_model
from app.agents.tools import retrieve, web_search

logger = logging.getLogger(__name__)


@dataclass
class DeepResearchConfig:
    """Configuration for a deep research agent instance."""
    max_researcher_iterations: int = 5
    max_concurrent_research_units: int = 3
    max_react_tool_calls: int = 8
    clarification_model: str = "gpt-5.4-nano"
    research_model: str = "gpt-5.4"
    compression_model: str = "gpt-5.4"
    final_report_model: str = "gpt-5.4"
    search_tools: list[str] = field(default_factory=lambda: ["web_search"])
    connected_sources: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "DeepResearchConfig":
        if not data:
            return cls()
        return cls(
            max_researcher_iterations=data.get("max_researcher_iterations", 5),
            max_concurrent_research_units=data.get("max_concurrent_research_units", 3),
            max_react_tool_calls=data.get("max_react_tool_calls", 8),
            clarification_model=data.get("clarification_model", "gpt-5.4-nano"),
            research_model=data.get("research_model", "gpt-5.4"),
            compression_model=data.get("compression_model", "gpt-5.4"),
            final_report_model=data.get("final_report_model", "gpt-5.4"),
            search_tools=data.get("search_tools", ["web_search"]),
            connected_sources=data.get("connected_sources", []),
        )


class ClarifyWithUser(BaseModel):
    """Determine if user clarification is needed before research."""
    need_clarification: bool = Field(
        description="Whether the user needs to be asked a clarifying question."
    )
    question: str = Field(
        description="A question to ask the user to clarify the report scope."
    )
    verification: str = Field(
        description="Verification message that we will start research after the user has provided the necessary information."
    )


class ResearchQuestion(BaseModel):
    """Research question and brief for guiding research."""
    research_brief: str = Field(
        description="A detailed research question that will be used to guide the research."
    )


class ConductResearch(BaseModel):
    """Call this tool to conduct research on a specific topic."""
    research_topic: str = Field(
        description="The topic to research. Should be a single topic, and should be described in high detail (at least a paragraph).",
    )


class ResearchComplete(BaseModel):
    """Call this tool to indicate that the research is complete."""



def _override_reducer(current_value, new_value):
    """Reducer that allows overriding values in state."""
    if isinstance(new_value, dict) and new_value.get("type") == "override":
        return new_value.get("value", new_value)
    else:
        return operator.add(current_value, new_value)


class ResearchState(TypedDict):
    """Main state for the deep research workflow."""
    messages: Annotated[list[AnyMessage], operator.add]
    research_brief: str | None
    notes: Annotated[list[str], _override_reducer]
    final_report: str
    clarification_question: str | None
    supervisor_messages: Annotated[list[AnyMessage], _override_reducer]


class SupervisorState(TypedDict):
    """State for the research supervisor."""
    supervisor_messages: Annotated[list[AnyMessage], _override_reducer]
    research_brief: str
    notes: Annotated[list[str], _override_reducer]
    research_iterations: int


class ResearcherState(TypedDict):
    """State for individual researchers."""
    researcher_messages: Annotated[list[AnyMessage], operator.add]
    research_topic: str
    tool_call_iterations: int


class ResearcherOutputState(TypedDict):
    """Output state from individual researchers."""
    compressed_research: str
    notes: Annotated[list[str], _override_reducer]



@tool
async def think_tool(reflection: str) -> str:
    """Use this tool to reflect on your research strategy and plan next steps."""
    return f"Reflection recorded: {reflection}"


def _get_today_str() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _get_research_tools(config: DeepResearchConfig) -> list:
    """Build the list of search tools available to researchers."""
    tools = [think_tool]
    for t in config.search_tools:
        if t == "web_search":
            tools.append(web_search)
        elif t == "retrieve":
            # Wrap retrieve with pre-bound source IDs
            async def _retrieve_wrapper(query: str) -> str:
                import json
                text, srcs = await _retrieve_and_format(query, config.connected_sources)
                return json.dumps({"text": text, "sources": srcs})
            from langchain_core.tools import tool as tool_decorator
            wrapper = tool_decorator(_retrieve_wrapper)
            wrapper.name = "retrieve"
            tools.append(wrapper)
    return tools


async def _retrieve_and_format(query: str, source_ids: list[str]) -> tuple[str, list[dict]]:
    """Retrieve from internal KB and format results."""
    from app.agents.tools import _retrieve_and_format as _raf
    return await _raf(query, source_ids=source_ids)


async def clarify_with_user(state: ResearchState, dr_config: DeepResearchConfig) -> Command:
    """Analyze user messages and ask clarifying questions if needed."""
    messages = state.get("messages", [])
    model = get_chat_model(dr_config.clarification_model, temperature=0.1)

    clarification_model = model.with_structured_output(ClarifyWithUser)
    prompt_content = CLARIFY_INSTRUCTIONS.format(
        messages=get_buffer_string(messages),
        date=_get_today_str(),
    )
    response = await clarification_model.ainvoke([HumanMessage(content=prompt_content)])

    if response.need_clarification:
        question = response.question
        logger.info("Deep research: asking clarification: %s", question)
        return Command(
            goto="write_research_brief",
            update={
                "messages": [
                    AIMessage(content=question),
                ],
                "clarification_question": question,
            },
        )
    else:
        return Command(
            goto="write_research_brief",
            update={
                "messages": [AIMessage(content=response.verification)],
            },
        )


async def write_research_brief(state: ResearchState, dr_config: DeepResearchConfig) -> Command:
    """Transform user messages into a structured research brief."""
    model = get_chat_model(dr_config.research_model, temperature=0.1)
    research_model = model.with_structured_output(ResearchQuestion)

    prompt_content = RESEARCH_BRIEF_PROMPT.format(
        messages=get_buffer_string(state.get("messages", [])),
        date=_get_today_str(),
    )
    response = await research_model.ainvoke([HumanMessage(content=prompt_content)])

    supervisor_system_prompt = SUPERVISOR_PROMPT.format(
        date=_get_today_str(),
        max_concurrent_research_units=dr_config.max_concurrent_research_units,
        max_researcher_iterations=dr_config.max_researcher_iterations,
    )

    return Command(
        goto="research_supervisor",
        update={
            "research_brief": response.research_brief,
            "supervisor_messages": {
                "type": "override",
                "value": [
                    SystemMessage(content=supervisor_system_prompt),
                    HumanMessage(content=response.research_brief),
                ],
            },
        },
    )


async def supervisor(state: SupervisorState, dr_config: DeepResearchConfig) -> Command:
    """Lead research supervisor that plans and delegates to researchers."""
    model = get_chat_model(dr_config.research_model, temperature=0.3)
    lead_researcher_tools = [ConductResearch, ResearchComplete, think_tool]
    research_model = model.bind_tools(lead_researcher_tools)

    supervisor_messages = state.get("supervisor_messages", [])
    response = await research_model.ainvoke(supervisor_messages)

    return Command(
        goto="supervisor_tools",
        update={
            "supervisor_messages": [response],
            "research_iterations": state.get("research_iterations", 0) + 1,
        },
    )


async def supervisor_tools(state: SupervisorState, dr_config: DeepResearchConfig) -> Command:
    """Execute supervisor tool calls - research delegation, completion, reflection."""
    supervisor_messages = state.get("supervisor_messages", [])
    research_iterations = state.get("research_iterations", 0)
    most_recent = supervisor_messages[-1]
    tool_calls = getattr(most_recent, "tool_calls", [])

    exceeded = research_iterations > dr_config.max_researcher_iterations
    no_calls = not tool_calls
    complete = any(tc["name"] == "ResearchComplete" for tc in tool_calls)

    if exceeded or no_calls or complete:
        notes = _get_notes_from_messages(supervisor_messages)
        return Command(
            goto=END,
            update={
                "notes": notes,
                "research_brief": state.get("research_brief", ""),
            },
        )

    all_tool_messages: list[ToolMessage] = []
    update_payload: dict[str, Any] = {"supervisor_messages": []}

    think_calls = [tc for tc in tool_calls if tc["name"] == "think_tool"]
    for tc in think_calls:
        reflection = tc["args"]["reflection"]
        all_tool_messages.append(ToolMessage(
            content=f"Reflection recorded: {reflection}",
            name="think_tool",
            tool_call_id=tc["id"],
        ))

    research_calls = [tc for tc in tool_calls if tc["name"] == "ConductResearch"]
    if research_calls:
        allowed = research_calls[:dr_config.max_concurrent_research_units]
        overflow = research_calls[dr_config.max_concurrent_research_units:]

        researcher_builder = _build_researcher_subgraph(dr_config)
        researcher_subgraph = researcher_builder.compile()

        research_tasks = [
            researcher_subgraph.ainvoke({
                "researcher_messages": [HumanMessage(content=tc["args"]["research_topic"])],
                "research_topic": tc["args"]["research_topic"],
                "tool_call_iterations": 0,
            })
            for tc in allowed
        ]
        results = await asyncio.gather(*research_tasks, return_exceptions=True)

        for obs, tc in zip(results, allowed):
            if isinstance(obs, Exception):
                logger.exception("Researcher subgraph failed")
                content = f"Research error: {obs}"
            else:
                content = obs.get("compressed_research", "Error: no research output")
            all_tool_messages.append(ToolMessage(
                content=content,
                name="ConductResearch",
                tool_call_id=tc["id"],
            ))

        for tc in overflow:
            all_tool_messages.append(ToolMessage(
                content=f"Error: exceeded max concurrent research units ({dr_config.max_concurrent_research_units}). "
                        f"Please conduct remaining research in a later iteration.",
                name="ConductResearch",
                tool_call_id=tc["id"],
            ))

    update_payload["supervisor_messages"] = all_tool_messages
    return Command(goto="supervisor", update=update_payload)


def _get_notes_from_messages(messages: list[AnyMessage]) -> list[str]:
    """Extract research notes from tool messages in supervisor conversation."""
    notes = []
    for msg in messages:
        if isinstance(msg, ToolMessage) and msg.name == "ConductResearch":
            notes.append(str(msg.content))
    return notes


async def researcher(state: ResearcherState, dr_config: DeepResearchConfig) -> Command:
    """Individual researcher conducting focused research on a specific topic."""
    tools = _get_research_tools(dr_config)
    if len(tools) <= 1:  # only think_tool
        raise ValueError(
            "No search tools configured for deep research. "
            "Enable web_search or retrieve in research_config."
        )

    model = get_chat_model(dr_config.research_model, temperature=0.3)
    research_model = model.bind_tools(tools)

    researcher_messages = state.get("researcher_messages", [])
    system_prompt = RESEARCHER_PROMPT.format(
        mcp_prompt="",
        date=_get_today_str(),
    )
    messages = [SystemMessage(content=system_prompt)] + researcher_messages
    response = await research_model.ainvoke(messages)

    return Command(
        goto="researcher_tools",
        update={
            "researcher_messages": [response],
            "tool_call_iterations": state.get("tool_call_iterations", 0) + 1,
        },
    )


async def researcher_tools(state: ResearcherState, dr_config: DeepResearchConfig) -> Command:
    """Execute researcher tool calls - search tools and think_tool."""
    researcher_messages = state.get("researcher_messages", [])
    most_recent = researcher_messages[-1]
    tool_calls = getattr(most_recent, "tool_calls", [])

    if not tool_calls:
        return Command(goto="compress_research")

    tools = _get_research_tools(dr_config)
    tools_by_name = {t.name: t for t in tools}

    tool_outputs = []
    for tc in tool_calls:
        tool_name = tc["name"]
        tool_fn = tools_by_name.get(tool_name)
        if tool_fn is None:
            tool_outputs.append(ToolMessage(
                content=f"Error: unknown tool '{tool_name}'",
                name=tool_name,
                tool_call_id=tc["id"],
            ))
            continue
        try:
            result = await tool_fn.ainvoke(tc["args"])
            tool_outputs.append(ToolMessage(
                content=str(result),
                name=tool_name,
                tool_call_id=tc["id"],
            ))
        except Exception as e:
            logger.exception("Researcher tool '%s' failed", tool_name)
            tool_outputs.append(ToolMessage(
                content=f"Error executing {tool_name}: {e}",
                name=tool_name,
                tool_call_id=tc["id"],
            ))

    exceeded = state.get("tool_call_iterations", 0) >= dr_config.max_react_tool_calls
    if exceeded:
        return Command(
            goto="compress_research",
            update={"researcher_messages": tool_outputs},
        )

    return Command(
        goto="researcher",
        update={"researcher_messages": tool_outputs},
    )


async def compress_research(state: ResearcherState, dr_config: DeepResearchConfig) -> dict:
    """Compress and synthesize research findings into a concise summary."""
    model = get_chat_model(dr_config.compression_model, temperature=0.1)
    researcher_messages = state.get("researcher_messages", [])

    compression_prompt = COMPRESS_PROMPT.format(date=_get_today_str())
    messages = [SystemMessage(content=compression_prompt)] + researcher_messages

    try:
        response = await model.ainvoke(messages)
        compressed = str(response.content)
    except Exception as e:
        logger.exception("Compression failed")
        compressed = f"Error synthesizing research: {e}"

    return {
        "compressed_research": compressed,
        "notes": [compressed],
    }


def _build_researcher_subgraph(config: DeepResearchConfig):
    """Build the researcher subgraph."""
    builder = StateGraph(ResearcherState, output=ResearcherOutputState)
    builder.add_node("researcher", partial(researcher, dr_config=config))
    builder.add_node("researcher_tools", partial(researcher_tools, dr_config=config))
    builder.add_node("compress_research", partial(compress_research, dr_config=config))
    builder.add_edge(START, "researcher")
    builder.add_edge("compress_research", END)
    return builder


async def final_report_generation(state: ResearchState, dr_config: DeepResearchConfig) -> dict:
    """Generate the final comprehensive research report."""
    notes = state.get("notes", [])
    findings = "\n\n---\n\n".join(notes)
    model = get_chat_model(dr_config.final_report_model, temperature=0.3)

    prompt = FINAL_REPORT_PROMPT.format(
        research_brief=state.get("research_brief", ""),
        messages=get_buffer_string(state.get("messages", [])),
        findings=findings,
        date=_get_today_str(),
    )

    try:
        response = await model.ainvoke([HumanMessage(content=prompt)])
        report = str(response.content)
    except Exception as e:
        logger.exception("Final report generation failed")
        report = f"Error generating final report: {e}"

    return {
        "final_report": report,
        "messages": [AIMessage(content=report)],
    }


def build_deep_research_graph(
    config: DeepResearchConfig,
    checkpointer=None,
):
    """Build the complete deep research workflow graph (without clarification).

    The clarification step is handled outside the graph to allow interactive
    WebSocket communication. This graph starts at write_research_brief.
    """
    builder = StateGraph(ResearchState)

    builder.add_node("write_research_brief", partial(write_research_brief, dr_config=config))
    builder.add_node("research_supervisor", _build_supervisor_subgraph(config))
    builder.add_node("final_report_generation", partial(final_report_generation, dr_config=config))

    builder.add_edge(START, "write_research_brief")
    builder.add_edge("write_research_brief", "research_supervisor")
    builder.add_edge("research_supervisor", "final_report_generation")
    builder.add_edge("final_report_generation", END)

    return builder.compile(checkpointer=checkpointer)


def _build_supervisor_subgraph(config: DeepResearchConfig):
    """Build the supervisor subgraph."""
    builder = StateGraph(SupervisorState)
    builder.add_node("supervisor", partial(supervisor, dr_config=config))
    builder.add_node("supervisor_tools", partial(supervisor_tools, dr_config=config))
    builder.add_edge(START, "supervisor")
    return builder.compile()


async def run_deep_research(
    user_message: str,
    config: DeepResearchConfig,
    thread_id: str,
    checkpointer=None,
    resume_answer: str | None = None,
) -> AsyncIterator[dict]:
    """Run the deep research workflow and yield progress events.

    Uses a two-phase approach:
    - Phase 1: Run clarification outside the graph. If needed, yield clarification and return.
    - Phase 2: Run the research graph (brief → supervisor → report) with streaming events.

    Args:
        user_message: The user's research question
        config: Deep research configuration
        thread_id: Unique thread ID for checkpointing
        checkpointer: LangGraph checkpointer
        resume_answer: If resuming from clarification, the user's answer

    Yields:
        Progress events:
            {"type": "clarification", "question": "..."}
            {"type": "progress", "step": "planning", "detail": "..."}
            {"type": "progress", "step": "searching", "detail": "query..."}
            {"type": "progress", "step": "compressing"}
            {"type": "progress", "step": "writing_report"}
            {"type": "report", "content": "final report text"}
            {"type": "error", "detail": "..."}
    """
    graph = build_deep_research_graph(config, checkpointer=checkpointer)
    graph_config = {"configurable": {"thread_id": thread_id}}

    try:
        if resume_answer:
            yield {"type": "progress", "step": "resuming", "detail": "Continuing research with your clarification..."}

            input_state = {
                "messages": [
                    HumanMessage(content=user_message),
                    AIMessage(content=""),
                    HumanMessage(content=resume_answer),
                ],
                "research_brief": None,
                "notes": [],
                "final_report": "",
                "clarification_question": None,
                "supervisor_messages": [],
            }
        else:
            yield {"type": "progress", "step": "clarifying", "detail": "Analyzing your research request..."}

            messages = [HumanMessage(content=user_message)]
            model = get_chat_model(config.clarification_model, temperature=0.1)
            clarification_model = model.with_structured_output(ClarifyWithUser)
            prompt_content = CLARIFY_INSTRUCTIONS.format(
                messages=get_buffer_string(messages),
                date=_get_today_str(),
            )
            response = await clarification_model.ainvoke([HumanMessage(content=prompt_content)])

            if response.need_clarification:
                logger.info("Deep research: asking clarification: %s", response.question)
                yield {"type": "clarification", "question": response.question}
                return

            input_state = {
                "messages": [
                    HumanMessage(content=user_message),
                    AIMessage(content=response.verification),
                ],
                "research_brief": None,
                "notes": [],
                "final_report": "",
                "clarification_question": None,
                "supervisor_messages": [],
            }

        async for event in graph.astream_events(input_state, graph_config, version="v2"):
            kind = event.get("event")
            name = event.get("name", "")

            if kind == "on_chain_start":
                if name == "write_research_brief":
                    yield {"type": "progress", "step": "planning", "detail": "Creating research plan..."}
                elif name == "supervisor":
                    yield {"type": "progress", "step": "supervising", "detail": "Coordinating research..."}
                elif name == "researcher":
                    yield {"type": "progress", "step": "searching", "detail": "Searching the web..."}
                elif name == "compress_research":
                    yield {"type": "progress", "step": "compressing", "detail": "Synthesizing findings..."}
                elif name == "final_report_generation":
                    yield {"type": "progress", "step": "writing_report", "detail": "Writing final report..."}

        final_state = await graph.aget_state(graph_config)
        final_values = final_state.values if final_state else {}
        report = final_values.get("final_report", "")

        if not report:
            for msg in reversed(final_values.get("messages", [])):
                if isinstance(msg, AIMessage) and msg.content:
                    report = str(msg.content)
                    break

        yield {"type": "report", "content": report}

    except Exception as e:
        logger.exception("Deep research failed")
        yield {"type": "error", "detail": str(e)}
