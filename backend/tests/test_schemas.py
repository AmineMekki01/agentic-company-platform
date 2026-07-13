"""Tests for Pydantic schemas."""

import uuid
from datetime import UTC, datetime

import pytest

from app.models import Conversation, Message, MessageFeedback, User
from app.schemas.agent_settings import AgentSettingCreate, AgentSettingOut, AgentSettingUpdate
from app.schemas.auth import LoginRequest, UserOut
from app.schemas.chat import (
    ConversationDetail,
    ConversationFolderCreate,
    ConversationOut,
    MessageFeedbackCreate,
    MessageOut,
)
from app.schemas.connector import ConnectorCreate
from app.schemas.knowledge_source import KnowledgeSourceCreate
from app.schemas.upload_settings import UploadSettingsUpdate



async def test_conversation_out_serialization(session_factory):
    async with session_factory() as session:
        user = User(email="schema@example.com", password_hash="x")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        convo = Conversation(user_id=user.id, title="Test")
        session.add(convo)
        await session.commit()
        await session.refresh(convo)
        out = ConversationOut.model_validate(convo)
        assert out.id == convo.id
        assert out.title == "Test"


async def test_conversation_detail_with_messages(session_factory):
    async with session_factory() as session:
        user = User(email="detail@example.com", password_hash="x")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        convo = Conversation(user_id=user.id, title="Detail Test")
        session.add(convo)
        await session.commit()
        await session.refresh(convo)
        msg = Message(conversation_id=convo.id, role="user", content="hello")
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        out = ConversationOut.model_validate(convo)
        msg_out = MessageOut.model_validate(msg)
        detail = ConversationDetail(**out.model_dump(), messages=[msg_out])
        assert len(detail.messages) == 1
        assert detail.messages[0].content == "hello"


def test_message_feedback_create_validation():
    fb = MessageFeedbackCreate(thumbs_up=True, comment="good")
    assert fb.thumbs_up is True
    assert fb.comment == "good"


def test_message_feedback_create_no_comment():
    fb = MessageFeedbackCreate(thumbs_up=False)
    assert fb.thumbs_up is False
    assert fb.comment is None


def test_agent_setting_create_validation():
    agent = AgentSettingCreate(slug="hr", name="HR")
    assert agent.slug == "hr"
    assert agent.retrieval_top_k == 5
    assert agent.visibility == "all"


def test_agent_setting_update_defaults():
    update = AgentSettingUpdate()
    assert update.retrieval_top_k == 5
    assert update.is_orchestrator is False


def test_connector_create_validation():
    import uuid

    secret_id = uuid.uuid4()
    conn = ConnectorCreate(
        slug="s3", name="S3", connector_type="s3",
        secret_id=secret_id,
    )
    assert conn.slug == "s3"
    assert conn.secret_id == secret_id


def test_knowledge_source_create_validation():
    ks = KnowledgeSourceCreate(slug="ks1", name="KS1", source_type="s3")
    assert ks.slug == "ks1"
    assert ks.config is None
    assert ks.connector_id is None


def test_upload_settings_update_partial():
    update = UploadSettingsUpdate(enabled=True)
    assert update.enabled is True
    assert update.retention_days == 30
    assert update.max_file_size_mb == 50


def test_login_request_validation():
    req = LoginRequest(email="user@example.com", password="pass")
    assert req.email == "user@example.com"


def test_user_out_from_model(session_factory):
    import asyncio

    async def _test():
        async with session_factory() as session:
            user = User(email="out@example.com", password_hash="x", role="user")
            session.add(user)
            await session.commit()
            await session.refresh(user)
            out = UserOut.model_validate(user)
            assert out.email == "out@example.com"
            assert out.role == "user"

    asyncio.get_event_loop().run_until_complete(_test())


def test_conversation_folder_create_validation():
    folder = ConversationFolderCreate(name="Work")
    assert folder.name == "Work"
    assert folder.color is None
