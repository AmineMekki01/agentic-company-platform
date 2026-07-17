"""Postgres-backed fixtures for tests that need real RLS (SQLite can't do it)."""
import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.rls import apply_statements as _rls_statements
import app.models

PG_URL = os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://app:app@postgres:5432/app_test")


async def _ensure_test_db() -> None:
    """Create the test database if it doesn't exist (it lives outside migrations)."""
    from sqlalchemy import text

    admin_url = PG_URL.rsplit("/", 1)[0] + "/postgres"
    dbname = PG_URL.rsplit("/", 1)[1]
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            exists = await conn.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": dbname}
            )
            if not exists:
                await conn.execute(text(f'CREATE DATABASE "{dbname}"'))
    finally:
        await engine.dispose()


async def _reset_schema(conn):
    await conn.execute(text("DROP SCHEMA public CASCADE"))
    await conn.execute(text("CREATE SCHEMA public"))


@pytest.fixture
async def pg_engine():
    await _ensure_test_db()
    engine = create_async_engine(PG_URL)
    async with engine.begin() as conn:
        await _reset_schema(conn)
        await conn.run_sync(Base.metadata.create_all)
        for stmt in _rls_statements():
            await conn.execute(text(stmt))
    yield engine
    async with engine.begin() as conn:
        await _reset_schema(conn)
    await engine.dispose()


@pytest.fixture
def pg_session_factory(pg_engine):
    return async_sessionmaker(pg_engine, expire_on_commit=False)
