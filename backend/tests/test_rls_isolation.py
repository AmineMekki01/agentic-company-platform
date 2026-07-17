"""Postgres-only tests for tenant isolation: composite uniqueness and RLS."""
import uuid

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.pg


async def test_same_slug_across_tenants(pg_session_factory):
    """Two tenants can each own an agent with the same slug."""
    from app.models.tenant import Tenant
    from app.models.agent_settings import AgentSettings
    async with pg_session_factory() as s:
        a, b = Tenant(slug="a", name="A"), Tenant(slug="b", name="B")
        s.add_all([a, b])
        await s.flush()
        s.add(AgentSettings(slug="hr", tenant_id=a.id))
        s.add(AgentSettings(slug="hr", tenant_id=b.id))
        await s.commit()


async def _seed_two_tenants(pg_engine):
    """Create tenants a and b, each with one user. Returns (tid_a, tid_b, uid_a, uid_b)."""
    tid_a, tid_b = uuid.uuid4(), uuid.uuid4()
    uid_a, uid_b = uuid.uuid4(), uuid.uuid4()
    async with pg_engine.begin() as conn:
        for tid, slug in [(tid_a, "a"), (tid_b, "b")]:
            await conn.execute(text("INSERT INTO tenants(id,slug,name) VALUES (:i,:s,:s)"), {"i": tid, "s": slug})
        for uid, tid, slug in [(uid_a, tid_a, "a"), (uid_b, tid_b, "b")]:
            await conn.execute(text(
                "INSERT INTO users(id,email,password_hash,tenant_id,role) "
                "VALUES (:u, :e, 'x', :t, 'user')"
            ), {"u": uid, "e": f"user@{slug}.test", "t": tid})
    return tid_a, tid_b, uid_a, uid_b


async def test_rls_blocks_cross_tenant_read(pg_engine):
    """As app_rls scoped to tenant B, tenant A's rows are invisible."""
    tid_a, tid_b, uid_a, _ = await _seed_two_tenants(pg_engine)
    async with pg_engine.begin() as conn:
        await conn.execute(text(
            "INSERT INTO conversations(id,user_id,tenant_id) VALUES (gen_random_uuid(), :u, :t)"
        ), {"u": uid_a, "t": tid_a})
    async with pg_engine.connect() as conn:
        await conn.execute(text("SET ROLE app_rls"))
        await conn.execute(text("SELECT set_config('app.tenant_id', :t, false)"), {"t": str(tid_b)})
        count = (await conn.execute(text("SELECT count(*) FROM conversations"))).scalar()
        assert count == 0


async def test_rls_allows_own_tenant_read(pg_engine):
    """As app_rls scoped to tenant A, tenant A's own rows are visible."""
    tid_a, _, uid_a, _ = await _seed_two_tenants(pg_engine)
    async with pg_engine.begin() as conn:
        await conn.execute(text(
            "INSERT INTO conversations(id,user_id,tenant_id) VALUES (gen_random_uuid(), :u, :t)"
        ), {"u": uid_a, "t": tid_a})
    async with pg_engine.connect() as conn:
        await conn.execute(text("SET ROLE app_rls"))
        await conn.execute(text("SELECT set_config('app.tenant_id', :t, false)"), {"t": str(tid_a)})
        count = (await conn.execute(text("SELECT count(*) FROM conversations"))).scalar()
        assert count == 1


async def test_rls_rejects_cross_tenant_write(pg_engine):
    """WITH CHECK rejects an INSERT that stamps another tenant's id."""
    tid_a, tid_b, uid_a, _ = await _seed_two_tenants(pg_engine)
    async with pg_engine.connect() as conn:
        await conn.execute(text("SET ROLE app_rls"))
        await conn.execute(text("SELECT set_config('app.tenant_id', :t, false)"), {"t": str(tid_a)})
        with pytest.raises(Exception):
            await conn.execute(text(
                "INSERT INTO conversations(id,user_id,tenant_id) VALUES (gen_random_uuid(), :u, :b)"
            ), {"u": uid_a, "b": str(tid_b)})
            await conn.commit()


async def test_unscoped_query_sees_nothing(pg_engine):
    """With no app.tenant_id set, app_rls sees zero rows (fail-closed)."""
    tid_a, _, uid_a, _ = await _seed_two_tenants(pg_engine)
    async with pg_engine.begin() as conn:
        await conn.execute(text(
            "INSERT INTO conversations(id,user_id,tenant_id) VALUES (gen_random_uuid(), :u, :t)"
        ), {"u": uid_a, "t": tid_a})
    async with pg_engine.connect() as conn:
        await conn.execute(text("SET ROLE app_rls"))
        count = (await conn.execute(text("SELECT count(*) FROM conversations"))).scalar()
        assert count == 0
