"""Tests for connector management API. Connectors reference a Secret for credentials."""

import pytest
from cryptography.fernet import Fernet

from app.core.config import settings
from app.models import Connector

pytestmark = pytest.mark.asyncio


async def _create_s3_secret(client, admin_headers, slug="s3-secret", **creds) -> str:
    """Create an s3-type secret and return its id."""
    credentials = {"access_key": "AKIA...", "secret_key": "secret", **creds}
    res = await client.post(
        "/api/admin/secrets",
        headers=admin_headers,
        json={"slug": slug, "name": "S3 Secret", "secret_type": "s3", "credentials": credentials},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


async def test_list_connectors_admin_only(client, auth_headers):
    res = await client.get("/api/admin/connectors", headers=auth_headers)
    assert res.status_code == 403


async def test_create_and_list_connectors(client, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    secret_id = await _create_s3_secret(client, admin_headers)
    res = await client.post(
        "/api/admin/connectors",
        headers=admin_headers,
        json={"slug": "my-s3", "name": "My S3", "connector_type": "s3", "secret_id": secret_id},
    )
    assert res.status_code == 201, res.text
    assert res.json()["slug"] == "my-s3"
    assert "credentials" not in res.json()

    listed = await client.get("/api/admin/connectors", headers=admin_headers)
    assert listed.status_code == 200
    assert any(c["slug"] == "my-s3" for c in listed.json())


async def test_create_connector_type_mismatch(client, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    secret_id = await _create_s3_secret(client, admin_headers, slug="mismatch-secret")
    res = await client.post(
        "/api/admin/connectors",
        headers=admin_headers,
        json={"slug": "bad-type", "name": "Bad", "connector_type": "notion", "secret_id": secret_id},
    )
    assert res.status_code == 400


async def test_create_duplicate_slug(client, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    secret_id = await _create_s3_secret(client, admin_headers, slug="dup-secret")
    await client.post(
        "/api/admin/connectors",
        headers=admin_headers,
        json={"slug": "dup", "name": "Dup", "connector_type": "s3", "secret_id": secret_id},
    )
    res = await client.post(
        "/api/admin/connectors",
        headers=admin_headers,
        json={"slug": "dup", "name": "Dup2", "connector_type": "s3", "secret_id": secret_id},
    )
    assert res.status_code == 409


async def test_create_connector_encrypts_credentials(client, admin_headers, monkeypatch, session_factory):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "fernet_key", key)
    secret_id = await _create_s3_secret(client, admin_headers, slug="enc-secret", secret_key="my-secret")
    await client.post(
        "/api/admin/connectors",
        headers=admin_headers,
        json={"slug": "enc-test", "name": "Enc", "connector_type": "s3", "secret_id": secret_id},
    )
    async with session_factory() as session:
        from sqlalchemy import select
        from app.models import Secret

        secret = await session.scalar(select(Secret).where(Secret.slug == "enc-secret"))
        assert secret is not None
        assert secret.credentials_encrypted != "my-secret"
        assert "my-secret" not in secret.credentials_encrypted


async def test_update_connector_rename_and_repoint(client, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    secret_id = await _create_s3_secret(client, admin_headers, slug="rename-secret")
    other_secret_id = await _create_s3_secret(client, admin_headers, slug="other-secret")
    await client.post(
        "/api/admin/connectors",
        headers=admin_headers,
        json={"slug": "renamable", "name": "Old Name", "connector_type": "s3", "secret_id": secret_id},
    )
    res = await client.patch(
        "/api/admin/connectors/renamable",
        headers=admin_headers,
        json={"name": "New Name", "secret_id": other_secret_id},
    )
    assert res.status_code == 200, res.text
    assert res.json()["name"] == "New Name"
    assert res.json()["secret_id"] == other_secret_id


async def test_delete_connector(client, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    secret_id = await _create_s3_secret(client, admin_headers, slug="del-secret")
    await client.post(
        "/api/admin/connectors",
        headers=admin_headers,
        json={"slug": "del", "name": "Del", "connector_type": "s3", "secret_id": secret_id},
    )
    res = await client.delete("/api/admin/connectors/del", headers=admin_headers)
    assert res.status_code == 204


async def test_delete_nonexistent_connector(client, admin_headers):
    res = await client.delete("/api/admin/connectors/nonexistent", headers=admin_headers)
    assert res.status_code == 404
