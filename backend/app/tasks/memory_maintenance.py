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
from app.tasks.base import TenantTask

logger = logging.getLogger(__name__)

STALE_AFTER_DAYS = 14
FORGET_FLOOR = 0.05


@celery_app.task(bind=True, max_retries=3)
def decay_stale_memories(self):
    """Dispatcher: fan out one decay task per active tenant."""
    async def _dispatch():
        from app.db.celery_session import iter_active_tenant_ids
        for tid in await iter_active_tenant_ids():
            decay_stale_memories_for_tenant.delay(tenant_id=str(tid))

    run_async(_dispatch())


@celery_app.task(bind=True, base=TenantTask, max_retries=3)
def decay_stale_memories_for_tenant(self, tenant_id: str):
    run_async(_decay())


async def _decay():
    from app.db.celery_session import tenant_scoped_session
    from app.models import AgentMemory
    from app.services.memory import _effective_importance, delete_memory
    from sqlalchemy import select

    cutoff = datetime.now(UTC) - timedelta(days=STALE_AFTER_DAYS)

    async with tenant_scoped_session() as db:
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
