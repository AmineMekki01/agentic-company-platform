"""Tenant-scoped wrapper over an AsyncQdrantClient."""
from typing import Any

from qdrant_client import models

from app.core.tenant_context import get_current_tenant

TENANT_KEY = "tenant_id"


class TenantScopedQdrant:
    def __init__(self, client: Any) -> None:
        self._c = client

    def _tenant(self) -> str:
        tid = get_current_tenant()
        if tid is None:
            raise RuntimeError(
                "Tenant-scoped Qdrant operation with no tenant in context. "
                "A request must set the tenant (JWT) or a Celery task must pass tenant_id."
            )
        return str(tid)

    def _merge(self, flt: models.Filter | None) -> models.Filter:
        cond = models.FieldCondition(key=TENANT_KEY, match=models.MatchValue(value=self._tenant()))
        if flt is None:
            return models.Filter(must=[cond])
        must = list(flt.must or [])
        must.append(cond)
        return models.Filter(must=must, should=flt.should, must_not=flt.must_not)

    async def query_points(self, *, collection_name: str, query_filter=None, **kw):
        return await self._c.query_points(
            collection_name=collection_name, query_filter=self._merge(query_filter), **kw
        )

    async def search(self, *, collection_name: str, query_filter=None, **kw):
        return await self._c.search(
            collection_name=collection_name, query_filter=self._merge(query_filter), **kw
        )

    async def scroll(self, *, collection_name: str, scroll_filter=None, **kw):
        return await self._c.scroll(
            collection_name=collection_name, scroll_filter=self._merge(scroll_filter), **kw
        )

    async def delete(self, *, collection_name: str, points_selector, **kw):
        sel = points_selector
        if isinstance(points_selector, models.Filter):
            sel = self._merge(points_selector)
        return await self._c.delete(collection_name=collection_name, points_selector=sel, **kw)

    async def upsert(self, *, collection_name: str, points, **kw):
        tid = self._tenant()
        for p in points:
            payload = getattr(p, "payload", None) or {}
            payload[TENANT_KEY] = tid
            p.payload = payload
        return await self._c.upsert(collection_name=collection_name, points=points, **kw)

    def __getattr__(self, name: str) -> Any:
        # create_collection, get_collection(s), collection_exists, create_payload_index, close, ...
        return getattr(self._c, name)
