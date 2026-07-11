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
    response_text: str | None
    orchestrator_history: list[dict] | None
    user_id: str | None
    conversation_id: str | None
    agent_message_id: str | None
    memory_context: str | None
    emotion_context: str | None
    commitment_context: str | None
    user_affect_context: str | None
    episode_context: str | None
    recall_context: str | None
    conscience_enabled: bool | None
    _needs_revision: bool | None
    _conscience_revised: bool | None
