"""Tests for admin agent templates API."""

import pytest

from app.models import AgentSettings

pytestmark = pytest.mark.asyncio


async def test_list_templates_admin_only(client, auth_headers):
    res = await client.get("/api/admin/agent-templates", headers=auth_headers)
    assert res.status_code == 403


async def test_list_templates(client, admin_headers):
    res = await client.get("/api/admin/agent-templates", headers=admin_headers)
    assert res.status_code == 200
    templates = res.json()
    assert isinstance(templates, list)
    assert len(templates) > 0
    ids = [t["id"] for t in templates]
    assert "hr_specialist" in ids


async def test_get_template_detail(client, admin_headers):
    res = await client.get("/api/admin/agent-templates/hr_specialist", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "hr_specialist"
    assert "agent_config" in data


async def test_get_nonexistent_template(client, admin_headers):
    res = await client.get("/api/admin/agent-templates/nonexistent", headers=admin_headers)
    assert res.status_code == 404


async def test_deploy_template(client, admin_headers, monkeypatch):
    monkeypatch.setattr("app.api.admin_agent_templates.load_template", lambda tid: {
        "id": tid,
        "name": "Test Template",
        "agent_config": {"slug": "test", "name": "Test", "tools": ["retrieve"]},
        "workflows": [],
    })
    res = await client.post(
        "/api/admin/agent-templates/test/deploy",
        headers=admin_headers,
        json={"slug": "deployed-test"},
    )
    assert res.status_code == 201
    assert res.json()["slug"] == "deployed-test"


async def test_deploy_duplicate_slug(client, admin_headers, session_factory):
    async with session_factory() as session:
        session.add(AgentSettings(slug="dup-deploy", name="Existing"))
        await session.commit()
    res = await client.post(
        "/api/admin/agent-templates/hr_specialist/deploy",
        headers=admin_headers,
        json={"slug": "dup-deploy"},
    )
    assert res.status_code == 409


async def test_deploy_template_with_custom_name(client, admin_headers, monkeypatch):
    monkeypatch.setattr("app.api.admin_agent_templates.load_template", lambda tid: {
        "id": tid,
        "name": "Original",
        "agent_config": {"slug": "test", "name": "Original", "tools": []},
        "workflows": [],
    })
    res = await client.post(
        "/api/admin/agent-templates/test/deploy",
        headers=admin_headers,
        json={"slug": "custom-name", "name": "Custom Name"},
    )
    assert res.status_code == 201
    assert res.json()["name"] == "Custom Name"
