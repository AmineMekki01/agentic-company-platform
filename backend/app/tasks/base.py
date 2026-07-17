"""Celery base task that establishes tenant context from a `tenant_id` kwarg."""
import logging
import uuid

from celery import Task

from app.agents.llm import reset_ollama_base_url, set_ollama_base_url
from app.core.tenant_context import reset_current_tenant, set_current_tenant
from app.core.tracing import reset_tracing_mode, set_tracing_mode

logger = logging.getLogger(__name__)


def _load_tenant_runtime(tenant_id: uuid.UUID):
    """Read the tenant's runtime settings on the Celery loop. None if unavailable."""
    from app.core.tenant_settings_cache import get_tenant_runtime
    from app.db.celery_session import get_celery_session_factory, run_async

    async def _load():
        factory = get_celery_session_factory()
        async with factory() as db:
            return await get_tenant_runtime(db, tenant_id)

    try:
        return run_async(_load())
    except Exception:
        logger.warning(
            "Could not load runtime settings for tenant %s; falling back to defaults. "
            "A tenant on tracing_mode 'masked'/'off' may be traced in full by this task.",
            tenant_id,
            exc_info=True,
        )
        return None


class TenantTask(Task):
    abstract = True

    def __call__(self, *args, **kwargs):
        tid = kwargs.get("tenant_id")
        tokens = []

        if tid is not None:
            tenant_uuid = uuid.UUID(str(tid))
            tokens.append((reset_current_tenant, set_current_tenant(tenant_uuid)))

            runtime = _load_tenant_runtime(tenant_uuid)
            if runtime is not None:
                tokens.append((reset_tracing_mode, set_tracing_mode(runtime.tracing_mode)))
                tokens.append((reset_ollama_base_url, set_ollama_base_url(runtime.ollama_base_url)))

        try:
            return super().__call__(*args, **kwargs)
        finally:
            for reset, token in reversed(tokens):
                try:
                    reset(token)
                except Exception:
                    logger.debug("Context reset failed", exc_info=True)
