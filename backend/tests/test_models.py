"""Tests for database models."""

import uuid

import pytest

from app.models import (
    AgentSettings,
    Conversation,
    ConversationFolder,
    Message,
    TokenUsage,
    User,
    UserRole,
)

pytestmark = pytest.mark.asyncio


async def test_conversation_defaults(session_factory):
    async with session_factory() as session:
        user = User(email="model@example.com", password_hash="x")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        convo = Conversation(user_id=user.id)
        session.add(convo)
        await session.commit()
        await session.refresh(convo)
        assert convo.title is None
        assert convo.folder_id is None


async def test_message_fields(session_factory):
    async with session_factory() as session:
        user = User(email="msg@example.com", password_hash="x")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        convo = Conversation(user_id=user.id)
        session.add(convo)
        await session.commit()
        await session.refresh(convo)
        msg = Message(conversation_id=convo.id, role="user", content="hello", agent_id="hr")
        session.add(msg)
        await session.commit()
        await session.refresh(msg)
        assert msg.role == "user"
        assert msg.content == "hello"
        assert msg.agent_id == "hr"
        assert msg.citations is None


async def test_agent_settings_defaults(session_factory):
    async with session_factory() as session:
        agent = AgentSettings(slug="test-agent", is_published=False, allow_uploads=True)
        session.add(agent)
        await session.commit()
        await session.refresh(agent)
        assert agent.slug == "test-agent"
        assert agent.visibility == "all"
        assert agent.is_published is False


async def test_token_usage_cost_calculation(session_factory):
    async with session_factory() as session:
        user = User(email="tu@example.com", password_hash="x")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        usage = TokenUsage(
            user_id=user.id,
            agent_slug="hr",
            model="gpt-5.4-nano",
            input_tokens=1000,
            output_tokens=500,
            total_tokens=1500,
            estimated_cost_usd=0.002,
        )
        session.add(usage)
        await session.commit()
        await session.refresh(usage)
        assert usage.estimated_cost_usd == 0.002


async def test_connector_encrypted_field(session_factory):
    from app.models import Connector
    async with session_factory() as session:
        conn = Connector(
            slug="test-conn",
            name="Test",
            connector_type="s3",
            credentials_encrypted="encrypted-string-here",
        )
        session.add(conn)
        await session.commit()
        await session.refresh(conn)
        assert conn.credentials_encrypted == "encrypted-string-here"


async def test_knowledge_source_fields(session_factory):
    from app.models import KnowledgeSource
    async with session_factory() as session:
        ks = KnowledgeSource(slug="test-ks", name="Test KS", source_type="s3")
        session.add(ks)
        await session.commit()
        await session.refresh(ks)
        assert ks.slug == "test-ks"
        assert ks.source_type == "s3"
        assert ks.status == "pending"


async def test_user_role_enum():
    assert UserRole.USER == "user"
    assert UserRole.ADMIN == "admin"
