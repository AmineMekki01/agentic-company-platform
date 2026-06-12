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

    async def _fake_retrieve(query, source_ids, agent_slug=""):
        return "", []

    monkeypatch.setattr(graph_module, "_retrieve_for_agent", _fake_retrieve)

    from langchain_core.language_models.base import BaseLanguageModel
    monkeypatch.setattr(BaseLanguageModel, "get_num_tokens", lambda self, text: len(text.split()))

    async with session_factory() as session:
        session.add(AgentSettings(
            slug="hr",
            name="HR Specialist",
            description="HR test agent",
            system_prompt="You are HR.",
            tools=["retrieve"],
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
