"""Celery app for background tasks (Notion sync, etc.)."""

from celery import Celery
from celery.signals import worker_process_init, worker_process_shutdown
from app.core.config import settings

celery_app = Celery(
    "app",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.services.notion", "app.services.s3", "app.services.gdrive", "app.tasks.retention", "app.tasks.eval_tasks", "app.tasks.memory_maintenance"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "process-eval-schedules": {
            "task": "app.tasks.eval_tasks.process_eval_schedules",
            "schedule": 300.0,
        },
        "decay-stale-memories": {
            "task": "app.tasks.memory_maintenance.decay_stale_memories",
            "schedule": 604800.0,  # weekly
        },
    },
)


@worker_process_init.connect
def init_worker_process(**kwargs):
    """Dispose SQLAlchemy engine so each worker gets its own connection pool."""
    from app.db.session import engine

    engine.dispose()


@worker_process_shutdown.connect
def shutdown_worker_process(**kwargs):
    """Dispose the Celery-shared async engine and eval runtime on worker shutdown."""
    import asyncio

    from app.db.celery_session import dispose_celery_engine

    async def _shutdown():
        await dispose_celery_engine()
        from app.tasks.eval_tasks import _worker_runtime
        if _worker_runtime is not None:
            await _worker_runtime.shutdown()

    try:
        asyncio.run(_shutdown())
    except Exception:
        pass
