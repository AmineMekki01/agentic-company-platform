"""Tests for health endpoint."""

from unittest.mock import AsyncMock, patch

import pytest

pytestmark = pytest.mark.asyncio


async def test_health_returns_ok(client):
    with patch("app.api.health._check_db", new=AsyncMock(return_value={"status": "ok"})), \
         patch("app.api.health._check_qdrant", new=AsyncMock(return_value={"status": "ok", "collections": 1})), \
         patch("app.api.health._check_redis", new=AsyncMock(return_value={"status": "ok"})):
        res = await client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert "service" in data
        assert "environment" in data
        assert data["dependencies"]["database"]["status"] == "ok"
        assert data["dependencies"]["qdrant"]["status"] == "ok"
        assert data["dependencies"]["redis"]["status"] == "ok"


async def test_health_returns_degraded_when_db_down(client):
    with patch("app.api.health._check_db", new=AsyncMock(return_value={"status": "error", "detail": "connection refused"})), \
         patch("app.api.health._check_qdrant", new=AsyncMock(return_value={"status": "ok", "collections": 1})), \
         patch("app.api.health._check_redis", new=AsyncMock(return_value={"status": "ok"})):
        res = await client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "degraded"
        assert data["dependencies"]["database"]["status"] == "error"
