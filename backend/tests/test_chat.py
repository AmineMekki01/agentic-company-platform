import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver

from app.agents import graph as graph_module
from app.agents import llm as llm_module
from app.agents.registry import AgentSpec
from app.agents.runtime import AgentRuntime
from app.api import chat as chat_module
from app.main import app as fastapi_app
from app.models import AgentSettings

pytestmark = pytest.mark.asyncio

FAKE_REPLY = "Hello from the fake agent"


@pytest.fixture
async def chat_env(monkeypatch, session_factory):
    monkeypatch.setattr(chat_module, "async_session_factory", session_factory)

    def fake_chat_model(model: str, temperature: float = 0.3):
        return GenericFakeChatModel(messages=iter([AIMessage(content=FAKE_REPLY)]))

    monkeypatch.setattr(graph_module, "get_chat_model", fake_chat_model)
    monkeypatch.setattr(llm_module, "get_chat_model", fake_chat_model)

    from langchain_core.language_models.base import BaseLanguageModel
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
    monkeypatch.setattr(BaseLanguageModel, "get_num_tokens", lambda self, text: len(text.split()))

    def _bind_tools(self, tools, **kwargs):
        return self
    monkeypatch.setattr(GenericFakeChatModel, "bind_tools", _bind_tools)

    async with session_factory() as session:
        session.add(AgentSettings(
            slug="hr",
            name="HR Specialist",
            description="HR test agent",
            system_prompt="You are HR.",
            tools=["retrieve"],
            is_published=True,
        ))
        await session.commit()

    agent_registry = {
        "hr": AgentSpec(
            slug="hr",
            name="HR Specialist",
            description="HR test agent",
            system_prompt="You are HR.",
            tools=["retrieve"],
        ),
    }
    agent_settings = {
        "hr": {"model": None, "system_prompt": None, "connected_sources": None},
    }

    runtime = AgentRuntime()
    runtime.agent_registry = agent_registry
    runtime.graph = graph_module.build_graph(MemorySaver(), agent_registry=agent_registry, agent_settings=agent_settings)
    fastapi_app.state.runtime = runtime
    yield runtime
    fastapi_app.state.runtime = None


@pytest.fixture
async def conscience_chat_env(monkeypatch, session_factory):
    """Like chat_env, but the entry agent has conscience_enabled=True end to end.

    Patches async_session_factory and get_chat_model everywhere the conscience
    pre/check/post nodes resolve them at call time (they use local imports), not
    just where chat.py itself resolves them, so background persistence hits the
    in-memory test DB instead of the real one.
    """
    monkeypatch.setattr(chat_module, "async_session_factory", session_factory)
    monkeypatch.setattr("app.db.session.async_session_factory", session_factory)

    def fake_chat_model(model: str, temperature: float = 0.3):
        return GenericFakeChatModel(messages=iter([AIMessage(content=FAKE_REPLY)]))

    monkeypatch.setattr(graph_module, "get_chat_model", fake_chat_model)
    monkeypatch.setattr(llm_module, "get_chat_model", fake_chat_model)
    monkeypatch.setattr("app.services.memory.get_chat_model", fake_chat_model)
    monkeypatch.setattr("app.services.emotion.get_chat_model", fake_chat_model)

    from langchain_core.language_models.base import BaseLanguageModel
    monkeypatch.setattr(BaseLanguageModel, "get_num_tokens", lambda self, text: len(text.split()))

    def _bind_tools(self, tools, **kwargs):
        return self
    monkeypatch.setattr(GenericFakeChatModel, "bind_tools", _bind_tools)

    async with session_factory() as session:
        session.add(AgentSettings(
            slug="chat",
            name="Chat",
            description="Conscience chat test agent",
            system_prompt="You are Chat.",
            tools=[],
            is_published=True,
            is_router=True,
            is_orchestrator=True,
            memory_enabled=True,
            emotions_enabled=True,
            episodes_enabled=True,
        ))
        await session.commit()

    agent_registry = {
        "chat": AgentSpec(
            slug="chat",
            name="Chat",
            description="Chat test agent",
            system_prompt="You are Chat.",
            tools=[],
            is_router=True,
            is_orchestrator=True,
        ),
    }
    agent_settings = {
        "chat": {
            "model": None, "system_prompt": None, "connected_sources": None,
            "memory_enabled": True, "emotions_enabled": True, "episodes_enabled": True,
        },
    }

    runtime = AgentRuntime()
    runtime.agent_registry = agent_registry
    runtime.graph = graph_module.build_graph(MemorySaver(), agent_registry=agent_registry, agent_settings=agent_settings)
    fastapi_app.state.runtime = runtime
    yield runtime
    fastapi_app.state.runtime = None


async def test_chat_stream_with_conscience_enabled_completes(client, auth_headers, conscience_chat_env):
    """The conscience-enabled entry point should still stream a normal response -
    the pre-node/check-node/post-node wiring shouldn't hang or break the SSE stream,
    and post-processing (memory/emotion extraction) must not block "done"."""
    convo = (await client.post("/api/conversations", headers=auth_headers)).json()

    res = await client.post(
        f"/api/chat/{convo['id']}/stream",
        headers=auth_headers,
        json={"content": "Hi, my name is Alex.", "agent": "chat"},
    )
    assert res.status_code == 200
    body = res.text
    assert "event: token" in body
    assert "event: done" in body
    assert FAKE_REPLY in body

    detail = (
        await client.get(f"/api/conversations/{convo['id']}", headers=auth_headers)
    ).json()
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant"]


async def test_chat_stream_threads_agent_message_id_into_conscience_post_processing(
    client, auth_headers, conscience_chat_env, monkeypatch
):
    """chat.py generates the assistant message id upfront and later persists it as
    the real Message row (see _make_stream_response). This confirms that exact id
    is what reaches conscience post-processing as agent_message_id - the thing
    memories use as provenance - rather than some other/no id.

    _run_conscience_post_processing itself is stubbed out here: this test is about
    the wiring (does the right id arrive), not about the extraction/persistence
    logic, which is covered directly in test_conscience_memory.py and
    test_conscience_graph.py.
    """
    import asyncio

    from app.agents import graph as graph_module

    captured: dict = {}

    async def fake_post_processing(
        agent_slug, user_id, conversation_id, last_user_msg, last_agent_msg, agent_message_id=None,
        memory_enabled=True, emotions_enabled=True, episodes_enabled=True,
    ):
        captured["agent_message_id"] = agent_message_id
        captured["conversation_id"] = conversation_id

    monkeypatch.setattr(graph_module, "_run_conscience_post_processing", fake_post_processing)

    convo = (await client.post("/api/conversations", headers=auth_headers)).json()

    res = await client.post(
        f"/api/chat/{convo['id']}/stream",
        headers=auth_headers,
        json={"content": "Hi, my name is Alex.", "agent": "chat"},
    )
    assert res.status_code == 200

    pending = [t for t in graph_module._BACKGROUND_TASKS if not t.done()]
    if pending:
        await asyncio.gather(*pending)

    detail = (
        await client.get(f"/api/conversations/{convo['id']}", headers=auth_headers)
    ).json()
    assistant_message_id = next(m["id"] for m in detail["messages"] if m["role"] == "assistant")

    assert captured["agent_message_id"] == assistant_message_id
    assert captured["conversation_id"] == convo["id"]


async def test_list_agents(client, auth_headers):
    res = await client.get("/api/agents", headers=auth_headers)
    assert res.status_code == 200
    agents = res.json()
    assert isinstance(agents, list)


async def test_chat_stream_persists_messages_and_title(client, auth_headers, chat_env):
    convo = (await client.post("/api/conversations", headers=auth_headers)).json()
    print(f"convo : {convo}")

    res = await client.post(
        f"/api/chat/{convo['id']}/stream",
        headers=auth_headers,
        json={
            "content": "What is the vacation policy?"
            },
    )
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")

    body = res.text
    print(f"body : {body}")
    assert "event: agent" in body
    assert "event: token" in body
    assert "event: done" in body

    detail = (
        await client.get(f"/api/conversations/{convo['id']}", headers=auth_headers)
    ).json()
    assert detail["title"] is not None
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant"]
    assert detail["messages"][1]["content"] == FAKE_REPLY
    assert detail["messages"][1]["agent_id"] == "hr"


async def test_chat_stream_includes_trace_url_when_tracing_enabled(client, auth_headers, chat_env, monkeypatch):
    """When Langfuse is enabled, the done event and persisted assistant message
    should both carry a trace_url so the UI can link to the exact trace."""
    from unittest.mock import MagicMock

    fake_handler = MagicMock()
    monkeypatch.setattr(chat_module, "new_langfuse_handler", lambda: fake_handler)
    monkeypatch.setattr(chat_module, "trace_url_for", lambda handler: "http://localhost:3000/trace/abc123" if handler is fake_handler else None)

    convo = (await client.post("/api/conversations", headers=auth_headers)).json()
    res = await client.post(
        f"/api/chat/{convo['id']}/stream",
        headers=auth_headers,
        json={"content": "What is the vacation policy?"},
    )
    assert res.status_code == 200
    assert '"trace_url": "http://localhost:3000/trace/abc123"' in res.text

    detail = (
        await client.get(f"/api/conversations/{convo['id']}", headers=auth_headers)
    ).json()
    assert detail["messages"][1]["trace_url"] == "http://localhost:3000/trace/abc123"


async def test_chat_rejects_unknown_agent(client, auth_headers, chat_env):
    convo = (await client.post("/api/conversations", headers=auth_headers)).json()
    res = await client.post(
        f"/api/chat/{convo['id']}/stream",
        headers=auth_headers,
        json={"content": "hi", "agent": "nonexistent"},
    )
    assert res.status_code == 400


async def test_chat_foreign_conversation_404(client, auth_headers, chat_env, create_test_user):
    convo = (await client.post("/api/conversations", headers=auth_headers)).json()

    other = await create_test_user("intruder@example.com", "password123")
    from app.core.security import create_access_token
    token = create_access_token(other.id, other.role)
    other_headers = {"Authorization": f"Bearer {token}"}

    res = await client.post(
        f"/api/chat/{convo['id']}/stream",
        headers=other_headers,
        json={"content": "hi"},
    )
    assert res.status_code == 404


async def test_router_respects_forced_agent(monkeypatch):
    from app.agents.graph import make_router_node
    from app.agents.registry import AgentSpec

    registry = {
        "general": AgentSpec(slug="general", name="General", description="General", tools=[]),
        "hr": AgentSpec(slug="hr", name="HR", description="HR", tools=[]),
    }
    node = make_router_node(registry, routes_map={"general": ["hr"]}, orchestrator_slugs={"general"}, default_agent="general")
    state = {
        "messages": [],
        "current_agent": "general",
        "orchestrator_agent": "general",
        "forced_agent": "hr",
        "sources": None,
        "mode": None,
    }
    result = await node(state)
    assert result["current_agent"] == "hr"


async def test_router_routes_at_mention():
    from langchain_core.messages import HumanMessage

    from app.agents.graph import make_router_node
    from app.agents.registry import AgentSpec

    registry = {
        "general": AgentSpec(slug="general", name="General", description="General", tools=[]),
        "it": AgentSpec(slug="it", name="IT", description="IT", tools=[]),
    }
    node = make_router_node(registry, routes_map={"general": ["it"]}, orchestrator_slugs={"general"}, default_agent="general")
    state = {
        "messages": [HumanMessage(content="My laptop is broken @it")],
        "current_agent": "general",
        "orchestrator_agent": "general",
        "forced_agent": None,
        "sources": None,
        "mode": None,
    }
    result = await node(state)
    assert result["current_agent"] == "it"


async def test_non_orchestrator_stays_fixed():
    from app.agents.graph import make_router_node
    from app.agents.registry import AgentSpec

    registry = {
        "hr": AgentSpec(slug="hr", name="HR", description="HR", tools=[]),
    }

    node = make_router_node(registry, routes_map={}, orchestrator_slugs=set(), default_agent="hr")
    state = {
        "messages": [],
        "current_agent": "hr",
        "orchestrator_agent": "hr",
        "forced_agent": None,
        "sources": None,
        "mode": None,
    }
    result = await node(state)
    assert result["current_agent"] == "hr"


async def test_router_restricts_to_orchestrator_routes(monkeypatch):
    from app.agents.graph import _llm_route, make_router_node
    from app.agents.registry import AgentSpec

    registry = {
        "general": AgentSpec(slug="general", name="General", description="General", tools=[]),
        "hr": AgentSpec(slug="hr", name="HR", description="HR", tools=[]),
        "it": AgentSpec(slug="it", name="IT", description="IT", tools=[]),
    }

    captured_registry = {}

    async def fake_llm_route(user_msg, current_agent, registry):
        captured_registry["slugs"] = list(registry.keys())
        return "hr"

    monkeypatch.setattr("app.agents.graph._llm_route", fake_llm_route)

    node = make_router_node(registry, routes_map={"general": ["hr"]}, orchestrator_slugs={"general"}, default_agent="general")
    state = {
        "messages": [],
        "current_agent": "general",
        "orchestrator_agent": "general",
        "forced_agent": None,
        "sources": None,
        "mode": None,
    }
    result = await node(state)
    assert result["current_agent"] == "hr"
    assert captured_registry["slugs"] == ["hr", "it", "general"]


async def test_orchestrator_empty_routes_only_routes_to_self(monkeypatch):
    from app.agents.graph import _llm_route, make_router_node
    from app.agents.registry import AgentSpec

    registry = {
        "general": AgentSpec(slug="general", name="General", description="General", tools=[], is_orchestrator=True, routes_to=[]),
        "hr": AgentSpec(slug="hr", name="HR", description="HR", tools=[]),
    }

    async def fake_llm_route(user_msg, current_agent, registry):
        return "hr"

    monkeypatch.setattr("app.agents.graph._llm_route", fake_llm_route)

    node = make_router_node(registry, routes_map={"general": []}, orchestrator_slugs={"general"}, default_agent="general")
    state = {
        "messages": [],
        "current_agent": "general",
        "orchestrator_agent": "general",
        "forced_agent": None,
        "sources": None,
        "mode": None,
    }
    result = await node(state)
    assert result["current_agent"] == "hr"


async def test_non_orchestrator_stays_fixed_despite_cross_domain_message(monkeypatch):
    from app.agents.graph import _llm_route, make_router_node
    from app.agents.registry import AgentSpec

    registry = {
        "it": AgentSpec(slug="it", name="IT", description="IT", tools=[]),
        "finance": AgentSpec(slug="finance", name="Finance", description="Finance", tools=[]),
    }

    async def fake_llm_route(user_msg, current_agent, registry):
        return "finance"

    monkeypatch.setattr("app.agents.graph._llm_route", fake_llm_route)

    node = make_router_node(registry, routes_map={}, orchestrator_slugs=set(), default_agent="it")
    state = {
        "messages": [],
        "current_agent": "it",
        "orchestrator_agent": "it",
        "forced_agent": None,
        "sources": None,
        "mode": None,
    }
    result = await node(state)
    assert result["current_agent"] == "it"
