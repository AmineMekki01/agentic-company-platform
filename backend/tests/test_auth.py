import pytest

from app.core.security import create_access_token

pytestmark = pytest.mark.asyncio

CREDS = {"email": "alice@example.com", "password": "password123"}


async def test_login_success(client, create_test_user):
    user = await create_test_user(CREDS["email"], CREDS["password"])
    res = await client.post("/api/auth/login", json=CREDS)
    assert res.status_code == 200
    assert res.json()["access_token"]


async def test_login_wrong_password(client, create_test_user):
    await create_test_user(CREDS["email"], CREDS["password"])
    res = await client.post(
        "/api/auth/login", json={"email": CREDS["email"], "password": "wrong-password"}
    )
    assert res.status_code == 401


async def test_login_nonexistent_user(client):
    res = await client.post("/api/auth/login", json=CREDS)
    assert res.status_code == 401


async def test_me_requires_auth(client):
    res = await client.get("/api/auth/me")
    assert res.status_code == 401


async def test_me_with_token(client, create_test_user):
    user = await create_test_user(CREDS["email"], CREDS["password"])
    token = create_access_token(user.id, user.role)
    res = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json()["email"] == CREDS["email"]
