"""Tests for agent evaluation API."""

import pytest
from sqlalchemy import select

from app.models import AgentEvalRun, AgentEvalTest, AgentSettings

pytestmark = pytest.mark.asyncio


async def _seed_agent(session_factory, slug="hr"):
    async with session_factory() as session:
        agent = AgentSettings(slug=slug, name="HR")
        session.add(agent)
        await session.commit()
        await session.refresh(agent)
        return agent


async def test_list_eval_tests_admin_only(client, auth_headers):
    res = await client.get("/api/admin/agents/hr/eval-tests", headers=auth_headers)
    assert res.status_code == 403


async def test_list_eval_tests(client, admin_headers, session_factory):
    await _seed_agent(session_factory)
    res = await client.get("/api/admin/agents/hr/eval-tests", headers=admin_headers)
    assert res.status_code == 200
    assert res.json() == []


async def test_create_eval_test(client, admin_headers, session_factory):
    await _seed_agent(session_factory)
    res = await client.post(
        "/api/admin/agents/hr/eval-tests",
        headers=admin_headers,
        json={"name": "Test 1", "question": "What is PTO?", "expected_answer": "Paid time off"},
    )
    assert res.status_code == 201
    assert res.json()["name"] == "Test 1"
    assert res.json()["created_by"] == "admin@example.com"


async def test_create_eval_test_nonexistent_agent(client, admin_headers):
    res = await client.post(
        "/api/admin/agents/nonexistent/eval-tests",
        headers=admin_headers,
        json={"name": "T", "question": "Q?", "expected_answer": "A"},
    )
    assert res.status_code == 404


async def test_update_eval_test(client, admin_headers, session_factory):
    agent = await _seed_agent(session_factory)
    async with session_factory() as session:
        test = AgentEvalTest(agent_id=agent.id, name="Old", question="Q?", expected_answer="A", created_by="admin@example.com")
        session.add(test)
        await session.commit()
        await session.refresh(test)
    res = await client.put(
        f"/api/admin/agents/hr/eval-tests/{test.id}",
        headers=admin_headers,
        json={"name": "Updated Name"},
    )
    assert res.status_code == 200
    assert res.json()["name"] == "Updated Name"


async def test_update_nonexistent_test(client, admin_headers):
    import uuid
    res = await client.put(
        f"/api/admin/agents/hr/eval-tests/{uuid.uuid4()}",
        headers=admin_headers,
        json={"name": "X"},
    )
    assert res.status_code == 404


async def test_delete_eval_test(client, admin_headers, session_factory):
    agent = await _seed_agent(session_factory)
    async with session_factory() as session:
        test = AgentEvalTest(agent_id=agent.id, name="Del", question="Q?", expected_answer="A", created_by="admin@example.com")
        session.add(test)
        await session.commit()
        await session.refresh(test)
    res = await client.delete(f"/api/admin/agents/hr/eval-tests/{test.id}", headers=admin_headers)
    assert res.status_code == 204


async def test_list_eval_runs(client, admin_headers, session_factory):
    await _seed_agent(session_factory)
    res = await client.get("/api/admin/agents/hr/eval-runs", headers=admin_headers)
    assert res.status_code == 200
    assert res.json() == []


async def test_create_eval_run(client, admin_headers, session_factory, monkeypatch):
    agent = await _seed_agent(session_factory)
    async with session_factory() as session:
        test = AgentEvalTest(agent_id=agent.id, name="T1", question="Q?", expected_answer="A", created_by="admin@example.com")
        session.add(test)
        await session.commit()
        await session.refresh(test)

    async def fake_delay(*args, **kwargs):
        pass
    monkeypatch.setattr("app.tasks.eval_tasks.execute_eval_run.delay", fake_delay)

    res = await client.post(
        "/api/admin/agents/hr/eval-runs",
        headers=admin_headers,
        json={"name": "Run 1", "test_ids": [str(test.id)]},
    )
    assert res.status_code == 201
    assert res.json()["status"] == "pending"


async def test_get_eval_run_detail(client, admin_headers, session_factory, monkeypatch):
    agent = await _seed_agent(session_factory)
    async with session_factory() as session:
        run = AgentEvalRun(agent_id=agent.id, name="Run 1", status="completed", thresholds={}, created_by="admin@example.com")
        session.add(run)
        await session.commit()
        await session.refresh(run)
    res = await client.get(f"/api/admin/agents/hr/eval-runs/{run.id}", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["name"] == "Run 1"
    assert res.json()["results"] == []


async def test_get_nonexistent_run(client, admin_headers):
    import uuid
    res = await client.get(f"/api/admin/agents/hr/eval-runs/{uuid.uuid4()}", headers=admin_headers)
    assert res.status_code == 404
