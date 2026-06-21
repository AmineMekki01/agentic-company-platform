"""Admin token usage analytics and budget management API."""

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select, text

from app.api.deps import AdminUser, DbSession
from app.models import TokenBudget, TokenUsage, User

router = APIRouter(prefix="/admin/usage", tags=["admin"])


class UsageSummary(BaseModel):
    total_tokens: int
    total_cost_usd: float
    total_requests: int
    input_tokens: int
    output_tokens: int
    by_agent: list[dict[str, Any]]
    by_user: list[dict[str, Any]]
    by_model: list[dict[str, Any]]


class TimeseriesPoint(BaseModel):
    date: str
    total_tokens: int
    total_cost_usd: float
    request_count: int


class RecentUsageItem(BaseModel):
    id: str
    user_email: str | None
    agent_slug: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    created_at: str


class BudgetOut(BaseModel):
    id: str
    scope: str
    scope_id: str
    monthly_cost_limit_usd: float
    created_at: str
    updated_at: str


class BudgetCreate(BaseModel):
    scope: str
    scope_id: str
    monthly_cost_limit_usd: float


def _month_start() -> datetime:
    now = datetime.now(UTC)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


@router.get("/summary", response_model=UsageSummary)
async def get_usage_summary(
    user: AdminUser,
    db: DbSession,
    start_date: str | None = Query(None, description="ISO date string; defaults to start of current month"),
    end_date: str | None = Query(None, description="ISO date string; defaults to now"),
) -> UsageSummary:
    """Get aggregated token usage summary with breakdowns."""
    start = datetime.fromisoformat(start_date) if start_date else _month_start()
    end = datetime.fromisoformat(end_date) if end_date else datetime.now(UTC)

    base_filter = TokenUsage.created_at >= start, TokenUsage.created_at < end

    total = await db.scalar(
        select(func.coalesce(func.sum(TokenUsage.total_tokens), 0)).where(*base_filter)
    )
    cost = await db.scalar(
        select(func.coalesce(func.sum(TokenUsage.estimated_cost_usd), 0.0)).where(*base_filter)
    )
    requests = await db.scalar(
        select(func.count(TokenUsage.id)).where(*base_filter)
    )
    input_total = await db.scalar(
        select(func.coalesce(func.sum(TokenUsage.input_tokens), 0)).where(*base_filter)
    )
    output_total = await db.scalar(
        select(func.coalesce(func.sum(TokenUsage.output_tokens), 0)).where(*base_filter)
    )

    by_agent_rows = await db.execute(
        select(
            TokenUsage.agent_slug,
            func.coalesce(func.sum(TokenUsage.total_tokens), 0).label("tokens"),
            func.coalesce(func.sum(TokenUsage.estimated_cost_usd), 0.0).label("cost"),
            func.count(TokenUsage.id).label("requests"),
        )
        .where(*base_filter)
        .group_by(TokenUsage.agent_slug)
        .order_by(text("tokens DESC"))
    )
    by_agent = [dict(r._mapping) for r in by_agent_rows]

    by_user_rows = await db.execute(
        select(
            TokenUsage.user_id,
            User.email.label("user_email"),
            func.coalesce(func.sum(TokenUsage.total_tokens), 0).label("tokens"),
            func.coalesce(func.sum(TokenUsage.estimated_cost_usd), 0.0).label("cost"),
            func.count(TokenUsage.id).label("requests"),
        )
        .outerjoin(User, TokenUsage.user_id == User.id)
        .where(*base_filter)
        .group_by(TokenUsage.user_id, User.email)
        .order_by(text("tokens DESC"))
    )
    by_user = [dict(r._mapping) for r in by_user_rows]

    by_model_rows = await db.execute(
        select(
            TokenUsage.model,
            func.coalesce(func.sum(TokenUsage.total_tokens), 0).label("tokens"),
            func.coalesce(func.sum(TokenUsage.estimated_cost_usd), 0.0).label("cost"),
            func.count(TokenUsage.id).label("requests"),
        )
        .where(*base_filter)
        .group_by(TokenUsage.model)
        .order_by(text("tokens DESC"))
    )
    by_model = [dict(r._mapping) for r in by_model_rows]

    return UsageSummary(
        total_tokens=int(total or 0),
        total_cost_usd=round(float(cost or 0.0), 6),
        total_requests=int(requests or 0),
        input_tokens=int(input_total or 0),
        output_tokens=int(output_total or 0),
        by_agent=[{**a, "tokens": int(a["tokens"]), "cost": round(float(a["cost"]), 6), "requests": int(a["requests"])} for a in by_agent],
        by_user=[{**u, "tokens": int(u["tokens"]), "cost": round(float(u["cost"]), 6), "requests": int(u["requests"])} for u in by_user],
        by_model=[{**m, "tokens": int(m["tokens"]), "cost": round(float(m["cost"]), 6), "requests": int(m["requests"])} for m in by_model],
    )


@router.get("/timeseries", response_model=list[TimeseriesPoint])
async def get_usage_timeseries(
    user: AdminUser,
    db: DbSession,
    days: int = Query(30, ge=1, le=365),
    agent_slug: str | None = Query(None),
) -> list[TimeseriesPoint]:
    """Get daily token usage for charting."""
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta
    start = start - timedelta(days=days)

    filters = [TokenUsage.created_at >= start]
    if agent_slug:
        filters.append(TokenUsage.agent_slug == agent_slug)

    rows = await db.execute(
        select(
            func.date_trunc("day", TokenUsage.created_at).label("date"),
            func.coalesce(func.sum(TokenUsage.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(TokenUsage.estimated_cost_usd), 0.0).label("total_cost_usd"),
            func.count(TokenUsage.id).label("request_count"),
        )
        .where(*filters)
        .group_by(text("date"))
        .order_by(text("date"))
    )

    return [
        TimeseriesPoint(
            date=str(r.date),
            total_tokens=int(r.total_tokens),
            total_cost_usd=round(float(r.total_cost_usd), 6),
            request_count=int(r.request_count),
        )
        for r in rows
    ]


@router.get("/recent", response_model=list[RecentUsageItem])
async def get_recent_usage(
    user: AdminUser,
    db: DbSession,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    agent_slug: str | None = Query(None),
) -> list[RecentUsageItem]:
    """Get paginated recent token usage records."""
    q = select(TokenUsage, User.email.label("user_email")).outerjoin(
        User, TokenUsage.user_id == User.id
    )
    if agent_slug:
        q = q.where(TokenUsage.agent_slug == agent_slug)
    q = q.order_by(TokenUsage.created_at.desc()).limit(limit).offset(offset)

    rows = await db.execute(q)
    return [
        RecentUsageItem(
            id=str(r.TokenUsage.id),
            user_email=r.user_email,
            agent_slug=r.TokenUsage.agent_slug,
            model=r.TokenUsage.model,
            input_tokens=r.TokenUsage.input_tokens,
            output_tokens=r.TokenUsage.output_tokens,
            total_tokens=r.TokenUsage.total_tokens,
            estimated_cost_usd=r.TokenUsage.estimated_cost_usd,
            created_at=r.TokenUsage.created_at.isoformat() if r.TokenUsage.created_at else "",
        )
        for r in rows
    ]


@router.get("/budgets", response_model=list[BudgetOut])
async def list_budgets(user: AdminUser, db: DbSession) -> list[BudgetOut]:
    """List all token budgets."""
    rows = await db.scalars(select(TokenBudget).order_by(TokenBudget.scope, TokenBudget.scope_id))
    return [
        BudgetOut(
            id=str(b.id),
            scope=b.scope,
            scope_id=b.scope_id,
            monthly_cost_limit_usd=b.monthly_cost_limit_usd,
            created_at=b.created_at.isoformat() if b.created_at else "",
            updated_at=b.updated_at.isoformat() if b.updated_at else "",
        )
        for b in rows
    ]


@router.put("/budgets", response_model=BudgetOut)
async def upsert_budget(
    body: BudgetCreate,
    user: AdminUser,
    db: DbSession,
) -> BudgetOut:
    """Create or update a token budget."""
    if body.scope not in ("user", "agent"):
        raise HTTPException(status_code=400, detail="scope must be 'user' or 'agent'")
    if body.monthly_cost_limit_usd <= 0:
        raise HTTPException(status_code=400, detail="monthly_cost_limit_usd must be positive")

    existing = await db.scalar(
        select(TokenBudget).where(
            TokenBudget.scope == body.scope,
            TokenBudget.scope_id == body.scope_id,
        )
    )

    if existing:
        existing.monthly_cost_limit_usd = body.monthly_cost_limit_usd
        await db.commit()
        await db.refresh(existing)
        budget = existing
    else:
        budget = TokenBudget(
            scope=body.scope,
            scope_id=body.scope_id,
            monthly_cost_limit_usd=body.monthly_cost_limit_usd,
        )
        db.add(budget)
        await db.commit()
        await db.refresh(budget)

    return BudgetOut(
        id=str(budget.id),
        scope=budget.scope,
        scope_id=budget.scope_id,
        monthly_cost_limit_usd=budget.monthly_cost_limit_usd,
        created_at=budget.created_at.isoformat() if budget.created_at else "",
        updated_at=budget.updated_at.isoformat() if budget.updated_at else "",
    )


@router.delete("/budgets/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_budget(
    budget_id: str,
    user: AdminUser,
    db: DbSession,
) -> None:
    """Delete a token budget."""
    try:
        bid = uuid.UUID(budget_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid budget ID")

    budget = await db.get(TokenBudget, bid)
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not found")

    await db.delete(budget)
    await db.commit()
