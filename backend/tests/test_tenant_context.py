import uuid


def test_context_roundtrip():
    from app.core.tenant_context import (
        get_current_tenant,
        reset_current_tenant,
        set_current_tenant,
    )

    tid = uuid.uuid4()
    token = set_current_tenant(tid)
    assert get_current_tenant() == tid
    reset_current_tenant(token)


def test_token_carries_tenant_claim():
    from app.core.security import create_access_token, decode_access_token
    uid, tid = uuid.uuid4(), uuid.uuid4()
    token = create_access_token(uid, "user", tid)
    payload = decode_access_token(token)
    assert payload["tenant_id"] == str(tid)
    assert payload["sub"] == str(uid)


async def test_middleware_sets_tenant_from_bearer():
    from app.core.security import create_access_token
    from app.core.tenant_context import get_current_tenant
    from app.core.tenant_middleware import TenantMiddleware

    uid, tid = uuid.uuid4(), uuid.uuid4()
    seen = {}

    async def inner_app(scope, receive, send):
        seen["tid"] = get_current_tenant()

    token = create_access_token(uid, "user", tid)
    mw = TenantMiddleware(inner_app)
    scope = {"type": "http", "headers": [(b"authorization", f"Bearer {token}".encode())]}
    await mw(scope, None, None)
    assert seen["tid"] == tid
    assert get_current_tenant() != tid
