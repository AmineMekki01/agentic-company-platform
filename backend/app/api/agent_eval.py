"""Admin agent evaluation API."""

import uuid

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import AdminUser, DbSession
from app.models import AgentEvalResult, AgentEvalRun, AgentEvalTest, AgentSettings
from app.schemas.agent_eval import (
    AgentEvalResultOut,
    AgentEvalRunCreate,
    AgentEvalRunDetailOut,
    AgentEvalRunOut,
    AgentEvalTestCreate,
    AgentEvalTestOut,
    AgentEvalTestUpdate,
)
from app.tasks.eval_tasks import execute_eval_run

router = APIRouter(prefix="/admin/agents", tags=["admin"])


async def _get_agent_by_slug(db: DbSession, slug: str) -> AgentSettings:
    agent = await db.scalar(select(AgentSettings).where(AgentSettings.slug == slug))
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.get("/{slug}/eval-tests", response_model=list[AgentEvalTestOut])
async def list_eval_tests(
    slug: str,
    user: AdminUser,
    db: DbSession,
) -> list[AgentEvalTestOut]:
    """List all evaluation tests for an agent."""
    agent = await _get_agent_by_slug(db, slug)
    stmt = (
        select(AgentEvalTest)
        .where(AgentEvalTest.agent_id == agent.id)
        .order_by(AgentEvalTest.created_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [AgentEvalTestOut.model_validate(r) for r in rows]


@router.post("/{slug}/eval-tests", response_model=AgentEvalTestOut, status_code=201)
async def create_eval_test(
    slug: str,
    user: AdminUser,
    db: DbSession,
    body: AgentEvalTestCreate,
) -> AgentEvalTestOut:
    """Create a new evaluation test for an agent."""
    agent = await _get_agent_by_slug(db, slug)
    test = AgentEvalTest(
        agent_id=agent.id,
        name=body.name,
        question=body.question,
        expected_answer=body.expected_answer,
        created_by=user.email,
    )
    db.add(test)
    await db.commit()
    await db.refresh(test)
    return AgentEvalTestOut.model_validate(test)


@router.put("/{slug}/eval-tests/{test_id}", response_model=AgentEvalTestOut)
async def update_eval_test(
    slug: str,
    test_id: uuid.UUID,
    user: AdminUser,
    db: DbSession,
    body: AgentEvalTestUpdate,
) -> AgentEvalTestOut:
    """Update an evaluation test."""
    agent = await _get_agent_by_slug(db, slug)
    test = await db.get(AgentEvalTest, test_id)
    if test is None or test.agent_id != agent.id:
        raise HTTPException(status_code=404, detail="Test not found")

    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(test, key, value)

    await db.commit()
    await db.refresh(test)
    return AgentEvalTestOut.model_validate(test)


@router.delete("/{slug}/eval-tests/{test_id}", status_code=204)
async def delete_eval_test(
    slug: str,
    test_id: uuid.UUID,
    user: AdminUser,
    db: DbSession,
):
    """Delete an evaluation test."""
    agent = await _get_agent_by_slug(db, slug)
    test = await db.get(AgentEvalTest, test_id)
    if test is None or test.agent_id != agent.id:
        raise HTTPException(status_code=404, detail="Test not found")
    await db.delete(test)
    await db.commit()


@router.get("/{slug}/eval-runs", response_model=list[AgentEvalRunOut])
async def list_eval_runs(
    slug: str,
    user: AdminUser,
    db: DbSession,
) -> list[AgentEvalRunOut]:
    """List all evaluation runs for an agent with pass/fail summary."""
    agent = await _get_agent_by_slug(db, slug)
    stmt = (
        select(AgentEvalRun)
        .where(AgentEvalRun.agent_id == agent.id)
        .order_by(AgentEvalRun.created_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()

    out: list[AgentEvalRunOut] = []
    for run in rows:
        pass_stmt = select(func.count()).where(
            AgentEvalResult.run_id == run.id, AgentEvalResult.passed == True  # noqa: E712
        )
        fail_stmt = select(func.count()).where(
            AgentEvalResult.run_id == run.id, AgentEvalResult.passed == False  # noqa: E712
        )
        total_stmt = select(func.count()).where(AgentEvalResult.run_id == run.id)
        pass_count = (await db.execute(pass_stmt)).scalar() or 0
        fail_count = (await db.execute(fail_stmt)).scalar() or 0
        total = (await db.execute(total_stmt)).scalar() or 0

        out.append(
            AgentEvalRunOut.model_validate(
                {
                    "id": run.id,
                    "agent_id": run.agent_id,
                    "name": run.name,
                    "status": run.status,
                    "thresholds": run.thresholds or {},
                    "started_at": run.started_at,
                    "completed_at": run.completed_at,
                    "created_at": run.created_at,
                    "created_by": run.created_by,
                    "pass_count": pass_count,
                    "fail_count": fail_count,
                    "total_tests": total,
                }
            )
        )
    return out


@router.post("/{slug}/eval-runs", response_model=AgentEvalRunOut, status_code=201)
async def create_eval_run(
    slug: str,
    user: AdminUser,
    db: DbSession,
    body: AgentEvalRunCreate,
) -> AgentEvalRunOut:
    """Create and enqueue an evaluation run."""
    agent = await _get_agent_by_slug(db, slug)

    if body.test_ids:
        test_stmt = select(AgentEvalTest).where(
            AgentEvalTest.agent_id == agent.id,
            AgentEvalTest.id.in_(body.test_ids),
        )
        result = await db.execute(test_stmt)
        found_tests = result.scalars().all()
        found_ids = {t.id for t in found_tests}
        missing = set(body.test_ids) - found_ids
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid test IDs: {sorted(missing)}",
            )

    run = AgentEvalRun(
        agent_id=agent.id,
        name=body.name,
        status="pending",
        thresholds=body.thresholds,
        created_by=user.email,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    execute_eval_run.delay(str(run.id))

    return AgentEvalRunOut.model_validate(
        {
            "id": run.id,
            "agent_id": run.agent_id,
            "name": run.name,
            "status": run.status,
            "thresholds": run.thresholds or {},
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "created_at": run.created_at,
            "created_by": run.created_by,
            "pass_count": 0,
            "fail_count": 0,
            "total_tests": 0,
        }
    )


@router.get("/{slug}/eval-runs/{run_id}", response_model=AgentEvalRunDetailOut)
async def get_eval_run_detail(
    slug: str,
    run_id: uuid.UUID,
    user: AdminUser,
    db: DbSession,
) -> AgentEvalRunDetailOut:
    """Get detailed results for a single evaluation run."""
    agent = await _get_agent_by_slug(db, slug)
    run = await db.get(AgentEvalRun, run_id)
    if run is None or run.agent_id != agent.id:
        raise HTTPException(status_code=404, detail="Run not found")

    pass_stmt = select(func.count()).where(
        AgentEvalResult.run_id == run.id, AgentEvalResult.passed == True  # noqa: E712
    )
    fail_stmt = select(func.count()).where(
        AgentEvalResult.run_id == run.id, AgentEvalResult.passed == False  # noqa: E712
    )
    total_stmt = select(func.count()).where(AgentEvalResult.run_id == run.id)
    pass_count = (await db.execute(pass_stmt)).scalar() or 0
    fail_count = (await db.execute(fail_stmt)).scalar() or 0
    total = (await db.execute(total_stmt)).scalar() or 0

    result_stmt = (
        select(AgentEvalResult)
        .where(AgentEvalResult.run_id == run.id)
        .options(selectinload(AgentEvalResult.test))
        .order_by(AgentEvalResult.created_at.asc())
    )
    result_rows = await db.execute(result_stmt)
    results = result_rows.scalars().all()

    results_out = []
    for res in results:
        res_dict = {
            "id": res.id,
            "run_id": res.run_id,
            "test_id": res.test_id,
            "test_name": res.test.name if res.test else "",
            "actual_answer": res.actual_answer,
            "retrieved_contexts": res.retrieved_contexts,
            "metrics": res.metrics,
            "metric_passes": res.metric_passes,
            "score": res.score,
            "passed": res.passed,
            "duration_ms": res.duration_ms,
            "created_at": res.created_at,
        }
        results_out.append(AgentEvalResultOut.model_validate(res_dict))

    return AgentEvalRunDetailOut.model_validate(
        {
            "id": run.id,
            "agent_id": run.agent_id,
            "name": run.name,
            "status": run.status,
            "thresholds": run.thresholds or {},
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "created_at": run.created_at,
            "created_by": run.created_by,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "total_tests": total,
            "results": results_out,
        }
    )


@router.delete("/{slug}/eval-runs/{run_id}", status_code=204)
async def delete_eval_run(
    slug: str,
    run_id: uuid.UUID,
    user: AdminUser,
    db: DbSession,
):
    """Delete an evaluation run and its results."""
    agent = await _get_agent_by_slug(db, slug)
    run = await db.get(AgentEvalRun, run_id)
    if run is None or run.agent_id != agent.id:
        raise HTTPException(status_code=404, detail="Run not found")
    await db.delete(run)
    await db.commit()
