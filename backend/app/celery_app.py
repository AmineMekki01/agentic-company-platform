"""Celery app for background tasks (Notion sync, etc.)."""

from celery import Celery
from celery.signals import worker_process_init
from app.core.config import settings

celery_app = Celery(
    "app",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.services.notion", "app.services.s3"],
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
)


@worker_process_init.connect
def init_worker_process(**kwargs):
    """Dispose SQLAlchemy engine so each worker gets its own connection pool."""
    from app.db.session import engine

    engine.dispose()
