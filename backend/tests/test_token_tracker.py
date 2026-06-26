"""Tests for token_tracker service."""

import uuid

import pytest
from sqlalchemy import select

from app.models import TokenBudget, TokenUsage
from app.services.token_tracker import check_budget, record_usage

pytestmark = pytest.mark.asyncio


async def test_record_usage_perspects(session_factory, monkeypatch):
    async with session_factory() as session:
        from app.models.user import User
        from app.core.security import hash_password
        user = User(email="track@example.com", password_hash=hash_password("x"))
        session.add(user)
        await session.commit()
        await session.refresh(user)

    monkeypatch.setattr("app.services.token_tracker.async_session_factory", session_factory)
    await record_usage(user.id, "hr", "gpt-5.4-nano", 100, 50)

    async with session_factory() as session:
        rows = await session.scalars(select(TokenUsage))
        records = rows.all()
        assert len(records) == 1
        assert records[0].input_tokens == 100
        assert records[0].output_tokens == 50
        assert records[0].total_tokens == 150


async def test_record_usage_skips_none_user(session_factory, monkeypatch):
    monkeypatch.setattr("app.services.token_tracker.async_session_factory", session_factory)
    await record_usage(None, "hr", "gpt-5.4-nano", 100, 50)
    async with session_factory() as session:
        rows = await session.scalars(select(TokenUsage))
        assert len(rows.all()) == 0


async def test_record_usage_skips_zero_tokens(session_factory, monkeypatch):
    monkeypatch.setattr("app.services.token_tracker.async_session_factory", session_factory)
    await record_usage(uuid.uuid4(), "hr", "gpt-5.4-nano", 0, 0)
    async with session_factory() as session:
        rows = await session.scalars(select(TokenUsage))
        assert len(rows.all()) == 0


async def test_record_usage_calculates_cost(session_factory, monkeypatch):
    async with session_factory() as session:
        from app.models.user import User
        from app.core.security import hash_password
        user = User(email="cost@example.com", password_hash=hash_password("x"))
        session.add(user)
        await session.commit()
        await session.refresh(user)

    monkeypatch.setattr("app.services.token_tracker.async_session_factory", session_factory)
    await record_usage(user.id, "hr", "gpt-5.4-nano", 1000, 500)

    async with session_factory() as session:
        row = await session.scalar(select(TokenUsage))
        assert row is not None
        assert row.estimated_cost_usd > 0


async def test_check_budget_no_budget(session_factory, monkeypatch):
    monkeypatch.setattr("app.services.token_tracker.async_session_factory", session_factory)
    exceeded, used, limit = await check_budget(uuid.uuid4(), "hr")
    assert exceeded is False
    assert used == 0
    assert limit == 0


async def test_check_budget_user_under(session_factory, monkeypatch):
    async with session_factory() as session:
        from app.models.user import User
        from app.core.security import hash_password
        user = User(email="under@example.com", password_hash=hash_password("x"))
        session.add(user)
        await session.commit()
        await session.refresh(user)
        session.add(TokenBudget(scope="user", scope_id=str(user.id), monthly_cost_limit_usd=100.0))
        await session.commit()

    monkeypatch.setattr("app.services.token_tracker.async_session_factory", session_factory)
    exceeded, used, limit = await check_budget(user.id, "hr")
    assert exceeded is False
    assert limit == 100.0


async def test_check_budget_user_exceeded(session_factory, monkeypatch):
    async with session_factory() as session:
        from app.models.user import User
        from app.core.security import hash_password
        user = User(email="over@example.com", password_hash=hash_password("x"))
        session.add(user)
        await session.commit()
        await session.refresh(user)
        session.add(TokenBudget(scope="user", scope_id=str(user.id), monthly_cost_limit_usd=0.01))
        session.add(TokenUsage(
            user_id=user.id, agent_slug="hr", model="gpt-5.4-nano",
            input_tokens=10000, output_tokens=5000, total_tokens=15000,
            estimated_cost_usd=1.0,
        ))
        await session.commit()

    monkeypatch.setattr("app.services.token_tracker.async_session_factory", session_factory)
    exceeded, used, limit = await check_budget(user.id, "hr")
    assert exceeded is True
    assert used >= 1.0
    assert limit == 0.01


async def test_check_budget_agent_exceeded(session_factory, monkeypatch):
    async with session_factory() as session:
        from app.models.user import User
        from app.core.security import hash_password
        user = User(email="agent@example.com", password_hash=hash_password("x"))
        session.add(user)
        await session.commit()
        await session.refresh(user)
        session.add(TokenBudget(scope="agent", scope_id="hr", monthly_cost_limit_usd=0.01))
        session.add(TokenUsage(
            user_id=user.id, agent_slug="hr", model="gpt-5.4-nano",
            input_tokens=10000, output_tokens=5000, total_tokens=15000,
            estimated_cost_usd=1.0,
        ))
        await session.commit()

    monkeypatch.setattr("app.services.token_tracker.async_session_factory", session_factory)
    exceeded, used, limit = await check_budget(user.id, "hr")
    assert exceeded is True
    assert limit == 0.01


async def test_check_budget_global_user_budget(session_factory, monkeypatch):
    async with session_factory() as session:
        from app.models.user import User
        from app.core.security import hash_password
        user = User(email="global@example.com", password_hash=hash_password("x"))
        session.add(user)
        await session.commit()
        await session.refresh(user)
        session.add(TokenBudget(scope="user", scope_id="*", monthly_cost_limit_usd=50.0))
        await session.commit()

    monkeypatch.setattr("app.services.token_tracker.async_session_factory", session_factory)
    exceeded, used, limit = await check_budget(user.id, "hr")
    assert exceeded is False
    assert limit == 50.0
