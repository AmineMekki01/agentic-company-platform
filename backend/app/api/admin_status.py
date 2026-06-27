"""Admin system status API — real-time health of services and connectors."""

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import AdminUser, DbSession
from app.api.health import _check_db, _check_qdrant, _check_redis
from app.core.config import settings
from app.models import Connector, KnowledgeSource

router = APIRouter(prefix="/admin/status", tags=["admin"])


@router.get("")
async def get_system_status(user: AdminUser, db: DbSession) -> dict:
    """Return real-time status of infrastructure services and data connectors."""
    import asyncio

    db_result, qdrant_result, redis_result = await asyncio.gather(
        _check_db(), _check_qdrant(), _check_redis()
    )

    services = {
        "database": db_result,
        "qdrant": qdrant_result,
        "redis": redis_result,
    }

    ks_result = await db.scalars(
        select(KnowledgeSource)
        .options(selectinload(KnowledgeSource.connector))
        .order_by(KnowledgeSource.created_at.desc())
    )
    knowledge_sources = [
        {
            "id": str(ks.id),
            "slug": ks.slug,
            "name": ks.name,
            "source_type": ks.source_type,
            "status": ks.status,
            "chunk_count": ks.chunk_count,
            "last_sync_at": ks.last_sync_at.isoformat() if ks.last_sync_at else None,
            "connector_name": ks.connector.name if ks.connector else None,
        }
        for ks in ks_result.all()
    ]

    conn_result = await db.scalars(
        select(Connector).order_by(Connector.created_at.desc())
    )
    connectors = [
        {
            "id": str(c.id),
            "slug": c.slug,
            "name": c.name,
            "connector_type": c.connector_type,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in conn_result.all()
    ]

    all_ok = all(d["status"] == "ok" for d in services.values())

    return {
        "status": "ok" if all_ok else "degraded",
        "service": settings.app_name,
        "environment": settings.environment,
        "services": services,
        "knowledge_sources": knowledge_sources,
        "connectors": connectors,
    }
