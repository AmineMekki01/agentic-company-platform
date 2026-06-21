"""Static model pricing lookup for cost estimation (USD per 1K tokens)."""

_MODEL_PRICING: dict[str, tuple[float, float]] = {
    # (input_per_1k, output_per_1k)
    "gpt-5.5": (0.005, 0.03),
    "gpt-5.4": (0.0025, 0.015),
    "gpt-5.4-mini": (0.00075, 0.0045),
    "gpt-5.4-nano": (0.0002, 0.0015),
}


def _lookup_pricing(model: str) -> tuple[float, float]:
    """Look up pricing by exact match, then by prefix. Raises if unknown."""
    if model in _MODEL_PRICING:
        return _MODEL_PRICING[model]
    for key, val in _MODEL_PRICING.items():
        if model.startswith(key):
            return val
    raise ValueError(f"Unknown model '{model}' — no pricing configured")


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for a single LLM call.

    Args:
        model: Model name (e.g. "gpt-5.4-nano")
        input_tokens: Number of input/prompt tokens
        output_tokens: Number of output/completion tokens

    Returns:
        Estimated cost in USD
    """
    pricing = _lookup_pricing(model)
    cost = (input_tokens / 1000.0) * pricing[0] + (output_tokens / 1000.0) * pricing[1]
    return round(cost, 6)
