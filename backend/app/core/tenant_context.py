"""Request-scoped current-tenant, resolved once at the edge (JWT) and read at
the isolation chokepoints (DB session scoping, Qdrant wrapper, auto-stamp on
insert). Downstream service code never passes a tenant_id explicitly."""
import uuid
from contextvars import ContextVar, Token

_current_tenant: ContextVar[uuid.UUID | None] = ContextVar("current_tenant", default=None)


def set_current_tenant(tenant_id: uuid.UUID) -> Token:
    return _current_tenant.set(tenant_id)

def get_current_tenant() -> uuid.UUID | None:
    return _current_tenant.get()


def reset_current_tenant(token: Token) -> None:
    _current_tenant.reset(token)
