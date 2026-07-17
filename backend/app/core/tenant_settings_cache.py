"""Small TTL cache for the per-tenant settings read on the hot path."""
import time
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tracing import DEFAULT_TRACING_MODE
from app.models.llm_settings import LLMSettings

_TTL_SECONDS = 60.0


@dataclass(frozen=True)
class TenantRuntime:
    """The tenant settings needed while serving a request."""

    tracing_mode: str = DEFAULT_TRACING_MODE
    ollama_enabled: bool = False
    ollama_base_url: str | None = None


DEFAULT_RUNTIME = TenantRuntime()

_cache: dict[uuid.UUID, tuple[TenantRuntime, float]] = {}


def invalidate(tenant_id: uuid.UUID) -> None:
    """Drop a tenant's cached settings (call after an admin edit)."""
    _cache.pop(tenant_id, None)


def clear() -> None:
    """Drop the whole cache (tests)."""
    _cache.clear()


async def get_tenant_runtime(db: AsyncSession, tenant_id: uuid.UUID) -> TenantRuntime:
    """Return the tenant's runtime settings, cached for _TTL_SECONDS."""
    now = time.monotonic()
    hit = _cache.get(tenant_id)
    if hit is not None and hit[1] > now:
        return hit[0]

    try:
        row = (
            await db.execute(
                select(
                    LLMSettings.tracing_mode,
                    LLMSettings.ollama_enabled,
                    LLMSettings.ollama_base_url,
                ).where(LLMSettings.tenant_id == tenant_id)
            )
        ).first()
    except Exception:
        return DEFAULT_RUNTIME

    if row is None:
        return DEFAULT_RUNTIME

    runtime = TenantRuntime(
        tracing_mode=row[0] or DEFAULT_TRACING_MODE,
        ollama_enabled=bool(row[1]),
        ollama_base_url=row[2] or None,
    )
    _cache[tenant_id] = (runtime, now + _TTL_SECONDS)
    return runtime
