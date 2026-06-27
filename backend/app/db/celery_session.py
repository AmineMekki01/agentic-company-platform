"""Shared async DB engine and event loop for Celery tasks."""

import asyncio
import logging

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings

logger = logging.getLogger(__name__)

_engine = None
_session_factory = None
_loop: asyncio.AbstractEventLoop | None = None


def _ensure_loop() -> asyncio.AbstractEventLoop:
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
    return _loop


def _ensure_session_factory() -> async_sessionmaker:
    global _engine, _session_factory
    if _session_factory is None:
        _engine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
        )
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _session_factory


def run_async(coro):
    """Run *coro* on the persistent Celery event loop.

    Replaces ``asyncio.run(coro)`` in Celery tasks so that the same
    event loop and DB connection pool are reused across invocations.
    """
    loop = _ensure_loop()
    _ensure_session_factory()
    return loop.run_until_complete(coro)


def get_celery_session_factory() -> async_sessionmaker:
    """Return the shared session factory for use inside async task code."""
    return _ensure_session_factory()


async def dispose_celery_engine() -> None:
    """Dispose the cached engine. Call on Celery worker shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
