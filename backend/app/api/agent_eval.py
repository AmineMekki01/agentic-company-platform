"""Admin agent evaluation API."""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import AdminUser, DbSession
from app.models import (
    AgentEvalResult,
    AgentEvalRun,
    AgentEvalSchedule,
    AgentEvalTest,
    AgentEvalTestSet,
    AgentSettings,
)
from app.schemas.agent_eval import (
    AgentEvalResultOut,
    AgentEvalRunCreate,
    AgentEvalRunDetailOut,
    AgentEvalRunOut,
    AgentEvalScheduleCreate,
    AgentEvalScheduleOut,
    AgentEvalScheduleUpdate,
    AgentEvalTestCreate,
    AgentEvalTestOut,
    AgentEvalTestSetCreate,
    AgentEvalTestSetDetailOut,
    AgentEvalTestSetOut,
    AgentEvalTestSetUpdate,
    AgentEvalTestUpdate,
)
from app.tasks.eval_tasks import execute_eval_run

router = APIRouter(prefix="/admin/agents", tags=["admin"])


async def _get_agent_by_slug(db: DbSession, slug: str) -> AgentSettings:
    agent = await db.scalar(select(AgentSettings).where(AgentSettings.slug == slug))
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.get("/{slug}/eval-test-sets", response_model=list[AgentEvalTestSetDetailOut])
async def list_eval_test_sets(
    slug: str,
    user: AdminUser,
    db: DbSession,
) -> list[AgentEvalTestSetDetailOut]:
    """List all evaluation test sets for an agent with their tests."""
    agent = await _get_agent_by_slug(db, slug)
    stmt = (
        select(AgentEvalTestSet)
        .where(AgentEvalTestSet.agent_id == agent.id)
        .options(selectinload(AgentEvalTestSet.tests))
        .order_by(AgentEvalTestSet.created_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [
        AgentEvalTestSetDetailOut(
            id=r.id,
            agent_id=r.agent_id,
            name=r.name,
            description=r.description,
            created_at=r.created_at,
            created_by=r.created_by,
            tests=[AgentEvalTestOut.model_validate(t) for t in r.tests],
        )
        for r in rows
    ]


@router.post("/{slug}/eval-test-sets", response_model=AgentEvalTestSetOut, status_code=201)
async def create_eval_test_set(
    slug: str,
    user: AdminUser,
    db: DbSession,
    body: AgentEvalTestSetCreate,
) -> AgentEvalTestSetOut:
    """Create a new evaluation test set."""
    agent = await _get_agent_by_slug(db, slug)
    test_set = AgentEvalTestSet(
        agent_id=agent.id,
        name=body.name,
        description=body.description,
        created_by=user.email,
    )
    db.add(test_set)
    await db.commit()
    await db.refresh(test_set)
    return AgentEvalTestSetOut.model_validate(test_set)


@router.put("/{slug}/eval-test-sets/{test_set_id}", response_model=AgentEvalTestSetOut)
async def update_eval_test_set(
    slug: str,
    test_set_id: uuid.UUID,
    user: AdminUser,
    db: DbSession,
    body: AgentEvalTestSetUpdate,
) -> AgentEvalTestSetOut:
    """Update an evaluation test set."""
    agent = await _get_agent_by_slug(db, slug)
    test_set = await db.get(AgentEvalTestSet, test_set_id)
    if test_set is None or test_set.agent_id != agent.id:
        raise HTTPException(status_code=404, detail="Test set not found")
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(test_set, key, value)
    await db.commit()
    await db.refresh(test_set)
    return AgentEvalTestSetOut.model_validate(test_set)


@router.delete("/{slug}/eval-test-sets/{test_set_id}", status_code=204)
async def delete_eval_test_set(
    slug: str,
    test_set_id: uuid.UUID,
    user: AdminUser,
    db: DbSession,
):
    """Delete an evaluation test set and all its tests."""
    agent = await _get_agent_by_slug(db, slug)
    test_set = await db.get(AgentEvalTestSet, test_set_id)
    if test_set is None or test_set.agent_id != agent.id:
        raise HTTPException(status_code=404, detail="Test set not found")
    await db.delete(test_set)
    await db.commit()


@router.post("/{slug}/eval-test-sets/{test_set_id}/tests", response_model=AgentEvalTestOut, status_code=201)
async def create_eval_test(
    slug: str,
    test_set_id: uuid.UUID,
    user: AdminUser,
    db: DbSession,
    body: AgentEvalTestCreate,
) -> AgentEvalTestOut:
    """Create a new test within a test set."""
    agent = await _get_agent_by_slug(db, slug)
    test_set = await db.get(AgentEvalTestSet, test_set_id)
    if test_set is None or test_set.agent_id != agent.id:
        raise HTTPException(status_code=404, detail="Test set not found")
    test = AgentEvalTest(
        test_set_id=test_set.id,
        question=body.question,
        expected_answer=body.expected_answer,
    )
    db.add(test)
    await db.commit()
    await db.refresh(test)
    return AgentEvalTestOut.model_validate(test)


@router.put("/{slug}/eval-test-sets/{test_set_id}/tests/{test_id}", response_model=AgentEvalTestOut)
async def update_eval_test(
    slug: str,
    test_set_id: uuid.UUID,
    test_id: uuid.UUID,
    user: AdminUser,
    db: DbSession,
    body: AgentEvalTestUpdate,
) -> AgentEvalTestOut:
    """Update a test within a test set."""
    agent = await _get_agent_by_slug(db, slug)
    test_set = await db.get(AgentEvalTestSet, test_set_id)
    if test_set is None or test_set.agent_id != agent.id:
        raise HTTPException(status_code=404, detail="Test set not found")
    test = await db.get(AgentEvalTest, test_id)
    if test is None or test.test_set_id != test_set.id:
        raise HTTPException(status_code=404, detail="Test not found")
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(test, key, value)
    await db.commit()
    await db.refresh(test)
    return AgentEvalTestOut.model_validate(test)


@router.delete("/{slug}/eval-test-sets/{test_set_id}/tests/{test_id}", status_code=204)
async def delete_eval_test(
    slug: str,
    test_set_id: uuid.UUID,
    test_id: uuid.UUID,
    user: AdminUser,
    db: DbSession,
):
    """Delete a test from a test set."""
    agent = await _get_agent_by_slug(db, slug)
    test_set = await db.get(AgentEvalTestSet, test_set_id)
    if test_set is None or test_set.agent_id != agent.id:
        raise HTTPException(status_code=404, detail="Test set not found")
    test = await db.get(AgentEvalTest, test_id)
    if test is None or test.test_set_id != test_set.id:
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

    if body.test_set_ids:
        ts_stmt = select(AgentEvalTestSet).where(
            AgentEvalTestSet.agent_id == agent.id,
            AgentEvalTestSet.id.in_(body.test_set_ids),
        )
        result = await db.execute(ts_stmt)
        found = result.scalars().all()
        found_ids = {ts.id for ts in found}
        missing = set(body.test_set_ids) - found_ids
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid test set IDs: {sorted(missing)}",
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

    execute_eval_run.delay(str(run.id), [str(tsid) for tsid in body.test_set_ids])

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
            "test_name": res.test.question[:80] if res.test else "",
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


@router.get("/{slug}/eval-schedules", response_model=list[AgentEvalScheduleOut])
async def list_eval_schedules(
    slug: str,
    user: AdminUser,
    db: DbSession,
) -> list[AgentEvalScheduleOut]:
    """List all evaluation schedules for an agent."""
    agent = await _get_agent_by_slug(db, slug)
    stmt = (
        select(AgentEvalSchedule)
        .where(AgentEvalSchedule.agent_id == agent.id)
        .order_by(AgentEvalSchedule.created_at.desc())
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [AgentEvalScheduleOut.model_validate(r) for r in rows]


@router.post("/{slug}/eval-schedules", response_model=AgentEvalScheduleOut, status_code=201)
async def create_eval_schedule(
    slug: str,
    user: AdminUser,
    db: DbSession,
    body: AgentEvalScheduleCreate,
) -> AgentEvalScheduleOut:
    """Create a new evaluation schedule for an agent."""
    agent = await _get_agent_by_slug(db, slug)

    if body.test_set_ids:
        ts_stmt = select(AgentEvalTestSet).where(
            AgentEvalTestSet.agent_id == agent.id,
            AgentEvalTestSet.id.in_(body.test_set_ids),
        )
        result = await db.execute(ts_stmt)
        found = result.scalars().all()
        found_ids = {ts.id for ts in found}
        missing = set(body.test_set_ids) - found_ids
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid test set IDs: {sorted(missing)}",
            )

    schedule = AgentEvalSchedule(
        agent_id=agent.id,
        name=body.name,
        frequency=body.frequency,
        interval=body.interval,
        start_date=body.start_date,
        end_date=body.end_date,
        test_set_ids=[str(tsid) for tsid in body.test_set_ids] if body.test_set_ids else None,
        thresholds=body.thresholds,
        enabled=body.enabled,
        created_by=user.email,
    )
    db.add(schedule)
    await db.commit()
    await db.refresh(schedule)
    return AgentEvalScheduleOut.model_validate(schedule)


@router.put("/{slug}/eval-schedules/{schedule_id}", response_model=AgentEvalScheduleOut)
async def update_eval_schedule(
    slug: str,
    schedule_id: uuid.UUID,
    user: AdminUser,
    db: DbSession,
    body: AgentEvalScheduleUpdate,
) -> AgentEvalScheduleOut:
    """Update an evaluation schedule."""
    agent = await _get_agent_by_slug(db, slug)
    schedule = await db.get(AgentEvalSchedule, schedule_id)
    if schedule is None or schedule.agent_id != agent.id:
        raise HTTPException(status_code=404, detail="Schedule not found")

    data = body.model_dump(exclude_unset=True)
    if "test_set_ids" in data and data["test_set_ids"] is not None:
        data["test_set_ids"] = [str(tsid) for tsid in data["test_set_ids"]]
    for key, value in data.items():
        setattr(schedule, key, value)

    await db.commit()
    await db.refresh(schedule)
    return AgentEvalScheduleOut.model_validate(schedule)


@router.delete("/{slug}/eval-schedules/{schedule_id}", status_code=204)
async def delete_eval_schedule(
    slug: str,
    schedule_id: uuid.UUID,
    user: AdminUser,
    db: DbSession,
):
    """Delete an evaluation schedule."""
    agent = await _get_agent_by_slug(db, slug)
    schedule = await db.get(AgentEvalSchedule, schedule_id)
    if schedule is None or schedule.agent_id != agent.id:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await db.delete(schedule)
    await db.commit()
