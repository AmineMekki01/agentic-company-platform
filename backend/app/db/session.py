from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.tenant_context import get_current_tenant

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


@event.listens_for(Session, "before_flush")
def _stamp_tenant_id(session: Session, flush_context, instances) -> None:
    """Auto-stamp tenant_id on new tenant-owned rows from the request context,
    so create-paths stay tenant-unaware and RLS WITH CHECK always passes."""
    tenant_id = get_current_tenant()
    if tenant_id is None:
        return
    for obj in session.new:
        if hasattr(obj, "tenant_id") and getattr(obj, "tenant_id", None) is None:
            obj.tenant_id = tenant_id


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield an async database session for dependency injection.

    When a tenant is in context (set from the JWT by TenantMiddleware), drop to
    the non-owner ``app_rls`` role and set ``app.tenant_id`` for the transaction
    so Row-Level Security scopes every query. Both are transaction-scoped and
    reset automatically. Unauthenticated requests (no tenant) run unscoped.
    """
    from sqlalchemy import text
    from app.core.tenant_context import get_current_tenant

    async with async_session_factory() as session:
        tenant_id = get_current_tenant()
        if tenant_id is not None and session.bind.dialect.name == "postgresql":
            await session.execute(text("SET LOCAL ROLE app_rls"))
            await session.execute(
                text("SELECT set_config('app.tenant_id', :tid, true)"),
                {"tid": str(tenant_id)},
            )
        yield session
