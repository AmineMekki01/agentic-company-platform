"""Celery task: execute an agent evaluation run asynchronously."""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.celery_app import celery_app
from app.core.config import settings
from app.models import AgentEvalRun, AgentEvalResult, AgentEvalTest, AgentSettings
from app.services.eval_runner import run_single_test

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def execute_eval_run(self, run_id: str):
    """Execute an agent evaluation run in a background Celery task."""
    import asyncio

    asyncio.run(_run_evaluation(run_id))


async def _run_evaluation(run_id: str):
    from datetime import datetime, timezone

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with session_factory() as db:
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

            logger.info("Agent %s is_published=%s before eval run", agent.slug, agent.is_published)
            run.status = "running"
            run.started_at = datetime.now(timezone.utc)
            await db.commit()

            stmt = select(AgentEvalTest).where(AgentEvalTest.agent_id == run.agent_id)
            result = await db.execute(stmt)
            tests = result.scalars().all()

            if not tests:
                run.status = "completed"
                run.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return

            from app.agents.runtime import AgentRuntime

            runtime = AgentRuntime()
            await runtime.startup()

            try:
                for test in tests:
                    logger.info("Evaluating test %s for agent %s", test.id, agent.slug)
                    try:
                        eval_result = await run_single_test(
                            runtime=runtime,
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
                    )
                    db.add(res)

                await db.commit()
            finally:
                await runtime.shutdown()

            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            await db.commit()

            agent_after = await db.get(AgentSettings, run.agent_id)
            if agent_after:
                logger.info("Agent %s is_published=%s after eval run", agent_after.slug, agent_after.is_published)

    except Exception:
        logger.exception("Eval run %s failed", run_id)
        async with session_factory() as db:
            run = await db.get(AgentEvalRun, uuid.UUID(run_id))
            if run:
                run.status = "failed"
                run.completed_at = datetime.now(timezone.utc)
                await db.commit()
    finally:
        await engine.dispose()
