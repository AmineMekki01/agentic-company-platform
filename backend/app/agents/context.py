"""Adaptive token budget management.
"""

from dataclasses import dataclass
from typing import Literal

from langchain_core.messages import BaseMessage, trim_messages

MODEL_CONTEXT_WINDOWS: dict[str, int] = {
    # OpenAI
    "gpt-5.5": 1_050_000,
    "gpt-5.4": 1_050_000,
    "gpt-5.4-mini": 400_000,
    "gpt-5.4-nano": 400_000,
    # Anthropic
    # Google
    # Local LLMs

    # will add this afer 


    "default": 128_000,
}


def resolve_context_window(model_name: str) -> int:
    """
    Look up a model's context window. Falls back to default.

    Args:
        model_name: The name of the model to look up.

    Returns:
        The context window size for the model, or the default if not found.
    """
    key = model_name.lower().replace("-", "").replace(".", "")
    for known, limit in MODEL_CONTEXT_WINDOWS.items():
        if known.lower().replace("-", "").replace(".", "") in key:
            return limit
    return MODEL_CONTEXT_WINDOWS["default"]


@dataclass(frozen=True)
class BudgetProfile:
    """
    A reusable allocation strategy.
    
    This class defines how to allocate the context window for different parts of the agent.
    """

    max_retrieval_ratio: float = 0.25
    response_reserve_ratio: float = 0.15
    max_system_ratio: float = 0.05
    max_history_ratio: float = 0.55
    min_history_tokens: int = 800
    retrieval_enabled: bool = True
    subgraph_depth: Literal["single", "multi"] = "single"

    def effective_limits(self, context_window: int) -> dict[str, int]:
        """
        Convert ratios to absolute token ceilings for a given model.
        
        Args:
            context_window: The total context window size for the model.
            
        Returns:
            A dictionary containing the effective limits for each component.
        """
        return {
            "retrieval": int(context_window * self.max_retrieval_ratio),
            "response": int(context_window * self.response_reserve_ratio),
            "system": int(context_window * self.max_system_ratio),
            "history": int(context_window * self.max_history_ratio),
            "window": context_window,
        }

    def history_budget_after(
        self,
        context_window: int,
        system_tokens: int,
        retrieval_tokens: int,
    ) -> int:
        """
        Compute how many tokens are left for history after we know
        the real sizes of system prompt and retrieved context.
        
        Args:
            context_window: The total context window size for the model.
            system_tokens: The number of tokens in the system prompt.
            retrieval_tokens: The number of tokens in the retrieved context.
            
        Returns:
            The number of tokens available for history.
        """
        limits = self.effective_limits(context_window)
        remaining = (
            context_window
            - system_tokens
            - retrieval_tokens
            - limits["response"]
        )
        return max(self.min_history_tokens, min(remaining, limits["history"]))


# presets for the UI modes
PROFILE_AUTO = BudgetProfile()
PROFILE_QUICK = BudgetProfile(
    max_retrieval_ratio=0.10,
    response_reserve_ratio=0.10,
    max_historyx_ratio=0.30,
    min_history_tokens=400,
    retrieval_enabled=True,
    subgraph_depth="single",
)
PROFILE_MID = BudgetProfile(
    max_retrieval_ratio=0.20,
    response_reserve_ratio=0.15,
    max_history_ratio=0.50,
    min_history_tokens=600,
    retrieval_enabled=True,
    subgraph_depth="single",
)
PROFILE_DEEP = BudgetProfile(
    max_retrieval_ratio=0.30,
    response_reserve_ratio=0.20,
    max_history_ratio=0.40,
    min_history_tokens=1_200,
    retrieval_enabled=True,
    subgraph_depth="multi",
)

MODE_PROFILES: dict[str, BudgetProfile] = {
    "auto": PROFILE_AUTO,
    "quick": PROFILE_QUICK,
    "mid": PROFILE_MID,
    "deep": PROFILE_DEEP,
}


_DEEP_SIGNALS: dict[str, float] = {
    "root cause": 3.0,
    "deep dive": 2.5,
    "trade-off": 2.0,
    "tradeoff": 2.0,
    "pros and cons": 2.0,
    "compare and contrast": 2.0,
    "architecture": 1.5,
    "design pattern": 1.5,
    "analyze": 1.5,
    "analysis": 1.5,
    "evaluate": 1.5,
    "assess": 1.5,
    "investigate": 1.5,
    "research": 1.5,
    "strategy": 1.5,
    "plan": 1.0,
    "recommend": 1.5,
    "suggest": 1.0,
    "best approach": 1.5,
    "optimal": 1.5,
    "alternative": 1.0,
    "impact": 1.0,
    "implications": 1.5,
    "complex": 1.0,
    "complicated": 1.0,
    "review": 1.0,
    "audit": 1.5,
    "debug": 1.5,
    "refactor": 1.5,
    "performance": 1.0,
    "optimization": 1.5,
    "why": 1.0,
    "cause": 1.0,
    "how does": 1.0,
    "how to": 0.5,
    "explain": 1.0,
    "elaborate": 1.5,
    "difference between": 1.5,
    "vs": 0.5,
    "versus": 0.5,
}

_QUICK_SIGNALS: dict[str, float] = {
    "quick": 1.5,
    "brief": 1.5,
    "short": 1.0,
    "fast": 1.0,
    "summary": 1.0,
    "tl;dr": 2.0,
    "what is": 1.0,
    "what's": 1.0,
    "who": 0.5,
    "when": 0.5,
    "where": 0.5,
    "which": 0.5,
    "hello": 2.0,
    "hi": 2.0,
    "hey": 2.0,
    "thanks": 1.0,
    "thank you": 1.0,
    "ok": 1.0,
    "yes": 1.0,
    "no": 1.0,
    "goodbye": 1.0,
    "bye": 1.0,
}

_INTERROGATIVE_DEEP = {"why", "how", "what if", "explain", "elaborate", "describe in detail"}
_INTERROGATIVE_QUICK = {"who", "when", "where", "what is", "what's", "which", "is there", "are there"}

_CONJUNCTIONS = (" and ", " but ", " or ", " however ", " therefore ", " because ", " although ", " whereas ", " while ", " moreover ", " furthermore ")
_CONDITIONALS = (" if ", " unless ", " assuming ", " provided that ", " given that ")


def auto_select_mode(query: str) -> str:
    """
    Advanced heuristic to select quick/mid/deep mode from a user query.

    Uses weighted lexical signals, question-type classification, syntactic
    complexity metrics, and code/technical markers. No LLM call - purely
    rule-based scoring with continuous thresholds.
    """
    q = query.lower().strip()
    words = q.split()
    word_count = len(words)

    deep_score = sum(w for kw, w in _DEEP_SIGNALS.items() if kw in q)
    quick_score = sum(w for kw, w in _QUICK_SIGNALS.items() if kw in q)

    question_deep = sum(1 for stem in _INTERROGATIVE_DEEP if q.startswith(stem) or f" {stem} " in q)
    question_quick = sum(1 for stem in _INTERROGATIVE_QUICK if q.startswith(stem) or f" {stem} " in q)

    conjunction_count = sum(q.count(c) for c in _CONJUNCTIONS)
    conditional_count = sum(q.count(c) for c in _CONDITIONALS)
    clause_markers = q.count(",") + q.count(";") + q.count(":")

    question_marks = q.count("?")
    sentence_count = q.count(".") + q.count("!") + q.count(";") + 1
    has_multi_part = question_marks >= 2 or sentence_count >= 3

    has_code = "`" in q or "```" in q
    tech_terms = {"implement", "debug", "refactor", "algorithm", "database", "api", "endpoint", "microservice", "container", "kubernetes", "docker"}
    tech_score = sum(1 for term in tech_terms if term in q)

    complexity = (
        deep_score * 2.0
        - quick_score * 1.5
        + question_deep * 1.5
        - question_quick * 0.5
        + conjunction_count * 0.8
        + conditional_count * 1.2
        + clause_markers * 0.3
        + (3.0 if has_multi_part else 0.0)
        + (2.5 if has_code else 0.0)
        + tech_score * 1.0
    )

    if word_count <= 6:
        complexity -= 2.5
    elif word_count <= 12:
        complexity -= 1.0
    elif word_count > 50:
        complexity += 3.0
    elif word_count > 30:
        complexity += 1.5

    if quick_score >= 2.5 and word_count < 20 and not has_multi_part:
        return "quick"
    if deep_score >= 4.0 or (has_code and word_count > 15) or (has_multi_part and word_count > 30):
        return "deep"

    if complexity <= 1.5:
        return "quick"
    if complexity <= 4.5:
        return "mid"
    return "deep"


def get_mode_profile(mode: str | None) -> BudgetProfile:
    return MODE_PROFILES.get(mode or "auto", PROFILE_AUTO)


def clamp_retrieval_context(raw_context: str, retrieval_budget: int) -> str:
    """Clamp retrieved context to a character budget derived from token budget."""
    if not raw_context:
        return ""
    char_budget = retrieval_budget * 4
    if len(raw_context) <= char_budget:
        return raw_context

    lines = raw_context.split("\n\n---\n\n")
    kept: list[str] = []
    kept_chars = 0
    for line in lines:
        if kept_chars + len(line) > char_budget:
            break
        kept.append(line)
        kept_chars += len(line)
    return "\n\n---\n\n".join(kept) + "\n\n[Additional sources omitted]"


def trim_history(
    history: list[BaseMessage],
    history_budget: int,
    llm,
) -> list[BaseMessage]:
    """Keep the most recent complete turns that fit the budget."""
    if history_budget <= 0:
        for m in reversed(history):
            if getattr(m, "type", None) == "human":
                return [m]
        return []

    return trim_messages(
        history,
        max_tokens=history_budget,
        strategy="last",
        token_counter=lambda msgs: sum(
            llm.get_num_tokens(m.content or "") for m in msgs
        ),
        allow_partial=False,
    )
