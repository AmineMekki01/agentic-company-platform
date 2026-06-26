"""Tests for connector credentials API."""

import pytest
from cryptography.fernet import Fernet

from app.core.config import settings
from app.models import Connector

pytestmark = pytest.mark.asyncio


async def test_list_connectors_admin_only(client, auth_headers):
    res = await client.get("/api/admin/connectors", headers=auth_headers)
    assert res.status_code == 403


async def test_create_and_list_connectors(client, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    res = await client.post(
        "/api/admin/connectors",
        headers=admin_headers,
        json={
            "slug": "my-s3",
            "name": "My S3",
            "connector_type": "s3",
            "credentials": {"access_key": "AKIA...", "secret_key": "secret"},
        },
    )
    assert res.status_code == 201
    assert res.json()["slug"] == "my-s3"
    assert "credentials" not in res.json()

    listed = await client.get("/api/admin/connectors", headers=admin_headers)
    assert listed.status_code == 200
    assert any(c["slug"] == "my-s3" for c in listed.json())


async def test_create_duplicate_slug(client, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    await client.post(
        "/api/admin/connectors",
        headers=admin_headers,
        json={"slug": "dup", "name": "Dup", "connector_type": "s3", "credentials": {"k": "v"}},
    )
    res = await client.post(
        "/api/admin/connectors",
        headers=admin_headers,
        json={"slug": "dup", "name": "Dup2", "connector_type": "s3", "credentials": {"k": "v"}},
    )
    assert res.status_code == 409


async def test_create_connector_encrypts_credentials(client, admin_headers, monkeypatch, session_factory):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "fernet_key", key)
    await client.post(
        "/api/admin/connectors",
        headers=admin_headers,
        json={"slug": "enc-test", "name": "Enc", "connector_type": "s3", "credentials": {"secret": "my-secret"}},
    )
    async with session_factory() as session:
        from sqlalchemy import select
        conn = await session.scalar(select(Connector).where(Connector.slug == "enc-test"))
        assert conn is not None
        assert conn.credentials_encrypted != "my-secret"
        assert "my-secret" not in conn.credentials_encrypted


async def test_delete_connector(client, admin_headers, monkeypatch):
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())
    await client.post(
        "/api/admin/connectors",
        headers=admin_headers,
        json={"slug": "del", "name": "Del", "connector_type": "s3", "credentials": {"k": "v"}},
    )
    res = await client.delete("/api/admin/connectors/del", headers=admin_headers)
    assert res.status_code == 204


async def test_delete_nonexistent_connector(client, admin_headers):
    res = await client.delete("/api/admin/connectors/nonexistent", headers=admin_headers)
    assert res.status_code == 404
