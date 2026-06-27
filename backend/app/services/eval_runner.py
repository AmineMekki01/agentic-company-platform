"""Agent evaluation runner using Ragas metrics."""

import logging
import sys
import time
import uuid
from types import ModuleType
from typing import Any

if "langchain_community.chat_models.vertexai" not in sys.modules:
    _fake_vertexai = ModuleType("langchain_community.chat_models.vertexai")
    _fake_vertexai.ChatVertexAI = None
    sys.modules["langchain_community.chat_models.vertexai"] = _fake_vertexai

from langchain_core.messages import HumanMessage

from app.agents.llm import get_chat_model
from app.agents.runtime import AgentRuntime
from app.core.config import settings

logger = logging.getLogger(__name__)


def _get_ragas_llm():
    from ragas.llms import LangchainLLMWrapper
    return LangchainLLMWrapper(get_chat_model("gpt-4o-mini", temperature=0.0))


def _get_ragas_embeddings():
    from langchain_openai import OpenAIEmbeddings
    from ragas.embeddings import LangchainEmbeddingsWrapper

    return LangchainEmbeddingsWrapper(
        OpenAIEmbeddings(api_key=settings.openai_api_key or None)
    )


async def run_single_test(
    runtime: AgentRuntime,
    agent_slug: str,
    question: str,
    expected_answer: str,
) -> dict[str, Any]:
    """
    Run a single evaluation test against the live agent graph.

    Returns a dict with:
    - actual_answer: str
    - retrieved_contexts: list[str]
    - metrics: dict[str, float]
    - score: float (mean of metrics)
    - duration_ms: int
    """
    start_ms = int(time.time() * 1000)

    thread_id = f"eval-{uuid.uuid4()}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {"messages": [HumanMessage(content=question)], "forced_agent": agent_slug}
    final_state = await runtime.graph.ainvoke(initial_state, config)

    duration_ms = int(time.time() * 1000) - start_ms

    messages = final_state.get("messages", [])
    actual_answer = ""
    for msg in reversed(messages):
        role = getattr(msg, "type", None) or getattr(msg, "role", None)
        if role in ("ai", "assistant"):
            content = getattr(msg, "content", "")
            if isinstance(content, str):
                actual_answer = content
            elif isinstance(content, list):
                actual_answer = "".join(
                    part.get("text", "")
                    for part in content
                    if isinstance(part, dict) and part.get("type") == "text"
                )
            break

    retrieved_contexts: list[str] = []
    for msg in messages:
        if getattr(msg, "name", None) == "retrieve":
            content = getattr(msg, "content", "") or ""
            if content:
                retrieved_contexts.append(str(content))
                logger.debug("Retrieved context from tool msg: %d chars", len(content))

    if not retrieved_contexts:
        sources = final_state.get("sources", []) or []
        for src in sources:
            if isinstance(src, dict):
                chunk = src.get("chunk_text") or src.get("text", "")
                if chunk:
                    retrieved_contexts.append(str(chunk))
            else:
                text = getattr(src, "chunk_text", None) or getattr(src, "text", "")
                if text:
                    retrieved_contexts.append(str(text))

    logger.info(
        "Eval contexts: count=%d, chars=%s",
        len(retrieved_contexts),
        [len(c) for c in retrieved_contexts],
    )

    from ragas.dataset_schema import SingleTurnSample
    from ragas.metrics import AnswerCorrectness, AnswerRelevancy, Faithfulness

    llm = _get_ragas_llm()
    embeddings = _get_ragas_embeddings()

    sample = SingleTurnSample(
        user_input=question,
        response=actual_answer,
        reference=expected_answer,
        retrieved_contexts=retrieved_contexts,
    )

    metrics: dict[str, float] = {}
    try:
        from ragas.metrics._answer_similarity import AnswerSimilarity
        answer_similarity = AnswerSimilarity(embeddings=embeddings)
        ac = AnswerCorrectness(llm=llm, answer_similarity=answer_similarity)
        metrics["answer_correctness"] = float(await ac.single_turn_ascore(sample) or 0.0)
    except Exception:
        logger.exception("AnswerCorrectness failed")
        metrics["answer_correctness"] = 0.0

    try:
        ar = AnswerRelevancy(llm=llm, embeddings=embeddings)
        metrics["answer_relevancy"] = float(await ar.single_turn_ascore(sample) or 0.0)
    except Exception:
        logger.exception("AnswerRelevancy failed")
        metrics["answer_relevancy"] = 0.0

    if retrieved_contexts:
        try:
            f = Faithfulness(llm=llm)
            metrics["faithfulness"] = float(await f.single_turn_ascore(sample) or 0.0)
        except Exception:
            logger.exception("Faithfulness failed")
            metrics["faithfulness"] = 0.0
    else:
        logger.info("No retrieved contexts, skipping Faithfulness")

    score = round(sum(metrics.values()) / len(metrics), 3) if metrics else 0.0

    return {
        "actual_answer": actual_answer,
        "retrieved_contexts": retrieved_contexts,
        "metrics": metrics,
        "score": score,
        "duration_ms": duration_ms,
    }
