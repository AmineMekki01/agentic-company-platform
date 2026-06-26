"""Tests for health endpoint."""

import pytest

pytestmark = pytest.mark.asyncio


async def test_health_returns_ok(client):
    res = await client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "service" in data
    assert "environment" in data
