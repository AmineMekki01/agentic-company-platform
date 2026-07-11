"""Tests for conscience context injection into agent system prompt."""

from app.agents.graph import CHAT_SYSTEM_PROMPT, get_builtin_chat_spec


def test_chat_system_prompt_has_conscience_keywords():
    prompt_lower = CHAT_SYSTEM_PROMPT.lower()
    assert "empathetic" in prompt_lower
    assert "memory" in prompt_lower
    assert "emotional" in prompt_lower
    assert "tone" in prompt_lower


def test_chat_spec_has_correct_tools():
    spec = get_builtin_chat_spec()
    assert "retrieve" in spec.tools
    assert "web_search" in spec.tools


def test_chat_spec_is_router_and_orchestrator():
    spec = get_builtin_chat_spec()
    assert spec.is_router is True
    assert spec.is_orchestrator is True


def test_conscience_enabled_in_state_allows_injection():
    from app.agents.state import AgentState
    fields = AgentState.__annotations__
    assert "memory_context" in fields
    assert "emotion_context" in fields
    assert "episode_context" in fields
    assert "conscience_enabled" in fields
