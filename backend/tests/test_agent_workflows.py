"""Tests for agent workflows API."""

import pytest
from sqlalchemy import select

from app.models import AgentSettings, AgentWorkflow

pytestmark = pytest.mark.asyncio

_WORKFLOW_DEF = {
    "input_schema": ["query"],
    "nodes": [
        {"id": "n1", "agent_slug": "hr", "inputs": [{"name": "query"}], "outputs": [{"name": "output"}], "output_var": "output"},
    ],
    "edges": [],
    "output": "n1.output",
}


async def _seed_agent(session_factory, slug="hr"):
    async with session_factory() as session:
        agent = AgentSettings(slug=slug, name="HR")
        session.add(agent)
        await session.commit()
        await session.refresh(agent)
        return agent


async def test_list_workflows_admin_only(client, auth_headers):
    res = await client.get("/api/admin/agents/hr/workflows", headers=auth_headers)
    assert res.status_code == 403


async def test_list_workflows(client, admin_headers, session_factory):
    await _seed_agent(session_factory)
    async with session_factory() as session:
        session.add(AgentWorkflow(owner_agent_slug="hr", name="WF1", enabled=False, definition=_WORKFLOW_DEF))
        await session.commit()
    res = await client.get("/api/admin/agents/hr/workflows", headers=admin_headers)
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["name"] == "WF1"


async def test_create_workflow(client, admin_headers, session_factory):
    await _seed_agent(session_factory)
    res = await client.post(
        "/api/admin/agents/hr/workflows",
        headers=admin_headers,
        json={"name": "New WF", "enabled": False, "definition": _WORKFLOW_DEF},
    )
    assert res.status_code == 201
    assert res.json()["name"] == "New WF"


async def test_create_workflow_nonexistent_agent(client, admin_headers):
    res = await client.post(
        "/api/admin/agents/nonexistent/workflows",
        headers=admin_headers,
        json={"name": "WF", "enabled": False, "definition": _WORKFLOW_DEF},
    )
    assert res.status_code == 404


async def test_update_workflow(client, admin_headers, session_factory):
    await _seed_agent(session_factory)
    async with session_factory() as session:
        wf = AgentWorkflow(owner_agent_slug="hr", name="Old", enabled=False, definition=_WORKFLOW_DEF)
        session.add(wf)
        await session.commit()
        await session.refresh(wf)
    res = await client.put(
        f"/api/admin/agents/hr/workflows/{wf.id}",
        headers=admin_headers,
        json={"name": "Updated", "enabled": True},
    )
    assert res.status_code == 200
    assert res.json()["name"] == "Updated"
    assert res.json()["enabled"] is True


async def test_update_nonexistent_workflow(client, admin_headers):
    import uuid
    res = await client.put(
        f"/api/admin/agents/hr/workflows/{uuid.uuid4()}",
        headers=admin_headers,
        json={"name": "X"},
    )
    assert res.status_code == 404


async def test_delete_workflow(client, admin_headers, session_factory):
    await _seed_agent(session_factory)
    async with session_factory() as session:
        wf = AgentWorkflow(owner_agent_slug="hr", name="Del", enabled=False, definition=_WORKFLOW_DEF)
        session.add(wf)
        await session.commit()
        await session.refresh(wf)
    res = await client.delete(f"/api/admin/agents/hr/workflows/{wf.id}", headers=admin_headers)
    assert res.status_code == 204


async def test_delete_nonexistent_workflow(client, admin_headers):
    import uuid
    res = await client.delete(f"/api/admin/agents/hr/workflows/{uuid.uuid4()}", headers=admin_headers)
    assert res.status_code == 404
