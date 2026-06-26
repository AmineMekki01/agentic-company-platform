"""Tests for admin agent settings API."""

import pytest
from sqlalchemy import select

from app.models import AgentSettings, AgentVersion, Connector, UploadSettings

pytestmark = pytest.mark.asyncio


async def _seed_agent(session_factory, slug="hr", **kwargs):
    async with session_factory() as session:
        agent = AgentSettings(slug=slug, name=kwargs.get("name", "HR Agent"), **{k: v for k, v in kwargs.items() if k != "name"})
        session.add(agent)
        await session.commit()
        await session.refresh(agent)
        return agent


async def _seed_upload_settings(session_factory, monkeypatch=None):
    from cryptography.fernet import Fernet
    from app.core.config import settings
    if monkeypatch:
        monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    async with session_factory() as session:
        conn = Connector(slug="s3-uploads", name="S3", connector_type="s3", credentials_encrypted="enc")
        session.add(conn)
        await session.commit()
        await session.refresh(conn)
        us = UploadSettings(enabled=True, s3_connector_id=conn.id, s3_bucket="test")
        session.add(us)
        await session.commit()


async def test_list_models_admin_only(client, auth_headers):
    res = await client.get("/api/admin/agents/models", headers=auth_headers)
    assert res.status_code == 403


async def test_list_models(client, admin_headers):
    res = await client.get("/api/admin/agents/models", headers=admin_headers)
    assert res.status_code == 200
    models = res.json()
    assert isinstance(models, list)
    assert "gpt-5.4-nano" in models
    assert models[0] == "gpt-5.4-nano"


async def test_list_agent_settings(client, admin_headers, session_factory):
    await _seed_agent(session_factory, slug="hr", name="HR")
    res = await client.get("/api/admin/agents", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert any(a["slug"] == "hr" for a in data)


async def test_get_agent_setting(client, admin_headers, session_factory):
    await _seed_agent(session_factory, slug="hr", name="HR")
    res = await client.get("/api/admin/agents/hr", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["slug"] == "hr"


async def test_get_nonexistent_agent(client, admin_headers):
    res = await client.get("/api/admin/agents/nonexistent", headers=admin_headers)
    assert res.status_code == 404


async def test_create_agent_setting(client, admin_headers, session_factory, monkeypatch):
    await _seed_upload_settings(session_factory, monkeypatch)
    res = await client.post(
        "/api/admin/agents",
        headers=admin_headers,
        json={"slug": "new-agent", "name": "New Agent", "system_prompt": "You are new."},
    )
    assert res.status_code == 201
    assert res.json()["slug"] == "new-agent"


async def test_create_duplicate_slug(client, admin_headers, session_factory):
    await _seed_agent(session_factory, slug="dup")
    res = await client.post(
        "/api/admin/agents",
        headers=admin_headers,
        json={"slug": "dup", "name": "Duplicate"},
    )
    assert res.status_code == 409


async def test_create_agent_restricted_visibility(client, admin_headers, session_factory, monkeypatch):
    await _seed_upload_settings(session_factory, monkeypatch)
    res = await client.post(
        "/api/admin/agents",
        headers=admin_headers,
        json={
            "slug": "restricted-agent",
            "name": "Restricted",
            "visibility": "restricted",
            "allowed_users": ["someone@example.com"],
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["visibility"] == "restricted"
    assert "admin@example.com" in data["allowed_users"]


async def test_update_agent_setting(client, admin_headers, session_factory):
    await _seed_agent(session_factory, slug="hr", name="HR")
    res = await client.put(
        "/api/admin/agents/hr",
        headers=admin_headers,
        json={"system_prompt": "Updated prompt"},
    )
    assert res.status_code == 200
    assert res.json()["system_prompt"] == "Updated prompt"


async def test_update_nonexistent_agent(client, admin_headers):
    res = await client.put(
        "/api/admin/agents/nonexistent",
        headers=admin_headers,
        json={"name": "Test"},
    )
    assert res.status_code == 404


async def test_delete_agent_setting(client, admin_headers, session_factory):
    await _seed_agent(session_factory, slug="todelete")
    res = await client.delete("/api/admin/agents/todelete", headers=admin_headers)
    assert res.status_code == 204


async def test_delete_nonexistent_agent(client, admin_headers):
    res = await client.delete("/api/admin/agents/nonexistent", headers=admin_headers)
    assert res.status_code == 404


async def test_list_agent_versions(client, admin_headers, session_factory):
    agent = await _seed_agent(session_factory, slug="hr")
    async with session_factory() as session:
        v1 = AgentVersion(agent_settings_id=agent.id, version_number=1, config={"name": "v1"}, notes="initial")
        session.add(v1)
        await session.commit()
    res = await client.get("/api/admin/agents/hr/versions", headers=admin_headers)
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["version_number"] == 1


async def test_save_agent_draft(client, admin_headers, session_factory):
    await _seed_agent(session_factory, slug="hr", name="HR", system_prompt="old")
    res = await client.post(
        "/api/admin/agents/hr/draft",
        headers=admin_headers,
        json={"system_prompt": "new draft prompt"},
    )
    assert res.status_code == 200
    assert res.json()["draft_config"] is not None
    assert res.json()["draft_config"]["system_prompt"] == "new draft prompt"


async def test_save_draft_filters_unchanged(client, admin_headers, session_factory):
    await _seed_agent(session_factory, slug="hr", name="HR", system_prompt="same")
    res = await client.post(
        "/api/admin/agents/hr/draft",
        headers=admin_headers,
        json={"system_prompt": "same"},
    )
    assert res.status_code == 200
    assert res.json()["draft_config"] is None


async def test_publish_agent(client, admin_headers, session_factory, monkeypatch):
    await _seed_upload_settings(session_factory, monkeypatch)
    await _seed_agent(session_factory, slug="hr", name="HR")
    res = await client.post(
        "/api/admin/agents/hr/publish",
        headers=admin_headers,
        json={"notes": "Initial publish"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_published"] is True
    assert data["published_at"] is not None


async def test_publish_with_draft(client, admin_headers, session_factory, monkeypatch):
    await _seed_upload_settings(session_factory, monkeypatch)
    await _seed_agent(session_factory, slug="hr", name="HR", system_prompt="live")
    await client.post(
        "/api/admin/agents/hr/draft",
        headers=admin_headers,
        json={"system_prompt": "draft prompt"},
    )
    res = await client.post(
        "/api/admin/agents/hr/publish",
        headers=admin_headers,
        json={"notes": "Publish with draft"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_published"] is True
    assert data["draft_config"] is None
    assert data["system_prompt"] == "draft prompt"


async def test_restore_agent_version(client, admin_headers, session_factory):
    agent = await _seed_agent(session_factory, slug="hr", name="HR", system_prompt="current")
    async with session_factory() as session:
        v1 = AgentVersion(
            agent_settings_id=agent.id,
            version_number=1,
            config={"name": "HR", "system_prompt": "old prompt", "llm_model": "gpt-5.4-nano", "retrieval_top_k": 5, "retrieval_enabled": True, "web_search_enabled": False, "connected_sources": [], "tools": [], "is_orchestrator": False, "routes_to": [], "mode_profile": None, "visibility": "all", "created_by": None, "allow_uploads": True, "allowed_users": [], "agent_type": "standard", "research_config": None},
            notes="v1",
        )
        session.add(v1)
        await session.commit()
        await session.refresh(v1)
    res = await client.post(
        f"/api/admin/agents/hr/restore/{v1.id}",
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.json()["system_prompt"] == "old prompt"


async def test_restore_nonexistent_version(client, admin_headers, session_factory):
    await _seed_agent(session_factory, slug="hr")
    import uuid
    res = await client.post(
        f"/api/admin/agents/hr/restore/{uuid.uuid4()}",
        headers=admin_headers,
    )
    assert res.status_code == 404


async def test_discard_draft(client, admin_headers, session_factory):
    await _seed_agent(session_factory, slug="hr", name="HR", system_prompt="live")
    await client.post(
        "/api/admin/agents/hr/draft",
        headers=admin_headers,
        json={"system_prompt": "draft"},
    )
    res = await client.post(
        "/api/admin/agents/hr/discard-draft",
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.json()["draft_config"] is None


async def test_get_agent_version_detail(client, admin_headers, session_factory):
    agent = await _seed_agent(session_factory, slug="hr", name="HR")
    async with session_factory() as session:
        v1 = AgentVersion(agent_settings_id=agent.id, version_number=1, config={"name": "HR"}, notes="v1")
        session.add(v1)
        await session.commit()
        await session.refresh(v1)
    res = await client.get(f"/api/admin/agents/hr/versions/{v1.id}", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["version_number"] == 1
    assert res.json()["config"]["name"] == "HR"


async def test_create_agent_uploads_not_configured(client, admin_headers):
    res = await client.post(
        "/api/admin/agents",
        headers=admin_headers,
        json={"slug": "upload-agent", "name": "Upload", "allow_uploads": True},
    )
    assert res.status_code == 400
    assert "upload" in res.json()["detail"].lower()
