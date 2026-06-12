import pytest

pytestmark = pytest.mark.asyncio


async def test_list_requires_auth(client):
    res = await client.get("/api/conversations")
    assert res.status_code == 401


async def test_create_and_list(client, auth_headers):
    created = await client.post("/api/conversations", headers=auth_headers)
    assert created.status_code == 201
    assert created.json()["title"] is None

    listed = await client.get("/api/conversations", headers=auth_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1


async def test_get_detail_empty_messages(client, auth_headers):
    convo = (await client.post("/api/conversations", headers=auth_headers)).json()
    detail = await client.get(f"/api/conversations/{convo['id']}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["messages"] == []


async def test_cannot_access_other_users_conversation(client, auth_headers, create_test_user):
    convo = (await client.post("/api/conversations", headers=auth_headers)).json()

    other = await create_test_user("other@example.com", "password123")
    from app.core.security import create_access_token
    token = create_access_token(other.id, other.role)
    other_headers = {"Authorization": f"Bearer {token}"}

    res = await client.get(f"/api/conversations/{convo['id']}", headers=other_headers)
    assert res.status_code == 404


async def test_delete_conversation(client, auth_headers):
    convo = (await client.post("/api/conversations", headers=auth_headers)).json()
    deleted = await client.delete(
        f"/api/conversations/{convo['id']}", headers=auth_headers
    )
    assert deleted.status_code == 204

    listed = await client.get("/api/conversations", headers=auth_headers)
    assert listed.json() == []
