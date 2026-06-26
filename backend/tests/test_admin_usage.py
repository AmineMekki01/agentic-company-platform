"""Tests for admin usage & budget API."""

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.models import TokenBudget, TokenUsage
from app.models.user import User

pytestmark = pytest.mark.asyncio


async def test_usage_summary_admin_only(client, auth_headers):
    res = await client.get("/api/admin/usage/summary", headers=auth_headers)
    assert res.status_code == 403


async def test_usage_summary_empty(client, admin_headers):
    res = await client.get("/api/admin/usage/summary", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_tokens"] == 0
    assert data["total_cost_usd"] == 0.0
    assert data["total_requests"] == 0


async def test_usage_summary_with_data(client, admin_headers, session_factory):
    async with session_factory() as session:
        admin = await session.scalar(select(User).where(User.email == "admin@example.com"))
        for i in range(3):
            session.add(TokenUsage(
                user_id=admin.id,
                agent_slug="hr",
                model="gpt-5.4-nano",
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                estimated_cost_usd=0.001,
            ))
        await session.commit()
    res = await client.get("/api/admin/usage/summary", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total_tokens"] == 450
    assert data["total_requests"] == 3
    assert data["input_tokens"] == 300
    assert data["output_tokens"] == 150


async def test_usage_summary_date_filter(client, admin_headers, session_factory):
    async with session_factory() as session:
        admin = await session.scalar(select(User).where(User.email == "admin@example.com"))
        session.add(TokenUsage(
            user_id=admin.id,
            agent_slug="hr",
            model="gpt-5.4-nano",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            estimated_cost_usd=0.001,
        ))
        await session.commit()
    res = await client.get(
        "/api/admin/usage/summary?start_date=2000-01-01T00:00:00&end_date=2000-12-31T00:00:00",
        headers=admin_headers,
    )
    assert res.status_code == 200
    assert res.json()["total_requests"] == 0


async def test_usage_timeseries(client, admin_headers):
    res = await client.get("/api/admin/usage/timeseries?days=7", headers=admin_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


async def test_usage_timeseries_agent_filter(client, admin_headers):
    res = await client.get("/api/admin/usage/timeseries?days=7&agent_slug=hr", headers=admin_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


async def test_recent_usage(client, admin_headers, session_factory):
    async with session_factory() as session:
        admin = await session.scalar(select(User).where(User.email == "admin@example.com"))
        session.add(TokenUsage(
            user_id=admin.id,
            agent_slug="hr",
            model="gpt-5.4-nano",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            estimated_cost_usd=0.001,
        ))
        await session.commit()
    res = await client.get("/api/admin/usage/recent", headers=admin_headers)
    assert res.status_code == 200
    assert len(res.json()) == 1


async def test_recent_usage_pagination(client, admin_headers, session_factory):
    async with session_factory() as session:
        admin = await session.scalar(select(User).where(User.email == "admin@example.com"))
        for i in range(5):
            session.add(TokenUsage(
                user_id=admin.id,
                agent_slug="hr",
                model="gpt-5.4-nano",
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                estimated_cost_usd=0.001,
            ))
        await session.commit()
    res = await client.get("/api/admin/usage/recent?limit=2&offset=0", headers=admin_headers)
    assert res.status_code == 200
    assert len(res.json()) == 2


async def test_list_budgets(client, admin_headers):
    res = await client.get("/api/admin/usage/budgets", headers=admin_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


async def test_upsert_budget_create(client, admin_headers):
    res = await client.put(
        "/api/admin/usage/budgets",
        headers=admin_headers,
        json={"scope": "user", "scope_id": "test-user-id", "monthly_cost_limit_usd": 10.0},
    )
    assert res.status_code == 200
    assert res.json()["scope"] == "user"
    assert res.json()["monthly_cost_limit_usd"] == 10.0


async def test_upsert_budget_update(client, admin_headers):
    await client.put(
        "/api/admin/usage/budgets",
        headers=admin_headers,
        json={"scope": "user", "scope_id": "update-id", "monthly_cost_limit_usd": 5.0},
    )
    res = await client.put(
        "/api/admin/usage/budgets",
        headers=admin_headers,
        json={"scope": "user", "scope_id": "update-id", "monthly_cost_limit_usd": 15.0},
    )
    assert res.status_code == 200
    assert res.json()["monthly_cost_limit_usd"] == 15.0


async def test_upsert_budget_invalid_scope(client, admin_headers):
    res = await client.put(
        "/api/admin/usage/budgets",
        headers=admin_headers,
        json={"scope": "invalid", "scope_id": "x", "monthly_cost_limit_usd": 10.0},
    )
    assert res.status_code == 400


async def test_upsert_budget_negative_limit(client, admin_headers):
    res = await client.put(
        "/api/admin/usage/budgets",
        headers=admin_headers,
        json={"scope": "user", "scope_id": "x", "monthly_cost_limit_usd": -5.0},
    )
    assert res.status_code == 400


async def test_delete_budget(client, admin_headers):
    created = await client.put(
        "/api/admin/usage/budgets",
        headers=admin_headers,
        json={"scope": "user", "scope_id": "delete-id", "monthly_cost_limit_usd": 10.0},
    )
    budget_id = created.json()["id"]
    res = await client.delete(f"/api/admin/usage/budgets/{budget_id}", headers=admin_headers)
    assert res.status_code == 204


async def test_delete_nonexistent_budget(client, admin_headers):
    res = await client.delete(f"/api/admin/usage/budgets/{uuid.uuid4()}", headers=admin_headers)
    assert res.status_code == 404


async def test_delete_invalid_budget_id(client, admin_headers):
    res = await client.delete("/api/admin/usage/budgets/not-a-uuid", headers=admin_headers)
    assert res.status_code == 400
