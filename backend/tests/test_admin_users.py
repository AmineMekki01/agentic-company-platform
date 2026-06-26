"""Tests for admin users API."""

import pytest

from app.models.user import UserRole

pytestmark = pytest.mark.asyncio


async def test_list_users_admin_only(client, auth_headers):
    res = await client.get("/api/admin/users", headers=auth_headers)
    assert res.status_code == 403


async def test_list_users(client, admin_headers, create_test_user):
    await create_test_user("user1@example.com", "pass")
    await create_test_user("user2@example.com", "pass")
    res = await client.get("/api/admin/users", headers=admin_headers)
    assert res.status_code == 200
    users = res.json()
    emails = [u["email"] for u in users]
    assert "user1@example.com" in emails
    assert "user2@example.com" in emails
    assert "admin@example.com" in emails


async def test_list_users_includes_roles(client, admin_headers):
    res = await client.get("/api/admin/users", headers=admin_headers)
    assert res.status_code == 200
    for u in res.json():
        assert "role" in u
