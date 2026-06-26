"""Tests for agent context module."""

import pytest

from app.agents.context import (
    MODEL_CONTEXT_WINDOWS,
    BudgetProfile,
    auto_select_mode,
    clamp_retrieval_context,
    get_mode_profile,
    resolve_context_window,
    trim_history,
)



def test_resolve_context_window_known():
    assert resolve_context_window("gpt-5.4") == MODEL_CONTEXT_WINDOWS["gpt-5.4"]


def test_resolve_context_window_case_insensitive():
    assert resolve_context_window("GPT-5.4") == MODEL_CONTEXT_WINDOWS["gpt-5.4"]


def test_resolve_context_window_unknown_raises():
    with pytest.raises(ValueError, match="Unknown model"):
        resolve_context_window("nonexistent-model-xyz")


def test_budget_profile_effective_limits():
    profile = BudgetProfile(
        max_retrieval_ratio=0.25,
        response_reserve_ratio=0.15,
        max_system_ratio=0.05,
        max_history_ratio=0.55,
    )
    limits = profile.effective_limits(100000)
    assert limits["retrieval"] == int(100000 * 0.25)
    assert limits["response"] == int(100000 * 0.15)
    assert limits["system"] == int(100000 * 0.05)
    assert limits["history"] == int(100000 * 0.55)
    assert limits["window"] == 100000


def test_budget_profile_history_budget_after():
    profile = BudgetProfile(
        max_retrieval_ratio=0.25,
        response_reserve_ratio=0.15,
        max_system_ratio=0.05,
        max_history_ratio=0.55,
        min_history_tokens=800,
    )
    result = profile.history_budget_after(100000, system_tokens=1000, retrieval_tokens=5000)
    assert result > 0
    assert result <= int(100000 * 0.55)


def test_auto_select_mode_quick():
    assert auto_select_mode("hi") == "quick"


def test_auto_select_mode_deep():
    result = auto_select_mode("Analyze and explain in detail `code.py` the algorithm implementation and why it works")
    assert result == "deep"


def test_auto_select_mode_mid():
    result = auto_select_mode("What is the company policy on remote work and how does it compare to industry standards?")
    assert result in ("mid", "deep")


def test_auto_select_mode_short_question():
    assert auto_select_mode("what is PTO") == "quick"


def test_get_mode_profile_auto():
    profile = get_mode_profile(None)
    assert profile is not None
    assert profile.max_history_ratio == 0.55


def test_get_mode_profile_invalid():
    profile = get_mode_profile("invalid")
    assert profile is not None
    assert profile.max_history_ratio == 0.55


def test_clamp_retrieval_context_under_budget():
    text = "short text"
    assert clamp_retrieval_context(text, 100) == "short text"


def test_clamp_retrieval_context_over_budget():
    text = "\n\n---\n\n".join([f"Line {i}" for i in range(100)])
    result = clamp_retrieval_context(text, 1)
    assert "[Additional sources omitted]" in result


def test_clamp_retrieval_context_empty():
    assert clamp_retrieval_context("", 100) == ""


def test_trim_history_fits():
    from langchain_core.messages import HumanMessage, AIMessage
    history = [HumanMessage(content="hi"), AIMessage(content="hello")]
    result = trim_history(history, 1000, type("FakeLLM", (), {"get_num_tokens": lambda self, s: 1})())
    assert len(result) == 2


def test_trim_history_trims():
    from langchain_core.messages import HumanMessage, AIMessage
    history = [HumanMessage(content="msg"), AIMessage(content="reply")] * 50
    result = trim_history(history, 10, type("FakeLLM", (), {"get_num_tokens": lambda self, s: 1})())
    assert len(result) <= 10
