"""Tests for agent evaluation API."""

import uuid

import pytest

from app.models import AgentEvalRun, AgentEvalTestSet, AgentSettings

pytestmark = pytest.mark.asyncio


async def _seed_agent(session_factory, slug="hr"):
    async with session_factory() as session:
        agent = AgentSettings(slug=slug, name="HR")
        session.add(agent)
        await session.commit()
        await session.refresh(agent)
        return agent


async def _seed_test_set(session_factory, agent, name="Set 1"):
    async with session_factory() as session:
        ts = AgentEvalTestSet(agent_id=agent.id, name=name, created_by="admin@example.com")
        session.add(ts)
        await session.commit()
        await session.refresh(ts)
        return ts


async def test_list_eval_test_sets_admin_only(client, auth_headers):
    res = await client.get("/api/admin/agents/hr/eval-test-sets", headers=auth_headers)
    assert res.status_code == 403


async def test_list_eval_test_sets(client, admin_headers, session_factory):
    await _seed_agent(session_factory)
    res = await client.get("/api/admin/agents/hr/eval-test-sets", headers=admin_headers)
    assert res.status_code == 200
    assert res.json() == []


async def test_create_eval_test_set(client, admin_headers, session_factory):
    await _seed_agent(session_factory)
    res = await client.post(
        "/api/admin/agents/hr/eval-test-sets",
        headers=admin_headers,
        json={"name": "Onboarding Tests", "description": "Basic onboarding Q&A"},
    )
    assert res.status_code == 201
    assert res.json()["name"] == "Onboarding Tests"
    assert res.json()["created_by"] == "admin@example.com"


async def test_create_eval_test_in_set(client, admin_headers, session_factory):
    agent = await _seed_agent(session_factory)
    ts = await _seed_test_set(session_factory, agent)
    res = await client.post(
        f"/api/admin/agents/hr/eval-test-sets/{ts.id}/tests",
        headers=admin_headers,
        json={"question": "What is PTO?", "expected_answer": "Paid time off"},
    )
    assert res.status_code == 201
    assert res.json()["question"] == "What is PTO?"


async def test_update_eval_test_set(client, admin_headers, session_factory):
    agent = await _seed_agent(session_factory)
    ts = await _seed_test_set(session_factory, agent)
    res = await client.put(
        f"/api/admin/agents/hr/eval-test-sets/{ts.id}",
        headers=admin_headers,
        json={"name": "Updated Name"},
    )
    assert res.status_code == 200
    assert res.json()["name"] == "Updated Name"


async def test_delete_eval_test_set(client, admin_headers, session_factory):
    agent = await _seed_agent(session_factory)
    ts = await _seed_test_set(session_factory, agent)
    res = await client.delete(f"/api/admin/agents/hr/eval-test-sets/{ts.id}", headers=admin_headers)
    assert res.status_code == 204


async def test_list_eval_runs(client, admin_headers, session_factory):
    await _seed_agent(session_factory)
    res = await client.get("/api/admin/agents/hr/eval-runs", headers=admin_headers)
    assert res.status_code == 200
    assert res.json() == []


async def test_create_eval_run(client, admin_headers, session_factory, monkeypatch):
    agent = await _seed_agent(session_factory)
    ts = await _seed_test_set(session_factory, agent)

    async def fake_delay(*args, **kwargs):
        pass
    monkeypatch.setattr("app.tasks.eval_tasks.execute_eval_run.delay", fake_delay)

    res = await client.post(
        "/api/admin/agents/hr/eval-runs",
        headers=admin_headers,
        json={"name": "Run 1", "test_set_ids": [str(ts.id)]},
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
    res = await client.get(f"/api/admin/agents/hr/eval-runs/{uuid.uuid4()}", headers=admin_headers)
    assert res.status_code == 404
