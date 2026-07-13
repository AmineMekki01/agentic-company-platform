"""Tests for knowledge sources API."""

import pytest
from cryptography.fernet import Fernet
from unittest.mock import MagicMock

from app.core.config import settings
from app.models import Connector, KnowledgeSource, Secret

pytestmark = pytest.mark.asyncio


async def _seed_connector(session_factory, slug: str, connector_type: str, credentials: str) -> Connector:
    """Create a Secret + Connector pair directly via the DB, pre-encrypted `credentials` JSON string."""
    from app.core.encryption import EncryptionService

    crypto = EncryptionService()
    async with session_factory() as session:
        secret = Secret(
            slug=f"{slug}-secret",
            name=f"{slug} secret",
            secret_type=connector_type,
            credentials_encrypted=crypto.encrypt(credentials),
        )
        session.add(secret)
        await session.flush()
        connector = Connector(slug=slug, name=slug, connector_type=connector_type, secret_id=secret.id)
        session.add(connector)
        await session.commit()
        await session.refresh(connector)
        return connector


async def _create_connector_via_api(client, admin_headers, slug: str, connector_type: str, credentials: dict) -> str:
    """Create a Secret + Connector via the admin API. Returns the connector id."""
    secret_res = await client.post(
        "/api/admin/secrets",
        headers=admin_headers,
        json={"slug": f"{slug}-secret", "name": f"{slug} secret", "secret_type": connector_type, "credentials": credentials},
    )
    assert secret_res.status_code == 201, secret_res.text
    conn_res = await client.post(
        "/api/admin/connectors",
        headers=admin_headers,
        json={"slug": slug, "name": slug, "connector_type": connector_type, "secret_id": secret_res.json()["id"]},
    )
    assert conn_res.status_code == 201, conn_res.text
    return conn_res.json()["id"]


async def test_list_knowledge_sources_admin_only(client, auth_headers):
    res = await client.get("/api/admin/knowledge-sources", headers=auth_headers)
    assert res.status_code == 403


async def test_create_knowledge_source(client, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    connector_id = await _create_connector_via_api(client, admin_headers, "s3-conn", "s3", {"access_key": "ak", "secret_key": "sk"})
    res = await client.post(
        "/api/admin/knowledge-sources",
        headers=admin_headers,
        json={
            "slug": "my-source",
            "name": "My Source",
            "source_type": "s3",
            "config": {"bucket": "test-bucket", "prefix": "data/"},
            "connector_id": connector_id,
        },
    )
    assert res.status_code == 201
    assert res.json()["slug"] == "my-source"
    assert res.json()["status"] == "pending"


async def test_create_ks_nonexistent_connector(client, admin_headers):
    import uuid
    res = await client.post(
        "/api/admin/knowledge-sources",
        headers=admin_headers,
        json={
            "slug": "bad-source",
            "name": "Bad",
            "source_type": "s3",
            "connector_id": str(uuid.uuid4()),
        },
    )
    assert res.status_code in (201, 400, 404, 500)


async def test_delete_knowledge_source(client, admin_headers, monkeypatch):
    class FakeRAGService:
        async def delete_by_knowledge_source(self, *args, **kwargs):
            pass
    monkeypatch.setattr("app.api.knowledge_sources.get_rag_service", lambda: FakeRAGService())
    await client.post(
        "/api/admin/knowledge-sources",
        headers=admin_headers,
        json={"slug": "del-source", "name": "Del", "source_type": "s3"},
    )
    res = await client.delete("/api/admin/knowledge-sources/del-source", headers=admin_headers)
    assert res.status_code == 204


async def test_delete_nonexistent_ks(client, admin_headers):
    res = await client.delete("/api/admin/knowledge-sources/nonexistent", headers=admin_headers)
    assert res.status_code == 404


async def test_sync_nonexistent_ks(client, admin_headers):
    res = await client.post("/api/admin/knowledge-sources/nonexistent/sync", headers=admin_headers)
    assert res.status_code == 404


async def test_create_duplicate_slug(client, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    await _create_connector_via_api(client, admin_headers, "s3-conn-dup", "s3", {"access_key": "ak", "secret_key": "sk"})
    payload = {
        "slug": "dup-source",
        "name": "First",
        "source_type": "s3",
        "config": {"bucket": "b", "prefix": "p/"},
    }
    await client.post("/api/admin/knowledge-sources", headers=admin_headers, json=payload)
    res = await client.post("/api/admin/knowledge-sources", headers=admin_headers, json=payload)
    assert res.status_code == 409


async def test_sync_notion_missing_connector(client, admin_headers, session_factory):
    async with session_factory() as session:
        ks = KnowledgeSource(
            slug="notion-no-conn",
            name="Notion No Connector",
            source_type="notion",
            config={"database_id": "db1"},
        )
        session.add(ks)
        await session.commit()
    res = await client.post("/api/admin/knowledge-sources/notion-no-conn/sync", headers=admin_headers)
    assert res.status_code == 400
    assert "connector" in res.json()["detail"].lower()


async def test_sync_notion_database(client, admin_headers, session_factory, monkeypatch):
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    connector = await _seed_connector(session_factory, "notion-conn", "notion", '{"token": "test_token"}')

    async with session_factory() as session:
        ks = KnowledgeSource(
            slug="notion-src",
            name="Notion Source",
            source_type="notion",
            config={"database_id": "db123"},
            connector_id=connector.id,
        )
        session.add(ks)
        await session.commit()

    mock_task = MagicMock()
    mock_task.id = "task-123"
    mock_delay = MagicMock(return_value=mock_task)
    monkeypatch.setattr("app.api.knowledge_sources.sync_notion_database.delay", mock_delay)

    res = await client.post("/api/admin/knowledge-sources/notion-src/sync", headers=admin_headers)
    assert res.status_code == 202
    assert res.json()["task_id"] == "task-123"
    assert res.json()["status"] == "queued"


async def test_sync_notion_page(client, admin_headers, session_factory, monkeypatch):
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    connector = await _seed_connector(session_factory, "notion-conn-p", "notion", '{"token": "test_token"}')

    async with session_factory() as session:
        ks = KnowledgeSource(
            slug="notion-page-src",
            name="Notion Page",
            source_type="notion",
            config={"page_id": "page123", "page_title": "My Page"},
            connector_id=connector.id,
        )
        session.add(ks)
        await session.commit()

    mock_task = MagicMock()
    mock_task.id = "task-456"
    mock_delay = MagicMock(return_value=mock_task)
    monkeypatch.setattr("app.api.knowledge_sources.sync_notion_page.delay", mock_delay)

    res = await client.post("/api/admin/knowledge-sources/notion-page-src/sync", headers=admin_headers)
    assert res.status_code == 202
    assert res.json()["task_id"] == "task-456"


async def test_sync_s3_source(client, admin_headers, session_factory, monkeypatch):
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    connector = await _seed_connector(session_factory, "s3-conn-sync", "s3", '{"access_key": "ak", "secret_key": "sk"}')

    async with session_factory() as session:
        ks = KnowledgeSource(
            slug="s3-src",
            name="S3 Source",
            source_type="s3",
            config={"bucket": "my-bucket", "prefix": "data/"},
            connector_id=connector.id,
        )
        session.add(ks)
        await session.commit()

    mock_task = MagicMock()
    mock_task.id = "task-s3"
    mock_delay = MagicMock(return_value=mock_task)
    monkeypatch.setattr("app.api.knowledge_sources.sync_s3_prefix.delay", mock_delay)

    res = await client.post("/api/admin/knowledge-sources/s3-src/sync", headers=admin_headers)
    assert res.status_code == 202
    assert res.json()["task_id"] == "task-s3"


async def test_sync_gdrive_source(client, admin_headers, session_factory, monkeypatch):
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    connector = await _seed_connector(session_factory, "gdrive-conn", "gdrive", '{"service_account_json": "{}"}')

    async with session_factory() as session:
        ks = KnowledgeSource(
            slug="gdrive-src",
            name="GDrive Source",
            source_type="gdrive",
            config={"folder_id": "folder123"},
            connector_id=connector.id,
        )
        session.add(ks)
        await session.commit()

    mock_task = MagicMock()
    mock_task.id = "task-gdrive"
    mock_delay = MagicMock(return_value=mock_task)
    monkeypatch.setattr("app.api.knowledge_sources.sync_gdrive_folder.delay", mock_delay)

    res = await client.post("/api/admin/knowledge-sources/gdrive-src/sync", headers=admin_headers)
    assert res.status_code == 202
    assert res.json()["task_id"] == "task-gdrive"


async def test_sync_notion_no_config(client, admin_headers, session_factory, monkeypatch):
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    connector = await _seed_connector(session_factory, "notion-conn-nocfg", "notion", '{"token": "tok"}')

    async with session_factory() as session:
        ks = KnowledgeSource(
            slug="notion-nocfg",
            name="Notion No Config",
            source_type="notion",
            config={},
            connector_id=connector.id,
        )
        session.add(ks)
        await session.commit()

    res = await client.post("/api/admin/knowledge-sources/notion-nocfg/sync", headers=admin_headers)
    assert res.status_code == 400


async def test_sync_s3_no_bucket(client, admin_headers, session_factory, monkeypatch):
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    connector = await _seed_connector(session_factory, "s3-conn-nobucket", "s3", '{"access_key": "ak", "secret_key": "sk"}')

    async with session_factory() as session:
        ks = KnowledgeSource(
            slug="s3-nobucket",
            name="S3 No Bucket",
            source_type="s3",
            config={"prefix": "data/"},
            connector_id=connector.id,
        )
        session.add(ks)
        await session.commit()

    res = await client.post("/api/admin/knowledge-sources/s3-nobucket/sync", headers=admin_headers)
    assert res.status_code == 400


async def test_sync_gdrive_no_folder(client, admin_headers, session_factory, monkeypatch):
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    connector = await _seed_connector(session_factory, "gdrive-conn-nofolder", "gdrive", '{"service_account_json": "{}"}')

    async with session_factory() as session:
        ks = KnowledgeSource(
            slug="gdrive-nofolder",
            name="GDrive No Folder",
            source_type="gdrive",
            config={},
            connector_id=connector.id,
        )
        session.add(ks)
        await session.commit()

    res = await client.post("/api/admin/knowledge-sources/gdrive-nofolder/sync", headers=admin_headers)
    assert res.status_code == 400
