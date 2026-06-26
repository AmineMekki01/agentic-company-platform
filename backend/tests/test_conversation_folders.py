"""Tests for conversation folders API."""

import uuid

import pytest

pytestmark = pytest.mark.asyncio


async def test_list_folders_requires_auth(client):
    res = await client.get("/api/conversation-folders")
    assert res.status_code == 401


async def test_create_and_list_folders(client, auth_headers):
    created = await client.post(
        "/api/conversation-folders", headers=auth_headers, json={"name": "Work"}
    )
    assert created.status_code == 201
    assert created.json()["name"] == "Work"

    listed = await client.get("/api/conversation-folders", headers=auth_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["name"] == "Work"


async def test_update_folder_name(client, auth_headers):
    folder = (await client.post(
        "/api/conversation-folders", headers=auth_headers, json={"name": "Old"}
    )).json()
    res = await client.put(
        f"/api/conversation-folders/{folder['id']}", headers=auth_headers, json={"name": "New"}
    )
    assert res.status_code == 200
    assert res.json()["name"] == "New"


async def test_update_folder_color(client, auth_headers):
    folder = (await client.post(
        "/api/conversation-folders", headers=auth_headers, json={"name": "Test", "color": "#ff0000"}
    )).json()
    res = await client.put(
        f"/api/conversation-folders/{folder['id']}", headers=auth_headers, json={"color": "#00ff00"}
    )
    assert res.status_code == 200
    assert res.json()["color"] == "#00ff00"


async def test_delete_folder(client, auth_headers):
    folder = (await client.post(
        "/api/conversation-folders", headers=auth_headers, json={"name": "ToDelete"}
    )).json()
    res = await client.delete(f"/api/conversation-folders/{folder['id']}", headers=auth_headers)
    assert res.status_code == 204

    listed = await client.get("/api/conversation-folders", headers=auth_headers)
    assert listed.json() == []


async def test_cross_user_folder_isolation(client, auth_headers, other_headers):
    folder = (await client.post(
        "/api/conversation-folders", headers=auth_headers, json={"name": "Mine"}
    )).json()

    listed = await client.get("/api/conversation-folders", headers=other_headers)
    assert listed.status_code == 200
    assert listed.json() == []

    res = await client.put(
        f"/api/conversation-folders/{folder['id']}", headers=other_headers, json={"name": "Hacked"}
    )
    assert res.status_code == 404

    res = await client.delete(f"/api/conversation-folders/{folder['id']}", headers=other_headers)
    assert res.status_code == 404


async def test_create_folder_with_color(client, auth_headers):
    res = await client.post(
        "/api/conversation-folders",
        headers=auth_headers,
        json={"name": "Colored", "color": "#3b82f6"},
    )
    assert res.status_code == 201
    assert res.json()["color"] == "#3b82f6"
