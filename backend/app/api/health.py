import asyncio
import logging

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine as db_engine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


async def _check_db() -> dict:
    try:
        async with db_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        logger.warning("DB health check failed: %s", exc)
        return {"status": "error", "detail": str(exc)}


async def _check_qdrant() -> dict:
    try:
        from app.services.rag import get_rag_service

        rag = get_rag_service()
        collections = await rag.qdrant.get_collections()
        return {"status": "ok", "collections": len(collections.collections)}
    except Exception as exc:
        logger.warning("Qdrant health check failed: %s", exc)
        return {"status": "error", "detail": str(exc)}


async def _check_redis() -> dict:
    try:
        import redis.asyncio as aioredis

        redis = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        pong = await redis.ping()
        await redis.aclose()
        if pong:
            return {"status": "ok"}
        return {"status": "error", "detail": "Redis returned False for ping"}
    except Exception as exc:
        logger.warning("Redis health check failed: %s", exc)
        return {"status": "error", "detail": str(exc)}


@router.get("/health")
async def health() -> dict:
    """Health check endpoint with dependency status."""
    db_result, qdrant_result, redis_result = await asyncio.gather(
        _check_db(), _check_qdrant(), _check_redis()
    )

    deps = {
        "database": db_result,
        "qdrant": qdrant_result,
        "redis": redis_result,
    }
    all_ok = all(d["status"] == "ok" for d in deps.values())

    return {
        "status": "ok" if all_ok else "degraded",
        "service": settings.app_name,
        "environment": settings.environment,
        "dependencies": deps,
    }
