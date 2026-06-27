"""Tests for knowledge sources API."""

import pytest
from cryptography.fernet import Fernet
from unittest.mock import MagicMock

from app.core.config import settings
from app.models import Connector, KnowledgeSource

pytestmark = pytest.mark.asyncio


async def test_list_knowledge_sources_admin_only(client, auth_headers):
    res = await client.get("/api/admin/knowledge-sources", headers=auth_headers)
    assert res.status_code == 403


async def test_create_knowledge_source(client, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    connector = await client.post(
        "/api/admin/connectors",
        headers=admin_headers,
        json={"slug": "s3-conn", "name": "S3", "connector_type": "s3", "credentials": {"k": "v"}},
    )
    res = await client.post(
        "/api/admin/knowledge-sources",
        headers=admin_headers,
        json={
            "slug": "my-source",
            "name": "My Source",
            "source_type": "s3",
            "config": {"bucket": "test-bucket", "prefix": "data/"},
            "connector_id": connector.json()["id"],
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
    from cryptography.fernet import Fernet
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    await client.post(
        "/api/admin/connectors",
        headers=admin_headers,
        json={"slug": "s3-conn-dup", "name": "S3", "connector_type": "s3", "credentials": {"k": "v"}},
    )
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
    from app.models import KnowledgeSource
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
    from app.models import KnowledgeSource, Connector
    from cryptography.fernet import Fernet
    from app.core.encryption import EncryptionService

    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    crypto = EncryptionService()
    creds_encrypted = crypto.encrypt('{"token": "test_token"}')

    async with session_factory() as session:
        connector = Connector(slug="notion-conn", name="Notion", connector_type="notion", credentials_encrypted=creds_encrypted)
        session.add(connector)
        await session.commit()
        await session.refresh(connector)
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
    from app.models import KnowledgeSource, Connector
    from cryptography.fernet import Fernet
    from app.core.encryption import EncryptionService

    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    crypto = EncryptionService()
    creds_encrypted = crypto.encrypt('{"token": "test_token"}')

    async with session_factory() as session:
        connector = Connector(slug="notion-conn-p", name="NotionP", connector_type="notion", credentials_encrypted=creds_encrypted)
        session.add(connector)
        await session.commit()
        await session.refresh(connector)
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
    from app.models import KnowledgeSource, Connector
    from cryptography.fernet import Fernet
    from app.core.encryption import EncryptionService

    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    crypto = EncryptionService()
    creds_encrypted = crypto.encrypt('{"access_key": "ak", "secret_key": "sk"}')

    async with session_factory() as session:
        connector = Connector(slug="s3-conn-sync", name="S3Sync", connector_type="s3", credentials_encrypted=creds_encrypted)
        session.add(connector)
        await session.commit()
        await session.refresh(connector)
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
    from app.models import KnowledgeSource, Connector
    from cryptography.fernet import Fernet
    from app.core.encryption import EncryptionService

    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    crypto = EncryptionService()
    creds_encrypted = crypto.encrypt('{"service_account_json": "{}"}')

    async with session_factory() as session:
        connector = Connector(slug="gdrive-conn", name="GDrive", connector_type="gdrive", credentials_encrypted=creds_encrypted)
        session.add(connector)
        await session.commit()
        await session.refresh(connector)
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
    from app.models import KnowledgeSource, Connector
    from cryptography.fernet import Fernet
    from app.core.encryption import EncryptionService

    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    crypto = EncryptionService()
    creds_encrypted = crypto.encrypt('{"token": "tok"}')

    async with session_factory() as session:
        connector = Connector(slug="notion-conn-nocfg", name="NotionNoCfg", connector_type="notion", credentials_encrypted=creds_encrypted)
        session.add(connector)
        await session.commit()
        await session.refresh(connector)
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
    from app.models import KnowledgeSource, Connector
    from cryptography.fernet import Fernet
    from app.core.encryption import EncryptionService

    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    crypto = EncryptionService()
    creds_encrypted = crypto.encrypt('{"access_key": "ak", "secret_key": "sk"}')

    async with session_factory() as session:
        connector = Connector(slug="s3-conn-nobucket", name="S3NoBucket", connector_type="s3", credentials_encrypted=creds_encrypted)
        session.add(connector)
        await session.commit()
        await session.refresh(connector)
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
    from app.models import KnowledgeSource, Connector
    from cryptography.fernet import Fernet
    from app.core.encryption import EncryptionService

    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    crypto = EncryptionService()
    creds_encrypted = crypto.encrypt('{"service_account_json": "{}"}')

    async with session_factory() as session:
        connector = Connector(slug="gdrive-conn-nofolder", name="GDriveNoFolder", connector_type="gdrive", credentials_encrypted=creds_encrypted)
        session.add(connector)
        await session.commit()
        await session.refresh(connector)
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
