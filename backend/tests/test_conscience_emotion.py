"""Tests for the emotion service: clamp, decay, momentum, formatting, extraction."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.emotion import (
    DECAY_RATES,
    EMOTION_DIMENSIONS,
    MOMENTUM,
    SPIKE_WEIGHT,
    _apply_decay,
    _clamp,
    _momentum_update,
    format_emotion_context,
)


def test_emotion_dimensions_count():
    assert len(EMOTION_DIMENSIONS) == 8
    assert set(EMOTION_DIMENSIONS) == {
        "joy", "trust", "fear", "surprise",
        "sadness", "disgust", "anger", "anticipation",
    }


def test_clamp():
    assert _clamp(0.5) == 0.5
    assert _clamp(-0.1) == 0.0
    assert _clamp(1.5) == 1.0
    assert _clamp(0.0) == 0.0
    assert _clamp(1.0) == 1.0


def test_apply_decay_no_time():
    assert _apply_decay(0.8, 0.3, 0.1, 0.0) == 0.8


def test_apply_decay_toward_baseline():
    result = _apply_decay(0.9, 0.3, 0.5, 10.0)
    assert result < 0.9
    assert result > 0.3


def test_apply_decay_long_time_approaches_baseline():
    result = _apply_decay(0.9, 0.3, 0.5, 1000.0)
    assert abs(result - 0.3) < 0.01


def test_decay_rates_volatile_faster_than_stable():
    assert DECAY_RATES["anger"] > DECAY_RATES["trust"]
    assert DECAY_RATES["surprise"] > DECAY_RATES["anticipation"]


def test_momentum_update_basic():
    result = _momentum_update(0.6, 0.8)
    expected = _clamp(0.6 * MOMENTUM + 0.8 * SPIKE_WEIGHT)
    assert abs(result - expected) < 1e-6


def test_momentum_update_clamps_high():
    result = _momentum_update(0.9, 1.0)
    assert result <= 1.0


def test_momentum_update_clamps_low():
    result = _momentum_update(0.1, 0.0)
    assert result >= 0.0


def test_format_emotion_context_empty_when_low():
    state = MagicMock()
    for dim in EMOTION_DIMENSIONS:
        setattr(state, dim, 0.05)
        setattr(state, f"{dim}_baseline", 0.05)
    assert format_emotion_context(state) == ""


def test_format_emotion_context_includes_high_emotions():
    state = MagicMock()
    for dim in EMOTION_DIMENSIONS:
        setattr(state, dim, 0.05)
        setattr(state, f"{dim}_baseline", 0.05)
    state.joy = 0.72
    state.joy_baseline = 0.3
    state.trust = 0.81
    state.trust_baseline = 0.3
    result = format_emotion_context(state)
    assert "Joy" in result
    assert "0.72" in result
    assert "Trust" in result
    assert "0.81" in result
    assert "Emotional State" in result


def test_format_emotion_context_none():
    assert format_emotion_context(None) == ""


def test_format_emotion_context_empty_when_at_resting_baseline_despite_absolute_value():
    """Regression test: joy/trust/anticipation default to a warm 0.3 baseline,
    so a flat 'val >= 0.2' rule used to fire on a brand-new, neutral
    conversation. Deviation-from-baseline must gate this instead."""
    state = MagicMock()
    for dim in EMOTION_DIMENSIONS:
        setattr(state, dim, 0.3)
        setattr(state, f"{dim}_baseline", 0.3)
    assert format_emotion_context(state) == ""


def test_format_emotion_context_empty_when_shift_below_dominant_bar():
    """A dimension can clear the per-emotion inclusion bar (0.15) yet still be
    too small to justify a tone directive (needs >= 0.2 to be "dominant")."""
    state = MagicMock()
    for dim in EMOTION_DIMENSIONS:
        setattr(state, dim, 0.1)
        setattr(state, f"{dim}_baseline", 0.1)
    state.joy = 0.26
    state.joy_baseline = 0.1
    assert format_emotion_context(state) == ""


def test_format_emotion_context_includes_when_shift_clears_dominant_bar():
    state = MagicMock()
    for dim in EMOTION_DIMENSIONS:
        setattr(state, dim, 0.1)
        setattr(state, f"{dim}_baseline", 0.1)
    state.anger = 0.35
    state.anger_baseline = 0.1
    result = format_emotion_context(state)
    assert "Anger" in result
    assert "Dominant emotion: anger" in result


def test_format_episode_context_empty():
    from app.services.emotion import format_episode_context
    assert format_episode_context([]) == ""


def test_format_episode_context_with_episodes():
    from app.services.emotion import format_episode_context

    ep = MagicMock()
    ep.summary = "High anger (0.90) during interaction: billing was wrong three times"
    result = format_episode_context([ep])
    assert "Moments You Remember" in result
    assert "billing was wrong three times" in result


@pytest.mark.asyncio
async def test_get_significant_episodes_orders_by_significance(session_factory, create_test_user):
    from app.models import Conversation
    from app.models.agent_episode import AgentEpisode
    from app.services.emotion import get_significant_episodes

    user = await create_test_user("episodeuser@example.com", "pass123")
    async with session_factory() as session:
        convo = Conversation(user_id=user.id)
        session.add(convo)
        await session.flush()

        session.add(AgentEpisode(
            user_id=user.id, agent_slug="chat", conversation_id=convo.id,
            summary="Minor thing", emotion_snapshot={}, significance_score=0.76,
        ))
        session.add(AgentEpisode(
            user_id=user.id, agent_slug="chat", conversation_id=convo.id,
            summary="Big emotional moment", emotion_snapshot={}, significance_score=0.95,
        ))
        await session.commit()

    async with session_factory() as session:
        episodes = await get_significant_episodes(session, user.id, "chat", limit=2)

    assert len(episodes) == 2
    assert episodes[0].summary == "Big emotional moment"


@pytest.mark.asyncio
async def test_extract_emotions_returns_all_dimensions():
    mock_response = MagicMock()
    mock_response.content = '{"joy": 0.8, "trust": 0.6, "fear": 0.1, "surprise": 0.2, "sadness": 0.05, "disgust": 0.0, "anger": 0.1, "anticipation": 0.7}'

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("app.services.emotion.get_chat_model", return_value=mock_llm):
        from app.services.emotion import extract_emotions
        result = await extract_emotions("Thanks so much!", "You're welcome!")

    assert set(result.keys()) == set(EMOTION_DIMENSIONS)
    assert result["joy"] == 0.8
    assert result["trust"] == 0.6
    for dim in EMOTION_DIMENSIONS:
        assert 0.0 <= result[dim] <= 1.0


@pytest.mark.asyncio
async def test_extract_emotions_failure_returns_none():
    with patch("app.services.emotion.get_chat_model", side_effect=Exception("LLM down")):
        from app.services.emotion import extract_emotions
        result = await extract_emotions("hi", "hello")

    assert result is None


@pytest.mark.asyncio
async def test_detect_user_affect_returns_label_and_intensity():
    mock_response = MagicMock()
    mock_response.content = '{"label": "frustrated", "intensity": 0.8}'

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("app.services.emotion.get_chat_model", return_value=mock_llm):
        from app.services.emotion import detect_user_affect
        result = await detect_user_affect("This still isn't working, third time I've asked!")

    assert result["label"] == "frustrated"
    assert result["intensity"] == 0.8


@pytest.mark.asyncio
async def test_detect_user_affect_empty_message_returns_neutral():
    from app.services.emotion import detect_user_affect
    result = await detect_user_affect("   ")
    assert result == {"label": "neutral", "intensity": 0.0, "is_recall_query": False}


@pytest.mark.asyncio
async def test_detect_user_affect_unknown_label_falls_back_to_neutral():
    mock_response = MagicMock()
    mock_response.content = '{"label": "ecstatic-supreme", "intensity": 0.9}'

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("app.services.emotion.get_chat_model", return_value=mock_llm):
        from app.services.emotion import detect_user_affect
        result = await detect_user_affect("whatever")

    assert result["label"] == "neutral"


@pytest.mark.asyncio
async def test_detect_user_affect_failure_returns_neutral():
    with patch("app.services.emotion.get_chat_model", side_effect=Exception("LLM down")):
        from app.services.emotion import detect_user_affect
        result = await detect_user_affect("hello")

    assert result == {"label": "neutral", "intensity": 0.0, "is_recall_query": False}


@pytest.mark.asyncio
async def test_detect_user_affect_flags_recall_query():
    mock_response = MagicMock()
    mock_response.content = '{"label": "neutral", "intensity": 0.1, "is_recall_query": true}'

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("app.services.emotion.get_chat_model", return_value=mock_llm):
        from app.services.emotion import detect_user_affect
        result = await detect_user_affect("Do you remember when we fixed the pod crash loop?")

    assert result["is_recall_query"] is True


@pytest.mark.asyncio
async def test_detect_user_affect_defaults_recall_query_false():
    mock_response = MagicMock()
    mock_response.content = '{"label": "happy", "intensity": 0.5}'

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("app.services.emotion.get_chat_model", return_value=mock_llm):
        from app.services.emotion import detect_user_affect
        result = await detect_user_affect("thanks!")

    assert result["is_recall_query"] is False


def test_format_user_affect_context_none():
    from app.services.emotion import format_user_affect_context
    assert format_user_affect_context(None) == ""


def test_format_user_affect_context_empty_for_neutral():
    from app.services.emotion import format_user_affect_context
    assert format_user_affect_context({"label": "neutral", "intensity": 0.9}) == ""


def test_format_user_affect_context_empty_below_threshold():
    from app.services.emotion import format_user_affect_context
    assert format_user_affect_context({"label": "frustrated", "intensity": 0.1}) == ""


def test_format_user_affect_context_includes_hint_above_threshold():
    from app.services.emotion import format_user_affect_context
    result = format_user_affect_context({"label": "frustrated", "intensity": 0.8})
    assert "frustrated" in result
    assert "0.80" in result
    assert "How The User Seems Right Now" in result


@pytest.mark.asyncio
async def test_update_emotion_state_none_applies_decay_only_no_momentum(session_factory, create_test_user):
    """When extraction fails (None), the state should only decay toward its
    existing baseline - no momentum blend, no baseline drift - not be treated
    as a zero-emotion turn."""
    from app.services.emotion import get_emotion_state, update_emotion_state

    user = await create_test_user("emotionnone@example.com", "pass123")

    async with session_factory() as session:
        state = await update_emotion_state(
            session, user.id, "chat", {"joy": 0.9, "trust": 0.8, "fear": 0.0,
                                        "surprise": 0.0, "sadness": 0.0, "disgust": 0.0,
                                        "anger": 0.0, "anticipation": 0.0},
        )
        await session.commit()
        joy_after_real_signal = state.joy
        baseline_after_real_signal = state.joy_baseline

    async with session_factory() as session:
        state = await get_emotion_state(session, user.id, "chat")
        state.last_interaction_at = state.last_interaction_at.replace(
            year=state.last_interaction_at.year - 1
        )
        await session.commit()

    async with session_factory() as session:
        state = await update_emotion_state(session, user.id, "chat", None)
        await session.commit()

        assert state.joy < joy_after_real_signal
        assert state.joy_baseline == baseline_after_real_signal


def _all_dims_zero(**overrides) -> dict:
    dims = {dim: 0.0 for dim in EMOTION_DIMENSIONS}
    dims.update(overrides)
    return dims


@pytest.mark.asyncio
async def test_maybe_create_episode_skips_pure_positive_spike(session_factory, create_test_user):
    """A joyful spike is a nice moment, not a rupture - it must not create an
    episode even though it clears the same numeric threshold a negative
    emotion would."""
    from app.models import Conversation
    from app.services.emotion import maybe_create_episode

    user = await create_test_user("positivespike@example.com", "pass123")
    async with session_factory() as session:
        convo = Conversation(user_id=user.id)
        session.add(convo)
        await session.flush()

        emotion_state = MagicMock()
        for dim in EMOTION_DIMENSIONS:
            setattr(emotion_state, dim, 0.1)

        episode = await maybe_create_episode(
            session, user.id, "chat", convo.id, emotion_state,
            _all_dims_zero(joy=0.95, trust=0.9),
            "Thank you so much, this made my day!", "You're very welcome!",
        )

    assert episode is None


@pytest.mark.asyncio
async def test_maybe_create_episode_creates_for_negative_spike(session_factory, create_test_user):
    from app.models import Conversation
    from app.services.emotion import maybe_create_episode

    user = await create_test_user("negativespike@example.com", "pass123")
    async with session_factory() as session:
        convo = Conversation(user_id=user.id)
        session.add(convo)
        await session.flush()

        emotion_state = MagicMock()
        for dim in EMOTION_DIMENSIONS:
            setattr(emotion_state, dim, 0.1)

        episode = await maybe_create_episode(
            session, user.id, "chat", convo.id, emotion_state,
            _all_dims_zero(anger=0.9, joy=0.95),
            "This is the third time you've gotten this wrong!", "I understand your frustration...",
        )
        await session.commit()

    assert episode is not None
    assert episode.trigger == "high_emotion"
    assert episode.significance_score == 0.9
    assert "Anger" in episode.summary or "anger" in episode.summary


@pytest.mark.asyncio
async def test_maybe_create_episode_dominant_ignores_higher_positive_dimension(session_factory, create_test_user):
    """Even when a positive dimension is numerically the highest overall, the
    episode's dominant/summary must be drawn from the negative dimensions only -
    it's describing what went wrong, not whatever happened to spike."""
    from app.models import Conversation
    from app.services.emotion import maybe_create_episode

    user = await create_test_user("mixedspike@example.com", "pass123")
    async with session_factory() as session:
        convo = Conversation(user_id=user.id)
        session.add(convo)
        await session.flush()

        emotion_state = MagicMock()
        for dim in EMOTION_DIMENSIONS:
            setattr(emotion_state, dim, 0.1)

        episode = await maybe_create_episode(
            session, user.id, "chat", convo.id, emotion_state,
            _all_dims_zero(joy=0.99, disgust=0.8),
            "Unbelievable, you broke it again.", "I'm sorry, let me fix this.",
        )
        await session.commit()

    assert episode is not None
    assert "disgust" in episode.summary.lower()
    assert episode.significance_score == 0.8
