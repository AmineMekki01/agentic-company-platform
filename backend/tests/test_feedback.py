"""Tests for feedback API endpoints."""

import uuid
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from app.models import Conversation, Message, MessageFeedback
from app.models.user import User

pytestmark = pytest.mark.asyncio


async def _create_convo_with_messages(session_factory, user_id):
    async with session_factory() as session:
        convo = Conversation(user_id=user_id, title="Test Convo")
        session.add(convo)
        await session.commit()
        await session.refresh(convo)
        user_msg = Message(conversation_id=convo.id, role="user", content="Hello agent")
        ai_msg = Message(conversation_id=convo.id, role="assistant", content="Hello human", agent_id="hr")
        session.add_all([user_msg, ai_msg])
        await session.commit()
        await session.refresh(ai_msg)
        return convo.id, ai_msg.id


async def test_submit_feedback_requires_auth(client):
    res = await client.post(
        f"/api/chat/{uuid.uuid4()}/messages/{uuid.uuid4()}/feedback",
        json={"thumbs_up": True},
    )
    assert res.status_code == 401


async def test_submit_feedback_success(client, auth_headers, session_factory):
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.email == "tester@example.com"))
    convo_id, msg_id = await _create_convo_with_messages(session_factory, user.id)
    res = await client.post(
        f"/api/chat/{convo_id}/messages/{msg_id}/feedback",
        headers=auth_headers,
        json={"thumbs_up": True, "comment": "Great answer!"},
    )
    assert res.status_code == 200
    assert res.json()["thumbs_up"] is True
    assert res.json()["comment"] == "Great answer!"


async def test_submit_feedback_upsert(client, auth_headers, session_factory):
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.email == "tester@example.com"))
    convo_id, msg_id = await _create_convo_with_messages(session_factory, user.id)
    await client.post(
        f"/api/chat/{convo_id}/messages/{msg_id}/feedback",
        headers=auth_headers,
        json={"thumbs_up": True},
    )
    res = await client.post(
        f"/api/chat/{convo_id}/messages/{msg_id}/feedback",
        headers=auth_headers,
        json={"thumbs_up": False, "comment": "Changed my mind"},
    )
    assert res.status_code == 200
    assert res.json()["thumbs_up"] is False
    async with session_factory() as session:
        rows = await session.scalars(
            select(MessageFeedback).where(MessageFeedback.message_id == msg_id)
        )
        feedbacks = rows.all()
        assert len(feedbacks) == 1


async def test_feedback_on_non_assistant_message(client, auth_headers, session_factory):
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.email == "tester@example.com"))
        convo = Conversation(user_id=user.id, title="Test")
        session.add(convo)
        await session.commit()
        await session.refresh(convo)
        user_msg = Message(conversation_id=convo.id, role="user", content="hi")
        session.add(user_msg)
        await session.commit()
        await session.refresh(user_msg)
    res = await client.post(
        f"/api/chat/{convo.id}/messages/{user_msg.id}/feedback",
        headers=auth_headers,
        json={"thumbs_up": True},
    )
    assert res.status_code == 400


async def test_feedback_cross_conversation(client, auth_headers, other_headers, session_factory):
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.email == "tester@example.com"))
    convo_id, msg_id = await _create_convo_with_messages(session_factory, user.id)
    res = await client.post(
        f"/api/chat/{convo_id}/messages/{msg_id}/feedback",
        headers=other_headers,
        json={"thumbs_up": True},
    )
    assert res.status_code == 404


async def test_feedback_nonexistent_message(client, auth_headers, session_factory):
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.email == "tester@example.com"))
        convo = Conversation(user_id=user.id, title="Test")
        session.add(convo)
        await session.commit()
        await session.refresh(convo)
    res = await client.post(
        f"/api/chat/{convo.id}/messages/{uuid.uuid4()}/feedback",
        headers=auth_headers,
        json={"thumbs_up": True},
    )
    assert res.status_code == 404


async def test_feedback_summary_admin_only(client, auth_headers):
    res = await client.get("/api/admin/agents/hr/feedback/summary", headers=auth_headers)
    assert res.status_code == 403


async def test_feedback_summary_stats(client, admin_headers, session_factory):
    async with session_factory() as session:
        admin = await session.scalar(select(User).where(User.email == "admin@example.com"))
        convo = Conversation(user_id=admin.id, title="Test")
        session.add(convo)
        await session.commit()
        await session.refresh(convo)
        msg1 = Message(conversation_id=convo.id, role="assistant", content="reply 1", agent_id="hr")
        msg2 = Message(conversation_id=convo.id, role="assistant", content="reply 2", agent_id="hr")
        session.add_all([msg1, msg2])
        await session.commit()
        await session.refresh(msg1)
        await session.refresh(msg2)
        fb1 = MessageFeedback(message_id=msg1.id, conversation_id=convo.id, user_id=admin.id, agent_id="hr", thumbs_up=True)
        fb2 = MessageFeedback(message_id=msg2.id, conversation_id=convo.id, user_id=admin.id, agent_id="hr", thumbs_up=False)
        session.add_all([fb1, fb2])
        await session.commit()
    res = await client.get("/api/admin/agents/hr/feedback/summary", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 2
    assert data["thumbs_up"] == 1
    assert data["thumbs_down"] == 1
    assert data["up_rate_pct"] == 50.0


async def test_list_agent_feedback_admin_only(client, auth_headers):
    res = await client.get("/api/admin/agents/hr/feedback", headers=auth_headers)
    assert res.status_code == 403


async def test_list_feedback_filter_thumbs_up(client, admin_headers, session_factory):
    async with session_factory() as session:
        admin = await session.scalar(select(User).where(User.email == "admin@example.com"))
        convo = Conversation(user_id=admin.id, title="Test")
        session.add(convo)
        await session.commit()
        await session.refresh(convo)
        msg1 = Message(conversation_id=convo.id, role="assistant", content="reply 1", agent_id="hr")
        msg2 = Message(conversation_id=convo.id, role="assistant", content="reply 2", agent_id="hr")
        session.add_all([msg1, msg2])
        await session.commit()
        await session.refresh(msg1)
        await session.refresh(msg2)
        fb1 = MessageFeedback(message_id=msg1.id, conversation_id=convo.id, user_id=admin.id, agent_id="hr", thumbs_up=True)
        fb2 = MessageFeedback(message_id=msg2.id, conversation_id=convo.id, user_id=admin.id, agent_id="hr", thumbs_up=False)
        session.add_all([fb1, fb2])
        await session.commit()
    res = await client.get("/api/admin/agents/hr/feedback?thumbs_up=true", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["thumbs_up"] is True


async def test_list_feedback_pagination(client, admin_headers, session_factory):
    async with session_factory() as session:
        admin = await session.scalar(select(User).where(User.email == "admin@example.com"))
        convo = Conversation(user_id=admin.id, title="Test")
        session.add(convo)
        await session.commit()
        await session.refresh(convo)
        for i in range(5):
            msg = Message(conversation_id=convo.id, role="assistant", content=f"reply {i}", agent_id="hr")
            session.add(msg)
            await session.commit()
            await session.refresh(msg)
            fb = MessageFeedback(message_id=msg.id, conversation_id=convo.id, user_id=admin.id, agent_id="hr", thumbs_up=True)
            session.add(fb)
        await session.commit()
    res = await client.get("/api/admin/agents/hr/feedback?skip=0&limit=2", headers=admin_headers)
    assert res.status_code == 200
    assert len(res.json()) == 2


async def test_upload_screenshot_requires_auth(client):
    res = await client.post("/api/feedback/upload-screenshot", files={"file": ("test.png", b"data", "image/png")})
    assert res.status_code == 401


async def test_upload_screenshot_non_image(client, auth_headers):
    res = await client.post(
        "/api/feedback/upload-screenshot",
        headers=auth_headers,
        files={"file": ("test.txt", b"hello", "text/plain")},
    )
    assert res.status_code == 400


async def test_upload_screenshot_uploads_disabled(client, auth_headers):
    res = await client.post(
        "/api/feedback/upload-screenshot",
        headers=auth_headers,
        files={"file": ("test.png", b"imgdata", "image/png")},
    )
    assert res.status_code == 400
    assert "disabled" in res.json()["detail"].lower()


async def test_upload_screenshot_no_bucket(client, admin_headers, session_factory):
    from app.models import UploadSettings
    async with session_factory() as session:
        settings = await session.scalar(select(UploadSettings))
        if settings is None:
            settings = UploadSettings(enabled=True, s3_bucket=None)
            session.add(settings)
        else:
            settings.enabled = True
            settings.s3_bucket = None
        await session.commit()

    res = await client.post(
        "/api/feedback/upload-screenshot",
        headers=admin_headers,
        files={"file": ("test.png", b"imgdata", "image/png")},
    )
    assert res.status_code == 503


async def test_upload_screenshot_no_connector(client, admin_headers, session_factory):
    from app.models import UploadSettings
    async with session_factory() as session:
        settings = await session.scalar(select(UploadSettings))
        if settings is None:
            settings = UploadSettings(enabled=True, s3_bucket="test-bucket")
            session.add(settings)
        else:
            settings.enabled = True
            settings.s3_bucket = "test-bucket"
        await session.commit()

    res = await client.post(
        "/api/feedback/upload-screenshot",
        headers=admin_headers,
        files={"file": ("test.png", b"imgdata", "image/png")},
    )
    assert res.status_code == 503


async def test_upload_screenshot_success(client, admin_headers, session_factory, monkeypatch):
    from app.models import UploadSettings
    from cryptography.fernet import Fernet
    from app.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "fernet_key", Fernet.generate_key().decode())

    async with session_factory() as session:
        settings = await session.scalar(select(UploadSettings))
        if settings is None:
            settings = UploadSettings(enabled=True, s3_bucket="test-bucket")
            session.add(settings)
        else:
            settings.enabled = True
            settings.s3_bucket = "test-bucket"
        await session.commit()

    # Create an S3 secret, then a connector referencing it
    secret_res = await client.post(
        "/api/admin/secrets",
        headers=admin_headers,
        json={"slug": "s3-test-secret", "name": "S3 Test Secret", "secret_type": "s3", "credentials": {"access_key": "ak", "secret_key": "sk"}},
    )
    await client.post(
        "/api/admin/connectors",
        headers=admin_headers,
        json={"slug": "s3-test", "name": "S3 Test", "connector_type": "s3", "secret_id": secret_res.json()["id"]},
    )

    # Mock boto3 S3 client
    mock_s3 = MagicMock()
    mock_s3.put_object = MagicMock()
    monkeypatch.setattr("app.api.feedback._get_s3_client", lambda creds: mock_s3)

    res = await client.post(
        "/api/feedback/upload-screenshot",
        headers=admin_headers,
        files={"file": ("screenshot.png", b"fake-image-data", "image/png")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["filename"] == "screenshot.png"
    assert data["mime_type"] == "image/png"
    assert data["file_size"] == len(b"fake-image-data")
    mock_s3.put_object.assert_called_once()


async def test_feedback_with_screenshot_attachment(client, auth_headers, admin_headers, session_factory, monkeypatch):
    from app.models import UploadSettings, FeedbackAttachment
    from cryptography.fernet import Fernet
    from app.core.config import settings as app_settings

    monkeypatch.setattr(app_settings, "fernet_key", Fernet.generate_key().decode())

    async with session_factory() as session:
        settings = await session.scalar(select(UploadSettings))
        if settings is None:
            settings = UploadSettings(enabled=True, s3_bucket="test-bucket")
            session.add(settings)
        else:
            settings.enabled = True
            settings.s3_bucket = "test-bucket"
        await session.commit()

    secret_res = await client.post(
        "/api/admin/secrets",
        headers=admin_headers,
        json={"slug": "s3-test2-secret", "name": "S3 Test2 Secret", "secret_type": "s3", "credentials": {"access_key": "ak", "secret_key": "sk"}},
    )
    await client.post(
        "/api/admin/connectors",
        headers=admin_headers,
        json={"slug": "s3-test2", "name": "S3 Test2", "connector_type": "s3", "secret_id": secret_res.json()["id"]},
    )

    mock_s3 = MagicMock()
    mock_s3.put_object = MagicMock()
    monkeypatch.setattr("app.api.feedback._get_s3_client", lambda creds: mock_s3)

    upload_res = await client.post(
        "/api/feedback/upload-screenshot",
        headers=auth_headers,
        files={"file": ("shot.png", b"img", "image/png")},
    )
    assert upload_res.status_code == 200
    attachment_id = upload_res.json()["id"]

    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.email == "tester@example.com"))
    convo_id, msg_id = await _create_convo_with_messages(session_factory, user.id)

    res = await client.post(
        f"/api/chat/{convo_id}/messages/{msg_id}/feedback",
        headers=auth_headers,
        json={"thumbs_up": True, "screenshot_attachment_id": attachment_id},
    )
    assert res.status_code == 200
    assert res.json()["thumbs_up"] is True


async def test_feedback_invalid_screenshot_attachment(client, auth_headers, session_factory):
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.email == "tester@example.com"))
    convo_id, msg_id = await _create_convo_with_messages(session_factory, user.id)

    res = await client.post(
        f"/api/chat/{convo_id}/messages/{msg_id}/feedback",
        headers=auth_headers,
        json={"thumbs_up": True, "screenshot_attachment_id": str(uuid.uuid4())},
    )
    assert res.status_code == 400
    assert "Invalid screenshot" in res.json()["detail"]


async def test_feedback_summary_empty(client, admin_headers):
    res = await client.get("/api/admin/agents/nonexistent/feedback/summary", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert data["up_rate_pct"] == 0.0


async def test_feedback_extracts_jira_actions(client, auth_headers, session_factory):
    async with session_factory() as session:
        user = await session.scalar(select(User).where(User.email == "tester@example.com"))
        convo = Conversation(user_id=user.id, title="Test")
        session.add(convo)
        await session.commit()
        await session.refresh(convo)
        user_msg = Message(conversation_id=convo.id, role="user", content="Create a ticket")
        sys_msg = Message(
            conversation_id=convo.id,
            role="assistant",
            content="Created Jira ticket [PROJ-123](https://test.atlassian.net/browse/PROJ-123): Fix login bug",
            agent_id="system",
        )
        ai_msg = Message(conversation_id=convo.id, role="assistant", content="Done", agent_id="hr")
        session.add_all([user_msg, sys_msg, ai_msg])
        await session.commit()
        await session.refresh(ai_msg)

    res = await client.post(
        f"/api/chat/{convo.id}/messages/{ai_msg.id}/feedback",
        headers=auth_headers,
        json={"thumbs_up": True},
    )
    assert res.status_code == 200

    async with session_factory() as session:
        fb = await session.scalar(select(MessageFeedback).where(MessageFeedback.message_id == ai_msg.id))
        assert fb is not None
        assert len(fb.conversation_actions) == 1
        assert fb.conversation_actions[0]["type"] == "jira_ticket_created"
        assert fb.conversation_actions[0]["ticket_key"] == "PROJ-123"
