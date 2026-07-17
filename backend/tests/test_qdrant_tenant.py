import uuid
from unittest.mock import AsyncMock

import pytest


async def test_query_injects_current_tenant_filter():
    from app.core.tenant_context import set_current_tenant, reset_current_tenant
    from app.services.qdrant_tenant import TenantScopedQdrant
    from qdrant_client import models

    raw = AsyncMock()
    scoped = TenantScopedQdrant(raw)
    tid = uuid.uuid4()
    tok = set_current_tenant(tid)
    try:
        await scoped.query_points(collection_name="company_knowledge", query=[0.1])
    finally:
        reset_current_tenant(tok)

    flt = raw.query_points.call_args.kwargs["query_filter"]
    conds = [c for c in flt.must if isinstance(c, models.FieldCondition) and c.key == "tenant_id"]
    assert conds and conds[0].match.value == str(tid)


async def test_upsert_stamps_tenant_on_points():
    from app.core.tenant_context import set_current_tenant, reset_current_tenant
    from app.services.qdrant_tenant import TenantScopedQdrant
    from qdrant_client import models

    raw = AsyncMock()
    scoped = TenantScopedQdrant(raw)
    tid = uuid.uuid4()
    point = models.PointStruct(id=str(uuid.uuid4()), vector=[0.1, 0.2], payload={"doc": "x"})
    tok = set_current_tenant(tid)
    try:
        await scoped.upsert(collection_name="company_knowledge", points=[point])
    finally:
        reset_current_tenant(tok)

    sent = raw.upsert.call_args.kwargs["points"][0]
    assert sent.payload["tenant_id"] == str(tid)


async def test_operation_without_tenant_fails_closed():
    from app.core.tenant_context import get_current_tenant, set_current_tenant, reset_current_tenant
    from app.services.qdrant_tenant import TenantScopedQdrant

    raw = AsyncMock()
    scoped = TenantScopedQdrant(raw)

    import app.core.tenant_context as tc
    token = tc._current_tenant.set(None)
    try:
        assert get_current_tenant() is None
        with pytest.raises(RuntimeError):
            await scoped.search(collection_name="company_knowledge", query_vector=[0.1])
    finally:
        tc._current_tenant.reset(token)


def test_services_use_the_wrapper():
    import pathlib
    import re
    root = pathlib.Path(__file__).resolve().parents[1] / "app" / "services"
    offenders = []
    for f in ["rag.py", "memory.py"]:
        txt = (root / f).read_text()
        if re.search(r"AsyncQdrantClient\(", txt) and "TenantScopedQdrant" not in txt:
            offenders.append(f)
    assert not offenders, f"{offenders} construct a raw client without the tenant wrapper"
