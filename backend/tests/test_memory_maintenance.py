"""Tests for the memory decay/forgetting Celery task's async body."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.asyncio


async def test_decay_persists_lower_importance_for_stale_memory(session_factory, create_test_user):
    from app.services.memory import create_memory
    from app.tasks.memory_maintenance import _decay

    user = await create_test_user("decayuser@example.com", "pass123")
    async with session_factory() as session:
        memory = await create_memory(session, user.id, "chat", "fact", "Uses vim", 0.8, [])
        memory.last_accessed_at = datetime.now(UTC) - timedelta(days=100)
        await session.commit()
        memory_id = memory.id

    with patch("app.db.celery_session.get_celery_session_factory", return_value=session_factory):
        await _decay()

    async with session_factory() as session:
        refreshed = await session.get(type(memory), memory_id)
        assert refreshed.importance_score < 0.8
        assert refreshed.decay_count == 1


async def test_decay_forgets_memory_below_floor(session_factory, create_test_user):
    from app.models.agent_memory import AgentMemory
    from app.services.memory import create_memory
    from app.tasks.memory_maintenance import _decay

    user = await create_test_user("forgetuser@example.com", "pass123")
    async with session_factory() as session:
        memory = await create_memory(session, user.id, "chat", "fact", "Trivial one-off detail", 0.06, [])
        memory.last_accessed_at = datetime.now(UTC) - timedelta(days=1000)
        await session.commit()
        memory_id = memory.id

    with patch("app.db.celery_session.get_celery_session_factory", return_value=session_factory):
        await _decay()

    async with session_factory() as session:
        refreshed = await session.get(AgentMemory, memory_id)
        assert refreshed is None


async def test_decay_leaves_recently_accessed_memories_alone(session_factory, create_test_user):
    from app.services.memory import create_memory
    from app.tasks.memory_maintenance import _decay

    user = await create_test_user("freshuser@example.com", "pass123")
    async with session_factory() as session:
        memory = await create_memory(session, user.id, "chat", "fact", "Just learned this", 0.7, [])
        await session.commit()
        memory_id = memory.id

    with patch("app.db.celery_session.get_celery_session_factory", return_value=session_factory):
        await _decay()

    async with session_factory() as session:
        refreshed = await session.get(type(memory), memory_id)
        assert refreshed is not None
        assert refreshed.importance_score == 0.7
        assert refreshed.decay_count == 0
