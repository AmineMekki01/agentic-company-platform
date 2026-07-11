"""Agent emotion service: decay math, momentum updates, LLM extraction, episode creation.
Emotions are the AGENT'S feelings toward a user (not the user's emotions).
8 Plutchik dimensions: joy, trust, fear, surprise, sadness, disgust, anger, anticipation.
"""

import json
import logging
import math
from datetime import UTC, datetime

from langchain_core.messages import SystemMessage
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.llm import get_chat_model
from app.models.agent_emotion_state import AgentEmotionState
from app.models.agent_episode import AgentEpisode

logger = logging.getLogger(__name__)

EMOTION_DIMENSIONS = [
    "joy", "trust", "fear", "surprise",
    "sadness", "disgust", "anger", "anticipation",
]

DECAY_RATES: dict[str, float] = {
    "anger": 0.30,
    "fear": 0.30,
    "surprise": 0.40,
    "sadness": 0.10,
    "joy": 0.10,
    "disgust": 0.15,
    "trust": 0.03,
    "anticipation": 0.03,
}

MOMENTUM = 0.7
SPIKE_WEIGHT = 0.4
BASELINE_LEARNING_RATE = 0.02
EPISODE_THRESHOLD = 0.75


NEGATIVE_EMOTION_DIMENSIONS = ["fear", "sadness", "disgust", "anger"]

EMOTION_DEVIATION_THRESHOLD = 0.15
DOMINANT_EMOTION_DEVIATION_THRESHOLD = 0.2

_TONE_HINTS: dict[str, str] = {
    "anger": "be calming and direct, don't take it personally",
    "joy": "be enthusiastic and warm, share their excitement",
    "trust": "be open and collaborative, you can be more casual",
    "fear": "be reassuring and clear, reduce uncertainty",
    "surprise": "be attentive, this is unexpected, explore it",
    "sadness": "be gentle and empathetic, acknowledge difficulty",
    "disgust": "be professional, address what's causing the reaction",
    "anticipation": "be forward-looking, build on their momentum",
}

USER_AFFECT_LABELS = [
    "neutral", "happy", "frustrated", "confused",
    "anxious", "urgent", "grateful", "annoyed", "sad",
]

_USER_AFFECT_TONE_HINTS: dict[str, str] = {
    "frustrated": "be calm, direct, and solution-focused - don't over-explain or sound defensive",
    "confused": "slow down, use simpler language, check understanding before moving on",
    "anxious": "be reassuring and concrete, reduce ambiguity",
    "urgent": "be brief, lead with the actionable answer",
    "annoyed": "be efficient and take their concern seriously, avoid a chipper tone",
    "sad": "be gentle and warm, don't rush past it",
    "grateful": "accept warmly, keep it light",
    "happy": "match their energy, be warm",
}

_AFFECT_INTENSITY_THRESHOLD = 0.35


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _apply_decay(current: float, baseline: float, decay_rate: float, hours: float) -> float:
    if hours <= 0:
        return current
    return baseline + (current - baseline) * math.exp(-decay_rate * hours)


def _momentum_update(
    decayed: float, extracted: float, momentum: float = MOMENTUM, spike_weight: float = SPIKE_WEIGHT
) -> float:
    return _clamp(decayed * momentum + extracted * spike_weight)


def _hours_since(dt: datetime) -> float:
    if dt is None:
        return 0.0
    now = datetime.now(UTC)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return max(0.0, (now - dt).total_seconds() / 3600.0)


async def extract_emotions(user_message: str, agent_response: str) -> dict[str, float] | None:
    """Use a small LLM to evaluate how the AGENT would feel toward the user after this exchange.

    Returns None on failure (not a zero dict) - a failed extraction carries no
    signal about how the agent felt, and must not be treated as "felt nothing".
    """
    prompt = (
        "You are an emotion analysis engine. Based on the following interaction between a user and an AI assistant, "
        "evaluate how the AI ASSISTANT would feel toward this user. Rate each emotion 0.0 to 1.0.\n\n"
        "Emotions: joy, trust, fear, surprise, sadness, disgust, anger, anticipation\n\n"
        "Guidelines:\n"
        "- joy: how much the assistant enjoyed helping this user\n"
        "- trust: how much the assistant trusts this user (follows advice, is honest)\n"
        "- fear: how much the assistant worries about this user's situation\n"
        "- surprise: how unexpected the interaction was\n"
        "- sadness: how much the interaction made the assistant feel down\n"
        "- disgust: how much the user's behavior was off-putting\n"
        "- anger: how frustrated the assistant feels toward this user\n"
        "- anticipation: how much the assistant looks forward to future interactions\n\n"
        f"User message: {user_message[:500]}\n"
        f"Assistant response: {agent_response[:500]}\n\n"
        "Return ONLY a JSON object with the 8 emotion names as keys and float values 0.0-1.0. No other text."
    )
    try:
        llm = get_chat_model("gpt-5.4-nano", temperature=0.1)
        response = await llm.ainvoke([SystemMessage(content=prompt)])
        text = str(getattr(response, "content", response)).strip()
        parsed = json.loads(text)
        result = {}
        for dim in EMOTION_DIMENSIONS:
            val = parsed.get(dim, 0.0)
            try:
                result[dim] = _clamp(float(val))
            except (TypeError, ValueError):
                result[dim] = 0.0
        return result
    except Exception:
        logger.debug("Emotion extraction failed", exc_info=True)
        return None


async def get_emotion_state(
    session: AsyncSession, user_id: str, agent_slug: str, for_update: bool = False
) -> AgentEmotionState | None:
    """Fetch the emotion row for a user/agent.

    Pass for_update=True only from a write path (see update_emotion_state):
    it takes a row lock so concurrent background tasks updating the same
    (user, agent) row serialize at the DB level instead of racing on a
    read-modify-write. The pre-node's read-only context fetch should not
    lock, since no write follows it.
    """
    stmt = (
        select(AgentEmotionState)
        .where(AgentEmotionState.user_id == user_id)
        .where(AgentEmotionState.agent_slug == agent_slug)
    )
    if for_update:
        stmt = stmt.with_for_update()
    result = await session.scalar(stmt)
    return result


async def update_emotion_state(
    session: AsyncSession,
    user_id: str,
    agent_slug: str,
    extracted_emotions: dict[str, float] | None,
) -> AgentEmotionState:
    state = await get_emotion_state(session, user_id, agent_slug, for_update=True)

    if state is None:
        state = AgentEmotionState(
            user_id=user_id,
            agent_slug=agent_slug,
        )
        session.add(state)
        await session.flush()

    hours = _hours_since(state.last_interaction_at)

    if extracted_emotions is None:
        logger.warning(
            "Emotion extraction unavailable, applying decay only: agent=%s user=%s",
            agent_slug, user_id,
        )
        for dim in EMOTION_DIMENSIONS:
            current = getattr(state, dim)
            baseline = getattr(state, f"{dim}_baseline")
            decayed = _apply_decay(current, baseline, DECAY_RATES[dim], hours)
            setattr(state, dim, decayed)
    else:
        for dim in EMOTION_DIMENSIONS:
            current = getattr(state, dim)
            baseline = getattr(state, f"{dim}_baseline")
            decayed = _apply_decay(current, baseline, DECAY_RATES[dim], hours)
            updated = _momentum_update(decayed, extracted_emotions.get(dim, 0.0))
            setattr(state, dim, updated)

            new_baseline = baseline * (1 - BASELINE_LEARNING_RATE) + updated * BASELINE_LEARNING_RATE
            setattr(state, f"{dim}_baseline", new_baseline)

    state.last_interaction_at = datetime.now(UTC)
    state.updated_at = datetime.now(UTC)
    await session.flush()
    return state


async def maybe_create_episode(
    session: AsyncSession,
    user_id: str,
    agent_slug: str,
    conversation_id: str,
    emotion_state: AgentEmotionState,
    extracted_emotions: dict[str, float],
    user_message: str,
    agent_response: str,
) -> AgentEpisode | None:
    """Record a rupture episode if this exchange was a genuinely bad moment for
    the agent - only the negative dimensions count (see NEGATIVE_EMOTION_DIMENSIONS).
    A positive spike (pure joy/trust/anticipation) never creates one.
    """
    max_intensity = max(extracted_emotions.get(dim, 0.0) for dim in NEGATIVE_EMOTION_DIMENSIONS)
    if max_intensity < EPISODE_THRESHOLD:
        return None

    trigger = "high_emotion"
    dominant = max(NEGATIVE_EMOTION_DIMENSIONS, key=lambda d: extracted_emotions.get(d, 0.0))

    summary = f"High {dominant} ({extracted_emotions[dominant]:.2f}) during interaction: {user_message[:200]}"

    snapshot = {dim: getattr(emotion_state, dim) for dim in EMOTION_DIMENSIONS}

    episode = AgentEpisode(
        user_id=user_id,
        agent_slug=agent_slug,
        conversation_id=conversation_id,
        summary=summary,
        emotion_snapshot=snapshot,
        significance_score=max_intensity,
        trigger=trigger,
    )
    session.add(episode)
    await session.flush()
    logger.info("Episode created: agent=%s user=%s trigger=%s intensity=%.2f", agent_slug, user_id, trigger, max_intensity)
    return episode


async def get_significant_episodes(
    session: AsyncSession, user_id: str, agent_slug: str, limit: int = 2
) -> list[AgentEpisode]:
    """Return the most significant past episodes for this user/agent."""
    result = await session.scalars(
        select(AgentEpisode)
        .where(AgentEpisode.user_id == user_id)
        .where(AgentEpisode.agent_slug == agent_slug)
        .order_by(desc(AgentEpisode.significance_score), desc(AgentEpisode.created_at))
        .limit(limit)
    )
    return list(result.all())


def format_episode_context(episodes: list[AgentEpisode]) -> str:
    if not episodes:
        return ""

    lines = [
        "## Moments You Remember",
        "Past exchanges that stood out. Reference them only if genuinely relevant - "
        "don't force it into an unrelated conversation.",
    ]
    for ep in episodes:
        lines.append(f"- {ep.summary}")

    return "\n".join(lines)


def format_emotion_context(emotion_state: AgentEmotionState | None) -> str:
    """Surface only emotions that have actually shifted from their resting
    baseline - not whatever happens to be nonzero. Several dimensions default
    to a warm resting baseline (joy/trust/anticipation = 0.3), and one
    momentum-blended turn is enough to clear a flat 0.2 floor regardless of
    what happened in the exchange. Gating on deviation from baseline instead
    means a brand-new, perfectly neutral conversation produces no emotional
    context at all.
    """
    if emotion_state is None:
        return ""

    shifted: list[tuple[str, float, float]] = []
    for dim in EMOTION_DIMENSIONS:
        val = getattr(emotion_state, dim, 0.0)
        baseline = getattr(emotion_state, f"{dim}_baseline", 0.0)
        deviation = val - baseline
        if abs(deviation) >= EMOTION_DEVIATION_THRESHOLD:
            shifted.append((dim, val, deviation))

    if not shifted:
        return ""

    dominant, dominant_val, dominant_deviation = max(shifted, key=lambda item: abs(item[2]))
    if abs(dominant_deviation) < DOMINANT_EMOTION_DEVIATION_THRESHOLD:
        return ""

    high_emotions = [f"- {dim.capitalize()}: {val:.2f}" for dim, val, _ in shifted]
    tone_hint = _TONE_HINTS.get(dominant, "adapt naturally")

    lines = [
        "## Your Emotional State Toward This User",
        *high_emotions,
        "",
        f"Dominant emotion: {dominant} ({dominant_val:.2f}) - {tone_hint}.",
        "Let this naturally influence your tone without explicitly mentioning your emotions.",
    ]
    return "\n".join(lines)


async def detect_user_affect(user_message: str) -> dict:
    """Read the emotional/mental state behind the user's latest message (theory of mind),
    and whether it's asking the assistant to recall a specific past exchange.

    Unlike extract_emotions (which asks how the AGENT feels), this asks what the
    USER seems to be feeling right now, so the reply can be tonally attuned to them -
    the more useful signal for actually sounding human. The recall flag rides along
    on this same call (rather than a dedicated one) since it's already made every
    turn - one more classification on the same message costs nothing extra.
    """
    if not user_message or not user_message.strip():
        return {"label": "neutral", "intensity": 0.0, "is_recall_query": False}

    prompt = (
        "Read the emotional/mental state behind this message from a user talking to an AI assistant.\n\n"
        f"Message: {user_message[:800]}\n\n"
        f"Pick the single best-fitting label from: {USER_AFFECT_LABELS}.\n"
        "Rate intensity 0.0-1.0 (0.0 = no real signal, just neutral/informational; 1.0 = very strong).\n"
        "Err toward 'neutral' with low intensity for ordinary informational messages.\n\n"
        "Also classify: is this message asking the assistant to recall a SPECIFIC past "
        "exchange or resolved issue (e.g. 'do you remember when we...', 'what did we do "
        "about...', 'how did we fix...')? Not a general question, an actual look-back.\n\n"
        'Return ONLY JSON: {"label": "...", "intensity": 0.0, "is_recall_query": false}'
    )
    try:
        llm = get_chat_model("gpt-5.4-nano", temperature=0.0)
        response = await llm.ainvoke([SystemMessage(content=prompt)])
        text = str(getattr(response, "content", response)).strip()
        parsed = json.loads(text)
        label = str(parsed.get("label", "neutral")).lower()
        if label not in USER_AFFECT_LABELS:
            label = "neutral"
        intensity = _clamp(float(parsed.get("intensity", 0.0)))
        is_recall_query = bool(parsed.get("is_recall_query", False))
        return {"label": label, "intensity": intensity, "is_recall_query": is_recall_query}
    except Exception:
        logger.debug("User affect detection failed", exc_info=True)
        return {"label": "neutral", "intensity": 0.0, "is_recall_query": False}


def format_user_affect_context(affect: dict | None) -> str:
    if not affect:
        return ""
    label = affect.get("label", "neutral")
    intensity = affect.get("intensity", 0.0)
    if label == "neutral" or intensity < _AFFECT_INTENSITY_THRESHOLD:
        return ""

    hint = _USER_AFFECT_TONE_HINTS.get(label, "adapt naturally")
    lines = [
        "## How The User Seems Right Now",
        f"Their latest message reads as {label} (confidence {intensity:.2f}). {hint[0].upper()}{hint[1:]}.",
        "This is a read of their current message, not a permanent label - stay natural and "
        "don't mention that you're analyzing their tone.",
    ]
    return "\n".join(lines)
