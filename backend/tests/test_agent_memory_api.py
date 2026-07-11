"""Tests for the user-facing agent memory view/delete endpoints."""

import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def test_list_agent_memories_empty(client, auth_headers):
    res = await client.get("/api/agents/chat/memory", headers=auth_headers)
    assert res.status_code == 200
    assert res.json() == []


async def test_list_agent_memories_scoped_to_current_user(client, auth_headers, other_headers, session_factory):
    """A memory created for a different user must not show up in this user's list."""
    from app.services.memory import create_memory

    other_me = await client.get("/api/auth/me", headers=other_headers)
    other_user_id = uuid.UUID(other_me.json()["id"])

    async with session_factory() as session:
        await create_memory(session, other_user_id, "chat", "preference", "Likes concise answers", 0.7, ["style"])
        await session.commit()

    res = await client.get("/api/agents/chat/memory", headers=auth_headers)
    assert res.status_code == 200
    assert res.json() == []


async def test_delete_agent_memory(client, auth_headers, session_factory):
    from app.services.memory import create_memory

    me = await client.get("/api/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])

    async with session_factory() as session:
        memory = await create_memory(session, user_id, "chat", "fact", "Works in finance", 0.6, [])
        await session.commit()
        memory_id = str(memory.id)

    list_res = await client.get("/api/agents/chat/memory", headers=auth_headers)
    assert any(m["id"] == memory_id for m in list_res.json())

    del_res = await client.delete(f"/api/agents/chat/memory/{memory_id}", headers=auth_headers)
    assert del_res.status_code == 204

    list_res_after = await client.get("/api/agents/chat/memory", headers=auth_headers)
    assert all(m["id"] != memory_id for m in list_res_after.json())


async def test_delete_agent_memory_not_owned_returns_404(client, auth_headers, other_headers, session_factory):
    from app.services.memory import create_memory

    me = await client.get("/api/auth/me", headers=other_headers)
    other_user_id = uuid.UUID(me.json()["id"])

    async with session_factory() as session:
        memory = await create_memory(session, other_user_id, "chat", "fact", "Other user's fact", 0.5, [])
        await session.commit()
        memory_id = str(memory.id)

    res = await client.delete(f"/api/agents/chat/memory/{memory_id}", headers=auth_headers)
    assert res.status_code == 404


async def test_delete_agent_memory_wrong_slug_returns_404(client, auth_headers, session_factory):
    from app.services.memory import create_memory

    me = await client.get("/api/auth/me", headers=auth_headers)
    user_id = uuid.UUID(me.json()["id"])

    async with session_factory() as session:
        memory = await create_memory(session, user_id, "hr", "fact", "HR agent's memory", 0.5, [])
        await session.commit()
        memory_id = str(memory.id)

    res = await client.delete(f"/api/agents/chat/memory/{memory_id}", headers=auth_headers)
    assert res.status_code == 404
