"""Tests for eval_tasks _run_evaluation – mocked DB and runtime."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


async def test_run_evaluation_run_not_found():
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=None)

    mock_sf = MagicMock()
    mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_sf.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch("app.tasks.eval_tasks.get_celery_session_factory", return_value=mock_sf):
        from app.tasks.eval_tasks import _run_evaluation
        await _run_evaluation(str(uuid.uuid4()), None)


async def test_run_evaluation_agent_not_found():
    run_id = uuid.uuid4()
    mock_run = MagicMock()
    mock_run.id = run_id
    mock_run.agent_id = uuid.uuid4()

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=[mock_run, None])
    mock_session.commit = AsyncMock()

    mock_sf = MagicMock()
    mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_sf.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch("app.tasks.eval_tasks.get_celery_session_factory", return_value=mock_sf):
        from app.tasks.eval_tasks import _run_evaluation
        await _run_evaluation(str(run_id), None)

        mock_session.commit.assert_called()


async def test_run_evaluation_no_tests():
    run_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    mock_run = MagicMock()
    mock_run.id = run_id
    mock_run.agent_id = agent_id

    mock_agent = MagicMock()
    mock_agent.slug = "hr"
    mock_agent.is_published = True
    mock_agent.draft_config = None
    mock_agent.published_version_id = None

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=[mock_run, mock_agent, mock_agent])
    mock_session.commit = AsyncMock()

    mock_execute = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_execute.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_execute)

    mock_sf = MagicMock()
    mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_sf.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch("app.tasks.eval_tasks.get_celery_session_factory", return_value=mock_sf):
        from app.tasks.eval_tasks import _run_evaluation
        await _run_evaluation(str(run_id), None)

        calls = mock_session.commit.call_args_list
        assert len(calls) >= 2


async def test_run_evaluation_with_tests():
    run_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    mock_run = MagicMock()
    mock_run.id = run_id
    mock_run.agent_id = agent_id
    mock_run.thresholds = {"answer_correctness": 0.7}

    mock_agent = MagicMock()
    mock_agent.slug = "hr"
    mock_agent.is_published = True
    mock_agent.draft_config = None
    mock_agent.published_version_id = None

    mock_test = MagicMock()
    mock_test.id = uuid.uuid4()
    mock_test.question = "What is the policy?"
    mock_test.expected_answer = "30 days"

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=[mock_run, mock_agent, mock_agent])
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    mock_execute = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_test]
    mock_execute.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_execute)

    mock_sf = MagicMock()
    mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_sf.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_runtime = MagicMock()
    mock_runtime.graph = MagicMock()
    mock_runtime.refresh_graph = AsyncMock()
    mock_runtime.startup = AsyncMock()
    mock_runtime.shutdown = AsyncMock()

    with patch("app.tasks.eval_tasks.get_celery_session_factory", return_value=mock_sf), \
         patch("app.tasks.eval_tasks.run_single_test", new_callable=AsyncMock) as mock_run_test, \
         patch("app.tasks.eval_tasks._get_worker_runtime", new_callable=AsyncMock, return_value=mock_runtime):

        mock_run_test.return_value = {
            "actual_answer": "The policy is 30 days.",
            "retrieved_contexts": ["context1"],
            "metrics": {"answer_correctness": 0.85, "answer_relevancy": 0.6},
            "score": 0.85,
            "duration_ms": 150,
        }

        from app.tasks.eval_tasks import _run_evaluation
        await _run_evaluation(str(run_id), None)

        mock_run_test.assert_called_once()
        mock_session.add.assert_called_once()
        assert mock_session.commit.call_count >= 3


async def test_run_evaluation_test_exception_handled():
    run_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    mock_run = MagicMock()
    mock_run.id = run_id
    mock_run.agent_id = agent_id
    mock_run.thresholds = {}

    mock_agent = MagicMock()
    mock_agent.slug = "hr"
    mock_agent.is_published = True
    mock_agent.draft_config = None
    mock_agent.published_version_id = None

    mock_test = MagicMock()
    mock_test.id = uuid.uuid4()
    mock_test.question = "What?"
    mock_test.expected_answer = "Answer"

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=[mock_run, mock_agent, mock_agent])
    mock_session.commit = AsyncMock()
    mock_session.add = MagicMock()

    mock_execute = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [mock_test]
    mock_execute.scalars.return_value = mock_scalars
    mock_session.execute = AsyncMock(return_value=mock_execute)

    mock_sf = MagicMock()
    mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_sf.return_value.__aexit__ = AsyncMock(return_value=None)

    mock_runtime = MagicMock()
    mock_runtime.graph = MagicMock()
    mock_runtime.refresh_graph = AsyncMock()
    mock_runtime.startup = AsyncMock()
    mock_runtime.shutdown = AsyncMock()

    with patch("app.tasks.eval_tasks.get_celery_session_factory", return_value=mock_sf), \
         patch("app.tasks.eval_tasks.run_single_test", new_callable=AsyncMock) as mock_run_test, \
         patch("app.tasks.eval_tasks._get_worker_runtime", new_callable=AsyncMock, return_value=mock_runtime):

        mock_run_test.side_effect = Exception("LLM timeout")

        from app.tasks.eval_tasks import _run_evaluation
        await _run_evaluation(str(run_id), None)

        mock_session.add.assert_called_once()
        result_arg = mock_session.add.call_args.args[0]
        assert result_arg.actual_answer == ""
        assert result_arg.score == 0.0


async def test_run_evaluation_outer_exception():
    run_id = uuid.uuid4()

    mock_session = AsyncMock()
    mock_session.get = AsyncMock(side_effect=[Exception("DB connection lost"), None])
    mock_session.commit = AsyncMock()

    mock_sf = MagicMock()
    mock_sf.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_sf.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch("app.tasks.eval_tasks.get_celery_session_factory", return_value=mock_sf):
        from app.tasks.eval_tasks import _run_evaluation
        await _run_evaluation(str(run_id), None)
