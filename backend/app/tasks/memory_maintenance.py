"""Celery task: decay stale agent memories and forget the ones that have
faded past relevance.

Reads/writes are needed because _effective_importance (app.services.memory)
only computes a decayed score at read time without persisting it - this task
is what actually applies that decay to the stored importance_score over time,
and removes memories once they've decayed below the point of being useful.
"""

import logging
from datetime import UTC, datetime, timedelta

from app.celery_app import celery_app
from app.db.celery_session import run_async

logger = logging.getLogger(__name__)

STALE_AFTER_DAYS = 14
FORGET_FLOOR = 0.05


@celery_app.task(bind=True, max_retries=3)
def decay_stale_memories(self):
    run_async(_decay())


async def _decay():
    from sqlalchemy import select

    from app.db.celery_session import get_celery_session_factory
    from app.models import AgentMemory
    from app.services.memory import _effective_importance, delete_memory

    session_factory = get_celery_session_factory()
    cutoff = datetime.now(UTC) - timedelta(days=STALE_AFTER_DAYS)

    async with session_factory() as db:
        result = await db.execute(
            select(AgentMemory).where(AgentMemory.last_accessed_at <= cutoff)
        )
        stale = result.scalars().all()

        now = datetime.now(UTC)
        decayed_count = 0
        forgotten_count = 0
        for memory in stale:
            effective = _effective_importance(memory, now)
            if effective < FORGET_FLOOR:
                await delete_memory(db, str(memory.id))
                forgotten_count += 1
            else:
                memory.importance_score = effective
                memory.decay_count += 1
                decayed_count += 1

        await db.commit()
        logger.info(
            "Memory decay: %d decayed, %d forgotten (stale_after_days=%d)",
            decayed_count, forgotten_count, STALE_AFTER_DAYS,
        )
