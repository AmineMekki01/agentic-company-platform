"""Tests for cross-worker agent registry invalidation in AgentRuntime.

The app runs multiple uvicorn worker processes, each with its own AgentRuntime
instance. refresh_graph() only rebuilds the calling process's local state, so a
shared redis version counter is used to let every other worker detect the
change and rebuild on its next request (refresh_if_stale).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agents.runtime import AgentRuntime

pytestmark = pytest.mark.asyncio


def _mock_redis(runtime: AgentRuntime, *, get_return: str | None = None, incr_return: int = 1) -> MagicMock:
    fake_redis = MagicMock()
    fake_redis.get = AsyncMock(return_value=get_return)
    fake_redis.incr = AsyncMock(return_value=incr_return)
    runtime._redis = fake_redis
    return fake_redis


async def test_refresh_graph_bumps_shared_version(monkeypatch):
    runtime = AgentRuntime()
    fake_redis = _mock_redis(runtime, incr_return=5)
    monkeypatch.setattr(runtime, "_rebuild", AsyncMock())

    await runtime.refresh_graph()

    runtime._rebuild.assert_awaited_once()
    fake_redis.incr.assert_awaited_once()
    assert runtime._registry_version == 5


async def test_refresh_if_stale_rebuilds_when_another_worker_bumped_version(monkeypatch):
    runtime = AgentRuntime()
    runtime._registry_version = 1
    _mock_redis(runtime, get_return="2")
    monkeypatch.setattr(runtime, "_rebuild", AsyncMock())

    await runtime.refresh_if_stale()

    runtime._rebuild.assert_awaited_once()
    assert runtime._registry_version == 2


async def test_refresh_if_stale_noop_when_version_matches(monkeypatch):
    runtime = AgentRuntime()
    runtime._registry_version = 3
    _mock_redis(runtime, get_return="3")
    monkeypatch.setattr(runtime, "_rebuild", AsyncMock())

    await runtime.refresh_if_stale()

    runtime._rebuild.assert_not_awaited()
    assert runtime._registry_version == 3


async def test_refresh_if_stale_swallows_redis_errors(monkeypatch):
    runtime = AgentRuntime()
    runtime._registry_version = 1
    fake_redis = MagicMock()
    fake_redis.get = AsyncMock(side_effect=Exception("redis unreachable"))
    runtime._redis = fake_redis
    monkeypatch.setattr(runtime, "_rebuild", AsyncMock())

    await runtime.refresh_if_stale()

    runtime._rebuild.assert_not_awaited()
    assert runtime._registry_version == 1
