from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class SourceInfo(TypedDict):
    rank: int
    title: str
    id: str


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    current_agent: str
    orchestrator_agent: str | None
    forced_agent: str | None
    sources: list[SourceInfo] | None
    mode: str | None
    reflection_done: bool | None
    step_count: int | None
    _needs_rethink: bool | None
    source_offset: int | None
    user_allowed_slugs: list[str] | None
