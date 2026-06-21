import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pricing import estimate_cost
from app.db.session import async_session_factory
from app.models.token_budget import TokenBudget
from app.models.token_usage import TokenUsage

logger = logging.getLogger(__name__)


async def record_usage(
    user_id: str | uuid.UUID | None,
    agent_slug: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    conversation_id: str | uuid.UUID | None = None,
) -> None:
    """Persist a token usage record. Fire-and-forget — never raises.

    Args:
        user_id: User UUID (string or uuid). Skips recording if None.
        agent_slug: Agent slug that handled the request.
        model: Model name used for the LLM call.
        input_tokens: Prompt tokens consumed.
        output_tokens: Completion tokens consumed.
        conversation_id: Optional conversation UUID.
    """
    if user_id is None or (input_tokens == 0 and output_tokens == 0):
        return

    try:
        total = input_tokens + output_tokens
        cost = estimate_cost(model, input_tokens, output_tokens)
        uid = uuid.UUID(str(user_id)) if not isinstance(user_id, uuid.UUID) else user_id
        cid = uuid.UUID(str(conversation_id)) if conversation_id else None

        async with async_session_factory() as session:
            session.add(TokenUsage(
                user_id=uid,
                agent_slug=agent_slug,
                conversation_id=cid,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total,
                estimated_cost_usd=cost,
            ))
            await session.commit()
    except Exception:
        logger.exception("Failed to record token usage (agent=%s model=%s)", agent_slug, model)


async def check_budget(
    user_id: str | uuid.UUID,
    agent_slug: str,
) -> tuple[bool, int, int]:
    """Check if user or agent has exceeded their monthly token budget.

    Args:
        user_id: User UUID
        agent_slug: Agent slug

    Returns:
        Tuple of (exceeded, used_tokens, limit_tokens).
        If no budget is set, returns (False, used, 0).
    """
    uid_str = str(user_id)

    now = datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    try:
        async with async_session_factory() as session:
            cost_result = await session.scalar(
                select(func.coalesce(func.sum(TokenUsage.estimated_cost_usd), 0.0)).where(
                    TokenUsage.user_id == uuid.UUID(uid_str),
                    TokenUsage.created_at >= month_start,
                )
            )
            used_cost = float(cost_result or 0.0)

            user_budget = await session.scalar(
                select(TokenBudget).where(
                    TokenBudget.scope == "user",
                    TokenBudget.scope_id == uid_str,
                )
            )
            if user_budget and used_cost >= user_budget.monthly_cost_limit_usd:
                return True, round(used_cost, 4), user_budget.monthly_cost_limit_usd

            global_user_budget = await session.scalar(
                select(TokenBudget).where(
                    TokenBudget.scope == "user",
                    TokenBudget.scope_id == "*",
                )
            )
            if global_user_budget and used_cost >= global_user_budget.monthly_cost_limit_usd:
                return True, round(used_cost, 4), global_user_budget.monthly_cost_limit_usd

            agent_budget = await session.scalar(
                select(TokenBudget).where(
                    TokenBudget.scope == "agent",
                    TokenBudget.scope_id == agent_slug,
                )
            )
            if agent_budget:
                agent_cost_result = await session.scalar(
                    select(func.coalesce(func.sum(TokenUsage.estimated_cost_usd), 0.0)).where(
                        TokenUsage.agent_slug == agent_slug,
                        TokenUsage.created_at >= month_start,
                    )
                )
                agent_cost = float(agent_cost_result or 0.0)
                if agent_cost >= agent_budget.monthly_cost_limit_usd:
                    return True, round(agent_cost, 4), agent_budget.monthly_cost_limit_usd

            limit = user_budget.monthly_cost_limit_usd if user_budget else (global_user_budget.monthly_cost_limit_usd if global_user_budget else 0)
            return False, round(used_cost, 4), limit
    except Exception:
        logger.exception("Failed to check token budget")
        return False, 0, 0
