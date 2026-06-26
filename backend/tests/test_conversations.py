import pytest
from sqlalchemy import select

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


# ─── Search endpoint tests ───


async def test_search_requires_auth(client):
    res = await client.get("/api/conversations/search?q=hello")
    assert res.status_code == 401


async def test_search_by_title(client, auth_headers, session_factory):
    from app.models import Conversation
    from app.models.user import User
    import uuid

    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.email == "tester@example.com"))
        c1 = Conversation(user_id=user.id, title="Quarterly Financial Review")
        c2 = Conversation(user_id=user.id, title="HR Onboarding Guide")
        session.add_all([c1, c2])
        await session.commit()

    res = await client.get("/api/conversations/search?q=Financial", headers=auth_headers)
    assert res.status_code == 200
    results = res.json()
    assert len(results) == 1
    assert "Financial" in results[0]["title"]


async def test_search_by_message_content(client, auth_headers, session_factory):
    from app.models import Conversation, Message
    from app.models.user import User
    from sqlalchemy import select as sa_select

    async with session_factory() as session:
        user = await session.scalar(sa_select(User).where(User.email == "tester@example.com"))
        c1 = Conversation(user_id=user.id, title="Random Topic")
        session.add(c1)
        await session.commit()
        await session.refresh(c1)
        msg = Message(conversation_id=c1.id, role="user", content="The quick brown fox jumps over the lazy dog")
        session.add(msg)
        await session.commit()

    res = await client.get("/api/conversations/search?q=brown+fox", headers=auth_headers)
    assert res.status_code == 200
    results = res.json()
    assert len(results) == 1
    assert results[0]["id"] == str(c1.id)


async def test_search_no_results(client, auth_headers):
    res = await client.get("/api/conversations/search?q=zzznonexistent", headers=auth_headers)
    assert res.status_code == 200
    assert res.json() == []


async def test_search_empty_query_rejected(client, auth_headers):
    res = await client.get("/api/conversations/search?q=", headers=auth_headers)
    assert res.status_code == 422


async def test_search_cross_user_isolation(client, auth_headers, other_headers, session_factory):
    from app.models import Conversation
    from app.models.user import User
    from sqlalchemy import select as sa_select

    async with session_factory() as session:
        user = await session.scalar(sa_select(User).where(User.email == "tester@example.com"))
        c = Conversation(user_id=user.id, title="Secret Private Conversation")
        session.add(c)
        await session.commit()

    res = await client.get("/api/conversations/search?q=Secret", headers=other_headers)
    assert res.status_code == 200
    assert res.json() == []


# ─── Folder-related conversation tests ───


async def test_list_with_folder_filter(client, auth_headers):
    folder = (await client.post("/api/conversation-folders", headers=auth_headers, json={"name": "Work"})).json()
    convo = (await client.post("/api/conversations", headers=auth_headers)).json()
    await client.patch(
        f"/api/conversations/{convo['id']}/folder",
        headers=auth_headers,
        json={"folder_id": folder["id"]},
    )
    filtered = await client.get(
        f"/api/conversations?folder_id={folder['id']}", headers=auth_headers
    )
    assert filtered.status_code == 200
    assert len(filtered.json()) == 1
    assert filtered.json()[0]["id"] == convo["id"]


async def test_move_to_folder(client, auth_headers):
    folder = (await client.post("/api/conversation-folders", headers=auth_headers, json={"name": "Work"})).json()
    convo = (await client.post("/api/conversations", headers=auth_headers)).json()
    res = await client.patch(
        f"/api/conversations/{convo['id']}/folder",
        headers=auth_headers,
        json={"folder_id": folder["id"]},
    )
    assert res.status_code == 200
    assert res.json()["folder_id"] == folder["id"]


async def test_move_to_nonexistent_folder(client, auth_headers):
    import uuid
    convo = (await client.post("/api/conversations", headers=auth_headers)).json()
    res = await client.patch(
        f"/api/conversations/{convo['id']}/folder",
        headers=auth_headers,
        json={"folder_id": str(uuid.uuid4())},
    )
    assert res.status_code == 404


async def test_move_cross_user_folder(client, auth_headers, other_headers):
    folder = (await client.post("/api/conversation-folders", headers=other_headers, json={"name": "Other"})).json()
    convo = (await client.post("/api/conversations", headers=auth_headers)).json()
    res = await client.patch(
        f"/api/conversations/{convo['id']}/folder",
        headers=auth_headers,
        json={"folder_id": folder["id"]},
    )
    assert res.status_code == 404


async def test_delete_cross_user(client, auth_headers, other_headers):
    convo = (await client.post("/api/conversations", headers=auth_headers)).json()
    res = await client.delete(f"/api/conversations/{convo['id']}", headers=other_headers)
    assert res.status_code == 404


async def test_create_returns_null_title(client, auth_headers):
    res = await client.post("/api/conversations", headers=auth_headers)
    assert res.status_code == 201
    assert res.json()["title"] is None


async def test_get_conversation_with_messages(client, auth_headers, session_factory):
    from app.models import Conversation, Message
    from app.models.user import User

    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.email == "tester@example.com"))
        convo = Conversation(user_id=user.id, title="With Messages")
        session.add(convo)
        await session.commit()
        await session.refresh(convo)
        msg1 = Message(conversation_id=convo.id, role="user", content="Hello")
        msg2 = Message(conversation_id=convo.id, role="assistant", content="Hi there", agent_id="hr")
        session.add_all([msg1, msg2])
        await session.commit()

    res = await client.get(f"/api/conversations/{convo.id}", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "With Messages"
    assert len(data["messages"]) == 2
    assert data["messages"][0]["role"] == "user"
    assert data["messages"][1]["role"] == "assistant"


async def test_move_conversation_to_null_folder(client, auth_headers):
    folder = (await client.post("/api/conversation-folders", headers=auth_headers, json={"name": "Work"})).json()
    convo = (await client.post("/api/conversations", headers=auth_headers)).json()
    await client.patch(
        f"/api/conversations/{convo['id']}/folder",
        headers=auth_headers,
        json={"folder_id": folder["id"]},
    )
    res = await client.patch(
        f"/api/conversations/{convo['id']}/folder",
        headers=auth_headers,
        json={"folder_id": None},
    )
    assert res.status_code == 200
    assert res.json()["folder_id"] is None


async def test_search_dedup_title_and_message(client, auth_headers, session_factory):
    from app.models import Conversation, Message
    from app.models.user import User

    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.email == "tester@example.com"))
        convo = Conversation(user_id=user.id, title="Unique Search Term")
        session.add(convo)
        await session.commit()
        await session.refresh(convo)
        msg = Message(conversation_id=convo.id, role="user", content="Contains Unique Search Term in body")
        session.add(msg)
        await session.commit()

    res = await client.get("/api/conversations/search?q=Unique+Search+Term", headers=auth_headers)
    assert res.status_code == 200
    results = res.json()
    assert len(results) == 1
    assert results[0]["id"] == str(convo.id)


async def test_list_conversations_unfiled(client, auth_headers):
    folder = (await client.post("/api/conversation-folders", headers=auth_headers, json={"name": "F1"})).json()
    convo1 = (await client.post("/api/conversations", headers=auth_headers)).json()
    convo2 = (await client.post("/api/conversations", headers=auth_headers)).json()
    await client.patch(
        f"/api/conversations/{convo2['id']}/folder",
        headers=auth_headers,
        json={"folder_id": folder["id"]},
    )
    listed = await client.get("/api/conversations", headers=auth_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 2
