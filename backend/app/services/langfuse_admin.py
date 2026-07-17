"""Administrative purging of Langfuse traces.

Traces hold the customer's prompts, completions and retrieved document chunks,
in a database that RLS and the per-tenant encryption keys do not reach. Two
things therefore have to be possible from code:

  * retention  - traces must not accumulate customer content forever
  * erasure    - deleting a tenant must delete that tenant's traces too,
                 otherwise "we deleted your data" is not true

Both rely on the `tenant:<id>` tag that app.core.tracing puts on every trace.
All functions are best-effort and never raise: a failed purge must not take
down a Celery worker, but it is logged loudly because it is a compliance gap.
"""
import logging
import uuid
from datetime import UTC, datetime, timedelta

from app.core.config import settings

logger = logging.getLogger(__name__)

_PAGE_LIMIT = 100
_MAX_PAGES = 500


def tenant_tag(tenant_id: uuid.UUID | str) -> str:
    """The Langfuse tag every trace of this tenant carries."""
    return f"tenant:{tenant_id}"


def _client():
    """Return a Langfuse client, or None if tracing isn't configured."""
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return None
    try:
        from langfuse import Langfuse

        return Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host or None,
        )
    except Exception:
        logger.warning("Langfuse admin client init failed", exc_info=True)
        return None


def _collect_trace_ids(client, **list_kwargs) -> list[str]:
    """Page through trace.list collecting ids for the given filter."""
    ids: list[str] = []
    for page in range(1, _MAX_PAGES + 1):
        resp = client.api.trace.list(page=page, limit=_PAGE_LIMIT, **list_kwargs)
        batch = getattr(resp, "data", None) or []
        ids.extend(t.id for t in batch)
        if len(batch) < _PAGE_LIMIT:
            break
    else:
        logger.warning("Trace listing hit the %d page cap; purge may be partial", _MAX_PAGES)
    return ids


def _delete(client, trace_ids: list[str]) -> int:
    """Delete traces in batches. Returns how many were requested for deletion."""
    for i in range(0, len(trace_ids), _PAGE_LIMIT):
        client.api.trace.delete_multiple(trace_ids=trace_ids[i : i + _PAGE_LIMIT])
    return len(trace_ids)


def purge_traces_older_than(days: int | None = None) -> int:
    """Delete traces older than `days` (default: settings.langfuse_trace_retention_days).

    Returns the number of traces deleted (0 if tracing is unconfigured/disabled).
    """
    days = settings.langfuse_trace_retention_days if days is None else days
    if not days or days <= 0:
        logger.info("Langfuse trace retention disabled (days=%s); skipping purge", days)
        return 0

    client = _client()
    if client is None:
        return 0

    cutoff = datetime.now(UTC) - timedelta(days=days)
    try:
        ids = _collect_trace_ids(client, to_timestamp=cutoff)
        if not ids:
            return 0
        deleted = _delete(client, ids)
        logger.info("Purged %d Langfuse traces older than %d days", deleted, days)
        return deleted
    except Exception:
        logger.exception("Langfuse retention purge failed (customer content may be over-retained)")
        return 0


def purge_tenant_traces(tenant_id: uuid.UUID | str) -> int:
    """Delete every trace belonging to one tenant. Part of tenant erasure.

    Returns the number of traces deleted.
    """
    client = _client()
    if client is None:
        return 0

    try:
        ids = _collect_trace_ids(client, tags=[tenant_tag(tenant_id)])
        if not ids:
            logger.info("No Langfuse traces found for tenant %s", tenant_id)
            return 0
        deleted = _delete(client, ids)
        logger.info("Purged %d Langfuse traces for tenant %s", deleted, tenant_id)
        return deleted
    except Exception:
        logger.exception(
            "Langfuse purge FAILED for tenant %s - their traces still hold customer "
            "content; erasure is incomplete until this succeeds",
            tenant_id,
        )
        raise
