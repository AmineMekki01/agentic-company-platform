"""Celery task: execute an agent evaluation run asynchronously."""

import logging
import uuid

from sqlalchemy import select

from app.celery_app import celery_app
from app.db.celery_session import get_celery_session_factory, run_async, tenant_scoped_session
from app.models import AgentEvalRun, AgentEvalResult, AgentEvalSchedule, AgentEvalTest, AgentEvalTestSet, AgentSettings
from app.services.eval_runner import run_single_test
from app.tasks.base import TenantTask

logger = logging.getLogger(__name__)

_worker_runtime = None

async def _get_worker_runtime():
    """Return a singleton AgentRuntime for the Celery worker process."""
    global _worker_runtime
    if _worker_runtime is None or _worker_runtime.graph is None:
        from app.agents.runtime import AgentRuntime
        _worker_runtime = AgentRuntime()
        await _worker_runtime.startup()
    return _worker_runtime


@celery_app.task(bind=True, base=TenantTask, max_retries=3)
def execute_eval_run(self, run_id: str, test_set_ids: list[str] | None = None, tenant_id: str | None = None):
    """Execute an agent evaluation run in a background Celery task."""
    run_async(_run_evaluation(run_id, test_set_ids))


async def _run_evaluation(run_id: str, test_set_ids: list[str] | None = None):
    from datetime import datetime, timezone

    try:
        async with tenant_scoped_session() as db:
            run = await db.get(AgentEvalRun, uuid.UUID(run_id))
            if run is None:
                logger.error("Eval run %s not found", run_id)
                return

            agent = await db.get(AgentSettings, run.agent_id)
            if agent is None:
                logger.error("Agent %s not found for eval run %s", run.agent_id, run_id)
                run.status = "failed"
                run.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return

            use_draft = agent.draft_config is not None and len(agent.draft_config) > 0
            logger.info(
                "Agent %s is_published=%s use_draft=%s before eval run",
                agent.slug, agent.is_published, use_draft,
            )
            run.status = "running"
            run.started_at = datetime.now(timezone.utc)
            run.config_source = "draft" if use_draft else "published"
            if not use_draft:
                run.agent_version_id = agent.published_version_id
            await db.commit()

            if test_set_ids:
                ts_uuids = [uuid.UUID(tsid) for tsid in test_set_ids]
                stmt = (
                    select(AgentEvalTest)
                    .join(AgentEvalTestSet, AgentEvalTest.test_set_id == AgentEvalTestSet.id)
                    .where(AgentEvalTestSet.agent_id == run.agent_id)
                    .where(AgentEvalTestSet.id.in_(ts_uuids))
                )
            else:
                stmt = (
                    select(AgentEvalTest)
                    .join(AgentEvalTestSet, AgentEvalTest.test_set_id == AgentEvalTestSet.id)
                    .where(AgentEvalTestSet.agent_id == run.agent_id)
                )
            result = await db.execute(stmt)
            tests = result.scalars().all()

            if not tests:
                run.status = "completed"
                run.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return

            if use_draft:
                from app.agents.runtime import build_graph_config
                from app.agents.graph import build_graph
                async with session_factory() as cfg_session:
                    registry, settings_map, workflows = await build_graph_config(cfg_session, slug=agent.slug)
                graph = build_graph(
                    checkpointer=None,
                    agent_registry=registry,
                    agent_settings=settings_map,
                    workflows=workflows,
                )
            else:
                runtime = await _get_worker_runtime()
                await runtime.refresh_graph()
                graph = runtime.graph

            for test in tests:
                logger.info("Evaluating test %s for agent %s", test.id, agent.slug)
                try:
                    eval_result = await run_single_test(
                        graph=graph,
                        agent_slug=agent.slug,
                        question=test.question,
                        expected_answer=test.expected_answer,
                    )
                except Exception:
                    logger.exception("Test %s failed", test.id)
                    eval_result = {
                        "actual_answer": "",
                        "retrieved_contexts": [],
                        "metrics": {},
                        "score": 0.0,
                        "duration_ms": 0,
                        "trace_url": None,
                    }

                thresholds = run.thresholds or {}
                metric_passes: dict[str, bool] = {}
                for metric_name, value in eval_result.get("metrics", {}).items():
                    threshold = thresholds.get(metric_name, 0.5)
                    metric_passes[metric_name] = value >= threshold

                passed = all(metric_passes.values()) if metric_passes else False

                logger.info(
                    "Test %s score=%.3f passed=%s metric_passes=%s",
                    test.id, eval_result["score"], passed, metric_passes,
                )

                res = AgentEvalResult(
                    run_id=run.id,
                    test_id=test.id,
                    actual_answer=eval_result["actual_answer"],
                    retrieved_contexts=eval_result["retrieved_contexts"],
                    metrics=eval_result["metrics"],
                    metric_passes=metric_passes,
                    score=eval_result["score"],
                    passed=passed,
                    duration_ms=eval_result["duration_ms"],
                    trace_url=eval_result.get("trace_url"),
                )
                db.add(res)

            await db.commit()
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            await db.commit()

            agent_after = await db.get(AgentSettings, run.agent_id)
            if agent_after:
                logger.info("Agent %s is_published=%s after eval run", agent_after.slug, agent_after.is_published)

    except Exception:
        logger.exception("Eval run %s failed", run_id)
        async with tenant_scoped_session() as db:
            run = await db.get(AgentEvalRun, uuid.UUID(run_id))
            if run:
                run.status = "failed"
                run.completed_at = datetime.now(timezone.utc)
                await db.commit()


@celery_app.task
def process_eval_schedules():
    """Dispatcher: fan out schedule processing per active tenant."""
    async def _dispatch():
        from app.db.celery_session import iter_active_tenant_ids
        for tid in await iter_active_tenant_ids():
            process_eval_schedules_for_tenant.delay(tenant_id=str(tid))

    run_async(_dispatch())


@celery_app.task(base=TenantTask)
def process_eval_schedules_for_tenant(tenant_id: str):
    """Check one tenant's enabled eval schedules and trigger due runs."""
    run_async(_process_eval_schedules(tenant_id))


async def _process_eval_schedules(tenant_id: str):
    from datetime import datetime, timedelta, timezone

    async with tenant_scoped_session() as db:
        stmt = select(AgentEvalSchedule).where(AgentEvalSchedule.enabled == True)  # noqa: E712
        result = await db.execute(stmt)
        schedules = result.scalars().all()

        now = datetime.now(timezone.utc)

        freq_delta = {
            "minutes": timedelta(minutes=1),
            "hours": timedelta(hours=1),
            "days": timedelta(days=1),
            "weeks": timedelta(weeks=1),
            "months": timedelta(days=30),
            "years": timedelta(days=365),
        }

        for schedule in schedules:
            try:
                base = schedule.last_triggered_at or schedule.start_date
                if base.tzinfo is None:
                    base = base.replace(tzinfo=timezone.utc)

                start = schedule.start_date
                if start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                if now < start:
                    continue

                if schedule.end_date:
                    end = schedule.end_date
                    if end.tzinfo is None:
                        end = end.replace(tzinfo=timezone.utc)
                    if now > end:
                        continue

                delta = freq_delta.get(schedule.frequency, timedelta(days=1)) * schedule.interval
                if schedule.last_triggered_at is None:
                    next_run = start
                else:
                    next_run = base + delta

                if next_run <= now:
                    agent = await db.get(AgentSettings, schedule.agent_id)
                    if agent is None:
                        continue

                    run = AgentEvalRun(
                        agent_id=agent.id,
                        name=f"{schedule.name} (scheduled)",
                        status="pending",
                        thresholds=schedule.thresholds,
                        created_by="scheduler",
                    )
                    db.add(run)
                    await db.commit()
                    await db.refresh(run)

                    schedule.last_triggered_at = now
                    await db.commit()

                    test_set_ids = schedule.test_set_ids if schedule.test_set_ids else None
                    execute_eval_run.delay(str(run.id), test_set_ids, tenant_id=tenant_id)
                    logger.info("Triggered scheduled eval run %s for agent %s", run.id, agent.slug)
            except Exception:
                logger.exception("Failed to process eval schedule %s", schedule.id)
