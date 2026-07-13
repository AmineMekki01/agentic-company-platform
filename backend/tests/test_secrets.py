"""Tests for the Secrets vault API."""

import pytest
from cryptography.fernet import Fernet

from app.core.config import settings

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _fernet_key(monkeypatch):
    monkeypatch.setattr(settings, "fernet_key", Fernet.generate_key().decode())


async def test_list_secrets_admin_only(client, auth_headers):
    res = await client.get("/api/admin/secrets", headers=auth_headers)
    assert res.status_code == 403


async def test_create_secret_missing_required_field(client, admin_headers):
    res = await client.post(
        "/api/admin/secrets",
        headers=admin_headers,
        json={"slug": "bad-jira", "name": "Bad Jira", "secret_type": "jira", "credentials": {"base_url": "https://x.atlassian.net"}},
    )
    assert res.status_code == 400
    assert "email" in res.json()["detail"] or "api_token" in res.json()["detail"]


async def test_create_secret_success(client, admin_headers):
    res = await client.post(
        "/api/admin/secrets",
        headers=admin_headers,
        json={
            "slug": "jira-secret",
            "name": "Jira Secret",
            "secret_type": "jira",
            "credentials": {"base_url": "https://x.atlassian.net", "email": "svc@x.com", "api_token": "tok"},
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["slug"] == "jira-secret"
    assert body["connector_count"] == 0
    assert "credentials" not in body
    assert "api_token" not in str(body)


async def test_create_secret_duplicate_slug(client, admin_headers):
    payload = {
        "slug": "dup-secret",
        "name": "Dup",
        "secret_type": "notion",
        "credentials": {"token": "secret-tok"},
    }
    await client.post("/api/admin/secrets", headers=admin_headers, json=payload)
    res = await client.post("/api/admin/secrets", headers=admin_headers, json=payload)
    assert res.status_code == 409


async def test_get_secret_reveals_only_non_sensitive_fields(client, admin_headers):
    await client.post(
        "/api/admin/secrets",
        headers=admin_headers,
        json={
            "slug": "reveal-secret",
            "name": "Reveal",
            "secret_type": "jira",
            "credentials": {"base_url": "https://x.atlassian.net", "email": "svc@x.com", "api_token": "super-secret-token"},
        },
    )
    res = await client.get("/api/admin/secrets/reveal-secret", headers=admin_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["non_sensitive_credentials"] == {"base_url": "https://x.atlassian.net", "email": "svc@x.com"}
    assert "super-secret-token" not in str(body)


async def test_get_secret_custom_type_reveals_nothing(client, admin_headers):
    await client.post(
        "/api/admin/secrets",
        headers=admin_headers,
        json={"slug": "custom-secret", "name": "Custom", "secret_type": "custom", "credentials": {"anything": "value"}},
    )
    res = await client.get("/api/admin/secrets/custom-secret", headers=admin_headers)
    assert res.status_code == 200
    assert res.json()["non_sensitive_credentials"] == {}


async def test_patch_secret_partial_credential_merge(client, admin_headers, session_factory):
    await client.post(
        "/api/admin/secrets",
        headers=admin_headers,
        json={
            "slug": "rotate-secret",
            "name": "Rotate",
            "secret_type": "jira",
            "credentials": {"base_url": "https://x.atlassian.net", "email": "svc@x.com", "api_token": "old-token"},
        },
    )
    res = await client.patch(
        "/api/admin/secrets/rotate-secret",
        headers=admin_headers,
        json={"credentials": {"api_token": "new-token"}},
    )
    assert res.status_code == 200, res.text

    from sqlalchemy import select
    from app.models import Secret
    from app.services.secrets import decrypt_credentials

    async with session_factory() as session:
        secret = await session.scalar(select(Secret).where(Secret.slug == "rotate-secret"))
        creds = decrypt_credentials(secret.credentials_encrypted)
        assert creds["api_token"] == "new-token"
        assert creds["base_url"] == "https://x.atlassian.net"
        assert creds["email"] == "svc@x.com"


async def test_delete_secret_blocked_while_referenced(client, admin_headers):
    secret_res = await client.post(
        "/api/admin/secrets",
        headers=admin_headers,
        json={"slug": "inuse-secret", "name": "In Use", "secret_type": "s3", "credentials": {"access_key": "a", "secret_key": "b"}},
    )
    secret_id = secret_res.json()["id"]
    await client.post(
        "/api/admin/connectors",
        headers=admin_headers,
        json={"slug": "inuse-conn", "name": "In Use Conn", "connector_type": "s3", "secret_id": secret_id},
    )
    res = await client.delete("/api/admin/secrets/inuse-secret", headers=admin_headers)
    assert res.status_code == 409
    assert "In Use Conn" in res.json()["detail"]


async def test_delete_secret_succeeds_when_unreferenced(client, admin_headers):
    await client.post(
        "/api/admin/secrets",
        headers=admin_headers,
        json={"slug": "free-secret", "name": "Free", "secret_type": "notion", "credentials": {"token": "tok"}},
    )
    res = await client.delete("/api/admin/secrets/free-secret", headers=admin_headers)
    assert res.status_code == 204
