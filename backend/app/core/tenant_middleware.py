"""Sets the request's tenant from the signed JWT claim, before any route
dependency (notably get_db) runs, so the DB session can scope RLS correctly."""
import uuid

from app.core.security import decode_access_token
from app.core.tenant_context import reset_current_tenant, set_current_tenant


class TenantMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        token = None
        for name, value in scope.get("headers", []):
            if name == b"authorization" and value.startswith(b"Bearer "):
                try:
                    payload = decode_access_token(value[7:].decode())
                    tid = payload.get("tenant_id")
                    if tid:
                        token = set_current_tenant(uuid.UUID(tid))
                except Exception:
                    pass
                break

        try:
            await self.app(scope, receive, send)
        finally:
            if token is not None:
                reset_current_tenant(token)
