"""Tests for graph integration: built-in chat agent, conscience nodes, routing."""

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.graph import (
    CHAT_AGENT_SLUG,
    CHAT_SYSTEM_PROMPT,
    get_builtin_chat_spec,
    make_conscience_check_node,
    make_conscience_post_node,
    make_conscience_pre_node,
    make_router_node,
)
from app.agents.registry import AgentSpec


def test_chat_agent_slug():
    assert CHAT_AGENT_SLUG == "chat"


def test_get_builtin_chat_spec():
    spec = get_builtin_chat_spec()
    assert spec.slug == "chat"
    assert spec.name == "Chat"
    assert "memory" in spec.description.lower()
    assert "emotional" in spec.description.lower()
    assert "retrieve" in spec.tools
    assert "web_search" in spec.tools
    assert spec.is_orchestrator is True
    assert spec.is_router is True


def test_chat_system_prompt_content():
    assert "empathetic" in CHAT_SYSTEM_PROMPT.lower()
    assert "memory" in CHAT_SYSTEM_PROMPT.lower()
    assert "emotional" in CHAT_SYSTEM_PROMPT.lower()


def test_make_conscience_pre_node_name():
    node = make_conscience_pre_node("chat")
    assert node.__name__ == "conscience_pre_chat"


def test_make_conscience_post_node_name():
    node = make_conscience_post_node("chat")
    assert node.__name__ == "conscience_post_chat"


@pytest.mark.asyncio
async def test_conscience_pre_node_no_user_id():
    node = make_conscience_pre_node("chat")
    state = {"messages": [], "user_id": None}
    result = await node(state)
    assert result["conscience_enabled"] is True


@pytest.mark.asyncio
async def test_conscience_post_node_no_user_id():
    node = make_conscience_post_node("chat")
    state = {"messages": [], "user_id": None}
    result = await node(state)
    assert result == {}


async def test_router_chat_orchestrator_ignores_stale_routes_to(monkeypatch):
    """Regression test: the built-in chat agent is seeded with routes_to=[] (a static
    snapshot), which would otherwise mean it can never delegate to any specialist.
    The router should treat it like "general" and always see the current full registry.
    """
    captured_registry = {}

    async def fake_llm_route(user_msg, current_agent, registry):
        captured_registry["slugs"] = sorted(registry.keys())
        return "it"

    monkeypatch.setattr("app.agents.graph._llm_route", fake_llm_route)

    registry = {
        CHAT_AGENT_SLUG: get_builtin_chat_spec(),
        "it": AgentSpec(slug="it", name="IT", description="IT", tools=[]),
        "hr": AgentSpec(slug="hr", name="HR", description="HR", tools=[]),
    }
    node = make_router_node(
        registry, routes_map={CHAT_AGENT_SLUG: []}, orchestrator_slugs={CHAT_AGENT_SLUG}, default_agent=CHAT_AGENT_SLUG
    )
    state = {
        "messages": [HumanMessage(content="my laptop is broken")],
        "current_agent": CHAT_AGENT_SLUG,
        "orchestrator_agent": CHAT_AGENT_SLUG,
        "forced_agent": None,
        "sources": None,
        "mode": None,
    }
    result = await node(state)
    assert result["current_agent"] == "it"
    assert captured_registry["slugs"] == [CHAT_AGENT_SLUG, "hr", "it"]


def test_make_conscience_check_node_name():
    node = make_conscience_check_node("chat")
    assert node.__name__ == "conscience_check_chat"


@pytest.mark.asyncio
async def test_conscience_check_node_skips_without_context():
    node = make_conscience_check_node("chat")
    state = {
        "messages": [HumanMessage(content="hi"), AIMessage(content="hello")],
        "memory_context": "",
        "commitment_context": "",
    }
    result = await node(state)
    assert result == {"_needs_revision": False}


@pytest.mark.asyncio
async def test_conscience_check_node_skips_when_already_revised():
    node = make_conscience_check_node("chat")
    state = {
        "messages": [HumanMessage(content="hi"), AIMessage(content="hello")],
        "memory_context": "## What You Remember About This User\n- Name is Sam",
        "commitment_context": "",
        "_conscience_revised": True,
    }
    result = await node(state)
    assert result == {"_needs_revision": False}


@pytest.mark.asyncio
async def test_conscience_check_node_flags_conflict(monkeypatch):
    async def fake_check(user_msg, draft, memory_ctx, commitment_ctx):
        return True, "called them the wrong name"

    monkeypatch.setattr("app.agents.graph._check_response_consistency", fake_check)

    node = make_conscience_check_node("chat")
    state = {
        "messages": [HumanMessage(content="hi"), AIMessage(content="Hi Alex!")],
        "memory_context": "## What You Remember About This User\n- Name is Sam",
        "commitment_context": "",
    }
    result = await node(state)
    assert result["_needs_revision"] is True
    assert result["_conscience_revised"] is True
    assert len(result["messages"]) == 1


@pytest.mark.asyncio
async def test_conscience_check_node_no_conflict(monkeypatch):
    async def fake_check(user_msg, draft, memory_ctx, commitment_ctx):
        return False, ""

    monkeypatch.setattr("app.agents.graph._check_response_consistency", fake_check)

    node = make_conscience_check_node("chat")
    state = {
        "messages": [HumanMessage(content="hi"), AIMessage(content="Hi Sam!")],
        "memory_context": "## What You Remember About This User\n- Name is Sam",
        "commitment_context": "",
    }
    result = await node(state)
    assert result == {"_needs_revision": False}


@pytest.mark.asyncio
async def test_check_response_consistency_skips_without_known_context():
    from app.agents.graph import _check_response_consistency

    conflict, reason = await _check_response_consistency("hi", "hello", "", "")
    assert conflict is False
    assert reason == ""


def test_build_graph_wires_conscience_nodes(monkeypatch):
    from langchain_core.language_models.base import BaseLanguageModel
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langgraph.checkpoint.memory import MemorySaver

    from app.agents import graph as graph_module

    def fake_chat_model(model, temperature=0.3):
        return GenericFakeChatModel(messages=iter([AIMessage(content="hi")]))

    monkeypatch.setattr(graph_module, "get_chat_model", fake_chat_model)
    monkeypatch.setattr(BaseLanguageModel, "get_num_tokens", lambda self, text: len(text.split()))
    monkeypatch.setattr(GenericFakeChatModel, "bind_tools", lambda self, tools, **kw: self)

    registry = {
        CHAT_AGENT_SLUG: get_builtin_chat_spec(),
        "it": AgentSpec(slug="it", name="IT", description="IT specialist", tools=[]),
    }
    settings_map = {
        CHAT_AGENT_SLUG: {
            "model": None, "system_prompt": None, "connected_sources": [],
            "memory_enabled": True, "emotions_enabled": True, "episodes_enabled": True,
        },
        "it": {"model": None, "system_prompt": None, "connected_sources": []},
    }
    g = graph_module.build_graph(
        MemorySaver(), agent_registry=registry, agent_settings=settings_map, workflows={}
    )
    node_names = set(g.get_graph().nodes.keys())
    assert f"conscience_pre_{CHAT_AGENT_SLUG}" in node_names
    assert f"conscience_check_{CHAT_AGENT_SLUG}" in node_names
    assert f"conscience_post_{CHAT_AGENT_SLUG}" in node_names
    assert "conscience_pre_it" not in node_names


def test_build_graph_wires_conscience_nodes_for_memory_only(monkeypatch):
    """Nodes must still be wired when only one of the two independent flags is
    set - conscience_enabled (topology-level) is memory_enabled or emotions_enabled,
    not both required."""
    from langchain_core.language_models.base import BaseLanguageModel
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langgraph.checkpoint.memory import MemorySaver

    from app.agents import graph as graph_module

    def fake_chat_model(model, temperature=0.3):
        return GenericFakeChatModel(messages=iter([AIMessage(content="hi")]))

    monkeypatch.setattr(graph_module, "get_chat_model", fake_chat_model)
    monkeypatch.setattr(BaseLanguageModel, "get_num_tokens", lambda self, text: len(text.split()))
    monkeypatch.setattr(GenericFakeChatModel, "bind_tools", lambda self, tools, **kw: self)

    registry = {
        CHAT_AGENT_SLUG: get_builtin_chat_spec(),
    }
    settings_map = {
        CHAT_AGENT_SLUG: {
            "model": None, "system_prompt": None, "connected_sources": [],
            "memory_enabled": True, "emotions_enabled": False, "episodes_enabled": False,
        },
    }
    g = graph_module.build_graph(
        MemorySaver(), agent_registry=registry, agent_settings=settings_map, workflows={}
    )
    node_names = set(g.get_graph().nodes.keys())
    assert f"conscience_pre_{CHAT_AGENT_SLUG}" in node_names
    assert f"conscience_check_{CHAT_AGENT_SLUG}" in node_names
    assert f"conscience_post_{CHAT_AGENT_SLUG}" in node_names


def test_build_graph_no_conscience_nodes_when_both_disabled(monkeypatch):
    from langchain_core.language_models.base import BaseLanguageModel
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langgraph.checkpoint.memory import MemorySaver

    from app.agents import graph as graph_module

    def fake_chat_model(model, temperature=0.3):
        return GenericFakeChatModel(messages=iter([AIMessage(content="hi")]))

    monkeypatch.setattr(graph_module, "get_chat_model", fake_chat_model)
    monkeypatch.setattr(BaseLanguageModel, "get_num_tokens", lambda self, text: len(text.split()))
    monkeypatch.setattr(GenericFakeChatModel, "bind_tools", lambda self, tools, **kw: self)

    registry = {
        CHAT_AGENT_SLUG: get_builtin_chat_spec(),
    }
    settings_map = {
        CHAT_AGENT_SLUG: {
            "model": None, "system_prompt": None, "connected_sources": [],
            "memory_enabled": False, "emotions_enabled": False, "episodes_enabled": False,
        },
    }
    g = graph_module.build_graph(
        MemorySaver(), agent_registry=registry, agent_settings=settings_map, workflows={}
    )
    node_names = set(g.get_graph().nodes.keys())
    assert f"conscience_pre_{CHAT_AGENT_SLUG}" not in node_names
    assert f"conscience_check_{CHAT_AGENT_SLUG}" not in node_names
    assert f"conscience_post_{CHAT_AGENT_SLUG}" not in node_names


def test_build_graph_episodes_defensively_requires_emotions(monkeypatch):
    """episodes_enabled=True in settings shouldn't matter if emotions_enabled is
    False - episodes are derived from emotion intensity and can't exist without it."""
    from langchain_core.language_models.base import BaseLanguageModel
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    from langgraph.checkpoint.memory import MemorySaver

    from app.agents import graph as graph_module

    def fake_chat_model(model, temperature=0.3):
        return GenericFakeChatModel(messages=iter([AIMessage(content="hi")]))

    monkeypatch.setattr(graph_module, "get_chat_model", fake_chat_model)
    monkeypatch.setattr(BaseLanguageModel, "get_num_tokens", lambda self, text: len(text.split()))
    monkeypatch.setattr(GenericFakeChatModel, "bind_tools", lambda self, tools, **kw: self)

    registry = {
        CHAT_AGENT_SLUG: get_builtin_chat_spec(),
    }
    settings_map = {
        CHAT_AGENT_SLUG: {
            "model": None, "system_prompt": None, "connected_sources": [],
            "memory_enabled": True, "emotions_enabled": False, "episodes_enabled": True,
        },
    }

    g = graph_module.build_graph(
        MemorySaver(), agent_registry=registry, agent_settings=settings_map, workflows={}
    )
    node_names = set(g.get_graph().nodes.keys())
    assert f"conscience_pre_{CHAT_AGENT_SLUG}" in node_names


@pytest.mark.asyncio
async def test_conscience_check_node_logs_timing(caplog):
    """Fix for cost/latency visibility: every check-node pass should emit a
    conscience_timing log record, even when it short-circuits without a
    conflict, so latency is measurable in production without a redesign."""
    import logging

    node = make_conscience_check_node("chat")
    state = {
        "messages": [HumanMessage(content="hi"), AIMessage(content="hello")],
        "memory_context": "",
        "commitment_context": "",
    }
    with caplog.at_level(logging.INFO, logger="app.agents.graph"):
        await node(state)

    timing_records = [r for r in caplog.records if r.message == "conscience_timing"]
    assert len(timing_records) == 1
    assert timing_records[0].node == "check"
    assert timing_records[0].agent == "chat"
    assert isinstance(timing_records[0].ms, float)


@pytest.mark.asyncio
async def test_conscience_pre_node_logs_timing(caplog, monkeypatch, session_factory, create_test_user):
    import logging
    from unittest.mock import AsyncMock, MagicMock

    monkeypatch.setattr("app.db.session.async_session_factory", session_factory)

    mock_response = MagicMock()
    mock_response.content = '{"label": "neutral", "intensity": 0.0}'
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    monkeypatch.setattr("app.services.emotion.get_chat_model", lambda *a, **kw: mock_llm)

    user = await create_test_user("timinguser@example.com", "pass123")

    node = make_conscience_pre_node("chat")
    state = {"messages": [HumanMessage(content="hi")], "user_id": str(user.id)}

    with caplog.at_level(logging.INFO, logger="app.agents.graph"):
        await node(state)

    timing_records = [r for r in caplog.records if r.message == "conscience_timing"]
    assert len(timing_records) == 1
    assert timing_records[0].node == "pre"
    assert timing_records[0].agent == "chat"


@pytest.mark.asyncio
async def test_post_processing_supersedes_old_fact(monkeypatch, session_factory, create_test_user):
    """End-to-end (minus real LLM calls) check of the Google->Meta scenario:
    when extraction flags a new fact as superseding an old one, the old row
    should be marked superseded and a fresh row created for the new fact -
    not merged by string length via the embedding-similarity path."""
    from unittest.mock import AsyncMock, MagicMock

    from app.agents.graph import _run_conscience_post_processing
    from app.models.agent_memory import AgentMemory
    from app.services.memory import create_memory

    monkeypatch.setattr("app.db.session.async_session_factory", session_factory)

    user = await create_test_user("supersedeflow@example.com", "pass123")
    async with session_factory() as session:
        old_fact = await create_memory(session, user.id, "chat", "fact", "Works at Google", 0.6, [])
        await session.commit()
        old_fact_id = old_fact.id

    emotion_response = MagicMock()
    emotion_response.content = '{"joy": 0.0, "trust": 0.0, "fear": 0.0, "surprise": 0.0, "sadness": 0.0, "disgust": 0.0, "anger": 0.0, "anticipation": 0.0}'
    emotion_llm = AsyncMock()
    emotion_llm.ainvoke = AsyncMock(return_value=emotion_response)
    monkeypatch.setattr("app.services.emotion.get_chat_model", lambda *a, **kw: emotion_llm)

    memory_response = MagicMock()
    memory_response.content = (
        '{"memories": [{"category": "fact", "content": "Works at Meta", "importance": 0.6, '
        '"tags": [], "supersedes_id": "%s"}], "resolved_commitment_ids": []}' % old_fact_id
    )
    memory_llm = AsyncMock()
    memory_llm.ainvoke = AsyncMock(return_value=memory_response)
    monkeypatch.setattr("app.services.memory.get_chat_model", lambda *a, **kw: memory_llm)

    await _run_conscience_post_processing(
        "chat", user.id, None, "I changed jobs, I work at Meta now", "Got it, updated!"
    )

    async with session_factory() as session:
        refreshed_old = await session.get(AgentMemory, old_fact_id)
        assert refreshed_old.status == "superseded"

        from sqlalchemy import select
        result = await session.scalars(
            select(AgentMemory).where(AgentMemory.user_id == user.id).where(AgentMemory.content == "Works at Meta")
        )
        new_facts = result.all()
        assert len(new_facts) == 1


@pytest.mark.asyncio
async def test_conscience_pre_node_hydrates_recall_context(monkeypatch, session_factory, create_test_user):
    """When the affect check flags a recall query, the pre-node should follow a
    hydratable memory's provenance back to the real conversation and inject the
    verbatim exchange, not just the memory's gisted summary."""
    import uuid as uuid_module
    from unittest.mock import AsyncMock, MagicMock

    from app.models import Conversation, Message
    from app.models.agent_memory import AgentMemory

    monkeypatch.setattr("app.db.session.async_session_factory", session_factory)

    mock_response = MagicMock()
    mock_response.content = '{"label": "neutral", "intensity": 0.0, "is_recall_query": true}'
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    monkeypatch.setattr("app.services.emotion.get_chat_model", lambda *a, **kw: mock_llm)

    user = await create_test_user("recallhydrationuser@example.com", "pass123")

    async with session_factory() as session:
        convo = Conversation(user_id=user.id)
        session.add(convo)
        await session.flush()

        user_msg = Message(
            id=uuid_module.uuid4(), conversation_id=convo.id, role="user",
            content="How did we fix the pod crash?",
        )
        assistant_msg = Message(
            id=uuid_module.uuid4(), conversation_id=convo.id, role="assistant",
            content="We bumped the memory limit on the deployment.",
        )
        session.add_all([user_msg, assistant_msg])
        await session.flush()

        memory = AgentMemory(
            user_id=user.id, agent_slug="chat", category="event",
            content="Fixed a k8s pod crash loop", conversation_id=convo.id,
            source_message_id=assistant_msg.id, importance_score=0.9,
        )
        session.add(memory)
        await session.commit()

    node = make_conscience_pre_node("chat")
    state = {
        "messages": [HumanMessage(content="Do you remember how we fixed the pod crash?")],
        "user_id": user.id,
    }
    result = await node(state)

    assert result["recall_context"] != ""
    assert "memory limit" in result["recall_context"]


@pytest.mark.asyncio
async def test_conscience_pre_node_no_recall_context_when_not_flagged(monkeypatch, session_factory, create_test_user):
    from unittest.mock import AsyncMock, MagicMock

    monkeypatch.setattr("app.db.session.async_session_factory", session_factory)

    mock_response = MagicMock()
    mock_response.content = '{"label": "neutral", "intensity": 0.0, "is_recall_query": false}'
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    monkeypatch.setattr("app.services.emotion.get_chat_model", lambda *a, **kw: mock_llm)

    user = await create_test_user("norecalluser@example.com", "pass123")

    node = make_conscience_pre_node("chat")
    state = {"messages": [HumanMessage(content="What's the weather like?")], "user_id": str(user.id)}
    result = await node(state)

    assert result["recall_context"] == ""


@pytest.mark.asyncio
async def test_conscience_check_node_skips_llm_call_when_memory_disabled(monkeypatch):
    """The consistency check is purely a Memory feature - it must not call the
    LLM at all when memory is disabled for this agent, regardless of context."""
    called = False

    async def fake_check(user_msg, draft, memory_ctx, commitment_ctx):
        nonlocal called
        called = True
        return True, "should not be reached"

    monkeypatch.setattr("app.agents.graph._check_response_consistency", fake_check)

    node = make_conscience_check_node("chat", memory_enabled=False)
    state = {
        "messages": [HumanMessage(content="hi"), AIMessage(content="Hi Alex!")],
        "memory_context": "## What You Remember About This User\n- Name is Sam",
        "commitment_context": "",
    }
    result = await node(state)

    assert result == {"_needs_revision": False}
    assert called is False


@pytest.mark.asyncio
async def test_conscience_pre_node_memory_only_skips_emotion_and_episode_fetch(
    monkeypatch, session_factory, create_test_user
):
    """A memory-only agent should never populate emotion_context/episode_context,
    even if this user/agent pair already has emotion state in the DB."""
    from unittest.mock import AsyncMock, MagicMock

    from app.services.emotion import update_emotion_state

    monkeypatch.setattr("app.db.session.async_session_factory", session_factory)

    mock_response = MagicMock()
    mock_response.content = '{"label": "neutral", "intensity": 0.0, "is_recall_query": false}'
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    monkeypatch.setattr("app.services.emotion.get_chat_model", lambda *a, **kw: mock_llm)

    user = await create_test_user("memoryonlyuser@example.com", "pass123")
    async with session_factory() as session:
        await update_emotion_state(
            session, user.id, "chat",
            {"joy": 0.9, "trust": 0.9, "fear": 0.0, "surprise": 0.0,
             "sadness": 0.0, "disgust": 0.0, "anger": 0.0, "anticipation": 0.0},
        )
        await session.commit()

    node = make_conscience_pre_node("chat", memory_enabled=True, emotions_enabled=False, episodes_enabled=False)
    state = {"messages": [HumanMessage(content="hi")], "user_id": user.id}
    result = await node(state)

    assert result["emotion_context"] == ""
    assert result["episode_context"] == ""
    assert result["user_affect_context"] == ""


@pytest.mark.asyncio
async def test_conscience_pre_node_emotions_only_skips_memory_fetch(monkeypatch, session_factory, create_test_user):
    """An emotions-only agent should never populate memory_context/commitment_context,
    even if this user/agent pair already has memories in the DB."""
    from unittest.mock import AsyncMock, MagicMock

    from app.services.memory import create_memory

    monkeypatch.setattr("app.db.session.async_session_factory", session_factory)

    mock_response = MagicMock()
    mock_response.content = '{"label": "neutral", "intensity": 0.0, "is_recall_query": false}'
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)
    monkeypatch.setattr("app.services.emotion.get_chat_model", lambda *a, **kw: mock_llm)

    user = await create_test_user("emotiononlyuser@example.com", "pass123")
    async with session_factory() as session:
        await create_memory(session, user.id, "chat", "fact", "Works at Meta", 0.9, [])
        await session.commit()

    node = make_conscience_pre_node("chat", memory_enabled=False, emotions_enabled=True, episodes_enabled=True)
    state = {"messages": [HumanMessage(content="hi")], "user_id": user.id}
    result = await node(state)

    assert result["memory_context"] == ""
    assert result["commitment_context"] == ""
    assert result["recall_context"] == ""


@pytest.mark.asyncio
async def test_conscience_post_node_spawns_nothing_when_both_disabled():
    from app.agents import graph as graph_module

    before = len(graph_module._BACKGROUND_TASKS)
    node = make_conscience_post_node("chat", memory_enabled=False, emotions_enabled=False, episodes_enabled=False)
    state = {
        "messages": [HumanMessage(content="hi"), AIMessage(content="hello")],
        "user_id": "some-user-id",
        "conversation_id": "some-convo-id",
    }
    result = await node(state)

    assert result == {}
    assert len(graph_module._BACKGROUND_TASKS) == before
