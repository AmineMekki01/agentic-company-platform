"""Tests for eval runner service – mocked LLM graph and Ragas metrics."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage

pytestmark = pytest.mark.asyncio


async def test_run_single_test_basic():
    from app.services import eval_runner

    fake_graph = MagicMock()
    fake_final_state = {
        "messages": [
            HumanMessage(content="What is the policy?"),
            AIMessage(content="The policy is 30 days."),
        ],
        "sources": [],
    }
    fake_graph.ainvoke = AsyncMock(return_value=fake_final_state)

    with patch("app.services.eval_runner._get_ragas_llm") as mock_llm, \
         patch("app.services.eval_runner._get_ragas_embeddings") as mock_emb, \
         patch("ragas.dataset_schema.SingleTurnSample"), \
         patch("ragas.metrics.AnswerCorrectness") as mock_ac_cls, \
         patch("ragas.metrics.AnswerRelevancy") as mock_ar_cls, \
         patch("ragas.metrics.Faithfulness") as mock_f_cls, \
         patch("ragas.metrics._answer_similarity.AnswerSimilarity") as mock_as_cls:

        mock_metric = MagicMock()
        mock_metric.single_turn_ascore = AsyncMock(return_value=0.85)
        mock_ac_cls.return_value = mock_metric
        mock_ar_cls.return_value = mock_metric
        mock_f_cls.return_value = mock_metric
        mock_as_cls.return_value = MagicMock()

        result = await eval_runner.run_single_test(
            fake_graph,
            "hr",
            "What is the policy?",
            "The policy is 30 days.",
        )

        assert result["actual_answer"] == "The policy is 30 days."
        assert "answer_correctness" in result["metrics"]
        assert "answer_relevancy" in result["metrics"]
        assert result["score"] > 0
        assert result["duration_ms"] >= 0
        assert result["trace_url"] is None  # no Langfuse configured in tests


async def test_run_single_test_includes_trace_url_when_tracing_enabled():
    """When Langfuse is enabled, run_single_test should surface a trace link
    built from the fresh per-call handler's last_trace_id, so an eval result
    can link straight to the exact trace for that test."""
    from app.services import eval_runner

    fake_graph = MagicMock()
    fake_final_state = {
        "messages": [
            HumanMessage(content="What is the policy?"),
            AIMessage(content="The policy is 30 days."),
        ],
        "sources": [],
    }
    fake_graph.ainvoke = AsyncMock(return_value=fake_final_state)

    fake_handler = MagicMock()
    fake_handler.last_trace_id = "abc123"

    with patch("app.services.eval_runner._get_ragas_llm") as mock_llm, \
         patch("app.services.eval_runner._get_ragas_embeddings") as mock_emb, \
         patch("app.services.eval_runner.new_langfuse_handler", return_value=fake_handler), \
         patch("app.services.eval_runner.trace_url_for", return_value="http://localhost:3000/trace/abc123"), \
         patch("ragas.dataset_schema.SingleTurnSample"), \
         patch("ragas.metrics.AnswerCorrectness") as mock_ac_cls, \
         patch("ragas.metrics.AnswerRelevancy") as mock_ar_cls, \
         patch("ragas.metrics.Faithfulness") as mock_f_cls, \
         patch("ragas.metrics._answer_similarity.AnswerSimilarity") as mock_as_cls:

        mock_metric = MagicMock()
        mock_metric.single_turn_ascore = AsyncMock(return_value=0.85)
        mock_ac_cls.return_value = mock_metric
        mock_ar_cls.return_value = mock_metric
        mock_f_cls.return_value = mock_metric
        mock_as_cls.return_value = MagicMock()

        result = await eval_runner.run_single_test(
            fake_graph, "hr", "What is the policy?", "The policy is 30 days.",
        )

        assert result["trace_url"] == "http://localhost:3000/trace/abc123"

        call_args = fake_graph.ainvoke.call_args
        assert call_args[0][1]["callbacks"] == [fake_handler]


async def test_run_single_test_with_retrieved_contexts_from_tool():
    from app.services import eval_runner

    tool_msg = MagicMock()
    tool_msg.name = "retrieve"
    tool_msg.content = "Policy document content"

    fake_graph = MagicMock()
    fake_final_state = {
        "messages": [
            HumanMessage(content="What is the policy?"),
            tool_msg,
            AIMessage(content="The policy is 30 days."),
        ],
        "sources": [],
    }
    fake_graph.ainvoke = AsyncMock(return_value=fake_final_state)

    with patch("app.services.eval_runner._get_ragas_llm"), \
         patch("app.services.eval_runner._get_ragas_embeddings"), \
         patch("ragas.dataset_schema.SingleTurnSample"), \
         patch("ragas.metrics.AnswerCorrectness") as mock_ac_cls, \
         patch("ragas.metrics.AnswerRelevancy") as mock_ar_cls, \
         patch("ragas.metrics.Faithfulness") as mock_f_cls, \
         patch("ragas.metrics._answer_similarity.AnswerSimilarity") as mock_as_cls:

        mock_metric = MagicMock()
        mock_metric.single_turn_ascore = AsyncMock(return_value=0.9)
        mock_ac_cls.return_value = mock_metric
        mock_ar_cls.return_value = mock_metric
        mock_f_cls.return_value = mock_metric
        mock_as_cls.return_value = MagicMock()

        result = await eval_runner.run_single_test(
            fake_graph, "hr", "question", "answer"
        )
        assert len(result["retrieved_contexts"]) == 1
        assert result["retrieved_contexts"][0] == "Policy document content"
        assert "faithfulness" in result["metrics"]


async def test_run_single_test_with_sources_list():
    from app.services import eval_runner

    fake_graph = MagicMock()
    fake_final_state = {
        "messages": [
            HumanMessage(content="question"),
            AIMessage(content="answer"),
        ],
        "sources": [
            {"chunk_text": "source chunk 1"},
            {"text": "source chunk 2"},
        ],
    }
    fake_graph.ainvoke = AsyncMock(return_value=fake_final_state)

    with patch("app.services.eval_runner._get_ragas_llm"), \
         patch("app.services.eval_runner._get_ragas_embeddings"), \
         patch("ragas.dataset_schema.SingleTurnSample"), \
         patch("ragas.metrics.AnswerCorrectness") as mock_ac_cls, \
         patch("ragas.metrics.AnswerRelevancy") as mock_ar_cls, \
         patch("ragas.metrics.Faithfulness") as mock_f_cls, \
         patch("ragas.metrics._answer_similarity.AnswerSimilarity") as mock_as_cls:

        mock_metric = MagicMock()
        mock_metric.single_turn_ascore = AsyncMock(return_value=0.8)
        mock_ac_cls.return_value = mock_metric
        mock_ar_cls.return_value = mock_metric
        mock_f_cls.return_value = mock_metric
        mock_as_cls.return_value = MagicMock()

        result = await eval_runner.run_single_test(
            fake_graph, "hr", "question", "answer"
        )
        assert len(result["retrieved_contexts"]) == 2
        assert result["retrieved_contexts"][0] == "source chunk 1"
        assert result["retrieved_contexts"][1] == "source chunk 2"


async def test_run_single_test_metric_exception_returns_zero():
    from app.services import eval_runner

    fake_graph = MagicMock()
    fake_final_state = {
        "messages": [HumanMessage(content="q"), AIMessage(content="a")],
        "sources": [],
    }
    fake_graph.ainvoke = AsyncMock(return_value=fake_final_state)

    with patch("app.services.eval_runner._get_ragas_llm"), \
         patch("app.services.eval_runner._get_ragas_embeddings"), \
         patch("ragas.dataset_schema.SingleTurnSample"), \
         patch("ragas.metrics.AnswerCorrectness") as mock_ac_cls, \
         patch("ragas.metrics.AnswerRelevancy") as mock_ar_cls, \
         patch("ragas.metrics.Faithfulness"), \
         patch("ragas.metrics._answer_similarity.AnswerSimilarity") as mock_as_cls:

        mock_metric = MagicMock()
        mock_metric.single_turn_ascore = AsyncMock(side_effect=Exception("LLM error"))
        mock_ac_cls.return_value = mock_metric
        mock_ar_cls.return_value = mock_metric
        mock_as_cls.return_value = MagicMock()

        result = await eval_runner.run_single_test(
            fake_graph, "hr", "q", "a"
        )
        assert result["metrics"]["answer_correctness"] == 0.0
        assert result["metrics"]["answer_relevancy"] == 0.0


async def test_run_single_test_content_as_list():
    from app.services import eval_runner

    fake_graph = MagicMock()
    ai_msg = MagicMock()
    ai_msg.type = "ai"
    ai_msg.role = "assistant"
    ai_msg.content = [{"type": "text", "text": "List answer"}]

    fake_final_state = {
        "messages": [HumanMessage(content="q"), ai_msg],
        "sources": [],
    }
    fake_graph.ainvoke = AsyncMock(return_value=fake_final_state)

    with patch("app.services.eval_runner._get_ragas_llm"), \
         patch("app.services.eval_runner._get_ragas_embeddings"), \
         patch("ragas.dataset_schema.SingleTurnSample"), \
         patch("ragas.metrics.AnswerCorrectness") as mock_ac_cls, \
         patch("ragas.metrics.AnswerRelevancy") as mock_ar_cls, \
         patch("ragas.metrics.Faithfulness"), \
         patch("ragas.metrics._answer_similarity.AnswerSimilarity") as mock_as_cls:

        mock_metric = MagicMock()
        mock_metric.single_turn_ascore = AsyncMock(return_value=0.7)
        mock_ac_cls.return_value = mock_metric
        mock_ar_cls.return_value = mock_metric
        mock_as_cls.return_value = MagicMock()

        result = await eval_runner.run_single_test(
            fake_graph, "hr", "q", "a"
        )
        assert result["actual_answer"] == "List answer"
