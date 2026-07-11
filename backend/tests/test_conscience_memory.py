"""Tests for the memory service: CRUD, SQL retrieval, formatting, extraction."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.agent_memory import AgentMemory
from app.services.memory import _effective_importance, format_memory_context


def test_effective_importance_unchanged_when_just_accessed():
    now = datetime.now(UTC)
    memory = MagicMock(spec=AgentMemory)
    memory.importance_score = 0.8
    memory.access_count = 0
    memory.last_accessed_at = now
    assert _effective_importance(memory, now) == pytest.approx(0.8, abs=1e-6)


def test_effective_importance_decays_with_idle_time():
    now = datetime.now(UTC)
    memory = MagicMock(spec=AgentMemory)
    memory.importance_score = 0.8
    memory.access_count = 0
    memory.last_accessed_at = now - timedelta(days=100)
    result = _effective_importance(memory, now)
    assert 0.0 < result < 0.8


def test_effective_importance_more_idle_decays_more():
    now = datetime.now(UTC)
    memory_recent = MagicMock(spec=AgentMemory)
    memory_recent.importance_score = 0.8
    memory_recent.access_count = 0
    memory_recent.last_accessed_at = now - timedelta(days=10)

    memory_stale = MagicMock(spec=AgentMemory)
    memory_stale.importance_score = 0.8
    memory_stale.access_count = 0
    memory_stale.last_accessed_at = now - timedelta(days=200)

    assert _effective_importance(memory_stale, now) < _effective_importance(memory_recent, now)


def test_effective_importance_frequent_access_slows_decay():
    now = datetime.now(UTC)
    memory_unused = MagicMock(spec=AgentMemory)
    memory_unused.importance_score = 0.8
    memory_unused.access_count = 0
    memory_unused.last_accessed_at = now - timedelta(days=100)

    memory_frequently_accessed = MagicMock(spec=AgentMemory)
    memory_frequently_accessed.importance_score = 0.8
    memory_frequently_accessed.access_count = 20
    memory_frequently_accessed.last_accessed_at = now - timedelta(days=100)

    assert _effective_importance(memory_frequently_accessed, now) > _effective_importance(memory_unused, now)


def test_format_memory_context_empty():
    assert format_memory_context([]) == ""


def test_format_memory_context_with_memories():
    m1 = MagicMock(spec=AgentMemory)
    m1.content = "Prefers concise answers"
    m1.category = "preference"
    m1.importance_score = 0.8

    m2 = MagicMock(spec=AgentMemory)
    m2.content = "Works in finance"
    m2.category = "fact"
    m2.importance_score = 0.6

    result = format_memory_context([m1, m2])
    assert "What You Remember" in result
    assert "Prefers concise answers" in result
    assert "preference" in result
    assert "Works in finance" in result
    assert "fact" in result


def test_format_memory_context_tags_superseded_as_past():
    current = MagicMock(spec=AgentMemory)
    current.content = "Works at Meta"
    current.category = "fact"
    current.importance_score = 0.6
    current.status = "open"

    past = MagicMock(spec=AgentMemory)
    past.content = "Works at Google"
    past.category = "fact"
    past.importance_score = 0.6
    past.status = "superseded"

    result = format_memory_context([current, past])
    assert "- Works at Meta (fact, importance: 0.6)\n" in result
    assert "Works at Google (fact, importance: 0.6) [past, no longer current]" in result


def test_effective_importance_superseded_ranks_below_equal_importance_current():
    now = datetime.now(UTC)
    current = MagicMock(spec=AgentMemory)
    current.importance_score = 0.6
    current.access_count = 0
    current.last_accessed_at = now
    current.status = "open"

    past = MagicMock(spec=AgentMemory)
    past.importance_score = 0.6
    past.access_count = 0
    past.last_accessed_at = now
    past.status = "superseded"

    assert _effective_importance(past, now) < _effective_importance(current, now)


@pytest.mark.asyncio
async def test_create_memory(session_factory, create_test_user):
    from app.services.memory import create_memory, get_memories

    user = await create_test_user("memuser@example.com", "pass123")
    async with session_factory() as session:
        mem = await create_memory(
            session,
            user_id=user.id,
            agent_slug="chat",
            category="preference",
            content="Likes Python",
            importance=0.7,
            tags=["programming"],
        )
        await session.commit()

    async with session_factory() as session:
        memories = await get_memories(session, user.id, "chat")
        assert len(memories) == 1
        assert memories[0].content == "Likes Python"
        assert memories[0].category == "preference"
        assert memories[0].importance_score == 0.7


async def _make_conversation_and_messages(session_factory, user_id):
    """Create a real Conversation + user/assistant Message pair, mirroring what
    a normal chat turn persists, for provenance/hydration tests."""
    import uuid as uuid_module

    from app.models import Conversation, Message

    async with session_factory() as session:
        convo = Conversation(user_id=user_id)
        session.add(convo)
        await session.flush()

        user_msg = Message(
            id=uuid_module.uuid4(), conversation_id=convo.id, role="user",
            content="Do you remember when we fixed the Kubernetes pod crash loop?",
        )
        session.add(user_msg)
        await session.flush()

        assistant_msg = Message(
            id=uuid_module.uuid4(), conversation_id=convo.id, role="assistant",
            content="Yes - it was a misconfigured resource limit causing OOMKills.",
        )
        session.add(assistant_msg)
        await session.commit()

        return convo.id, user_msg.id, assistant_msg.id


@pytest.mark.asyncio
async def test_create_memory_stores_provenance(session_factory, create_test_user):
    from app.services.memory import create_memory, get_memories

    user = await create_test_user("provenanceuser@example.com", "pass123")
    convo_id, _, assistant_msg_id = await _make_conversation_and_messages(session_factory, user.id)

    async with session_factory() as session:
        await create_memory(
            session, user.id, "chat", "event", "Fixed a K8s pod crash loop", 0.7, [],
            conversation_id=convo_id, source_message_id=assistant_msg_id,
        )
        await session.commit()

    async with session_factory() as session:
        memories = await get_memories(session, user.id, "chat")
        assert memories[0].conversation_id == convo_id
        assert memories[0].source_message_id == assistant_msg_id


@pytest.mark.asyncio
async def test_consolidate_and_store_memory_updates_provenance_on_merge(session_factory, create_test_user):
    from app.services.memory import consolidate_and_store_memory, create_memory, get_memories

    user = await create_test_user("provenancemerge@example.com", "pass123")
    convo_id_1, _, assistant_msg_id_1 = await _make_conversation_and_messages(session_factory, user.id)
    convo_id_2, _, assistant_msg_id_2 = await _make_conversation_and_messages(session_factory, user.id)

    async with session_factory() as session:
        existing = await create_memory(
            session, user.id, "chat", "preference", "Prefers dark mode", 0.5, ["ui"],
            conversation_id=convo_id_1, source_message_id=assistant_msg_id_1,
        )
        await session.commit()
        existing_id = existing.id

    async with session_factory() as session:
        existing_row = await session.get(AgentMemory, existing_id)
        with patch(
            "app.services.memory._find_merge_candidate",
            AsyncMock(return_value=(existing_row, 0.97)),
        ), patch("app.services.memory._sync_memory_to_qdrant", AsyncMock(return_value="pt")):
            await consolidate_and_store_memory(
                session, user.id, "chat", "preference", "Strongly prefers dark mode everywhere", 0.9, ["theme"],
                conversation_id=convo_id_2, source_message_id=assistant_msg_id_2,
            )
        await session.commit()

    async with session_factory() as session:
        memories = await get_memories(session, user.id, "chat")
        assert memories[0].conversation_id == convo_id_2
        assert memories[0].source_message_id == assistant_msg_id_2


@pytest.mark.asyncio
async def test_sync_memory_to_qdrant_payload_includes_provenance_metadata(session_factory, create_test_user):
    from app.services.memory import create_memory

    user = await create_test_user("qdrantpayloaduser@example.com", "pass123")
    convo_id, _, assistant_msg_id = await _make_conversation_and_messages(session_factory, user.id)

    mock_client = MagicMock()
    mock_client.upsert = AsyncMock()

    async with session_factory() as session:
        with patch("app.services.memory._get_qdrant", return_value=mock_client), patch(
            "app.services.memory._get_embeddings"
        ) as mock_get_embeddings:
            mock_get_embeddings.return_value.aembed_query = AsyncMock(return_value=[0.1] * 1536)
            await create_memory(
                session, user.id, "chat", "event", "Fixed a K8s pod crash loop", 0.7, [],
                conversation_id=convo_id, source_message_id=assistant_msg_id,
            )
        await session.commit()

    payload = mock_client.upsert.call_args.kwargs["points"][0].payload
    assert payload["conversation_id"] == str(convo_id)
    assert "created_at" in payload and payload["created_at"] is not None


@pytest.mark.asyncio
async def test_hydrate_source_exchange_found(session_factory, create_test_user):
    from app.services.memory import hydrate_source_exchange

    user = await create_test_user("hydrateuser@example.com", "pass123")
    convo_id, user_msg_id, assistant_msg_id = await _make_conversation_and_messages(session_factory, user.id)

    async with session_factory() as session:
        memory = AgentMemory(
            user_id=user.id, agent_slug="chat", category="event",
            content="Fixed a K8s pod crash loop", conversation_id=convo_id,
            source_message_id=assistant_msg_id,
        )
        session.add(memory)
        await session.commit()

        exchange = await hydrate_source_exchange(session, memory)

    assert exchange is not None
    user_msg, assistant_msg = exchange
    assert user_msg.id == user_msg_id
    assert assistant_msg.id == assistant_msg_id


@pytest.mark.asyncio
async def test_hydrate_source_exchange_missing_reference_returns_none(session_factory, create_test_user):
    from app.services.memory import create_memory, hydrate_source_exchange

    user = await create_test_user("hydratemissing@example.com", "pass123")

    async with session_factory() as session:
        memory = await create_memory(session, user.id, "chat", "fact", "Uses vim", 0.6, [])
        await session.commit()

        exchange = await hydrate_source_exchange(session, memory)

    assert exchange is None


def test_format_recall_context_empty():
    from app.services.memory import format_recall_context
    assert format_recall_context([]) == ""


def test_format_recall_context_with_exchange():
    from app.services.memory import format_recall_context

    user_msg = MagicMock()
    user_msg.content = "Do you remember when we fixed the pod crash loop?"

    assistant_msg = MagicMock()
    assistant_msg.content = "Yes - it was a misconfigured resource limit."
    assistant_msg.created_at = datetime(2026, 3, 1, tzinfo=UTC)

    result = format_recall_context([(user_msg, assistant_msg)])
    assert "A Past Exchange You're Being Asked About" in result
    assert "pod crash loop" in result
    assert "misconfigured resource limit" in result
    assert "2026-03-01" in result


@pytest.mark.asyncio
async def test_retrieve_memories_sql(session_factory, create_test_user):
    from app.services.memory import create_memory, retrieve_memories_sql

    user = await create_test_user("sqluser@example.com", "pass123")
    async with session_factory() as session:
        await create_memory(session, user.id, "chat", "fact", "Uses Python daily", 0.9, ["python"])
        await create_memory(session, user.id, "chat", "preference", "Prefers dark mode", 0.5, ["ui"])
        await session.commit()

    async with session_factory() as session:
        results = await retrieve_memories_sql(session, user.id, "chat", "Python")
        assert len(results) >= 1
        assert any("Python" in m.content for m in results)


@pytest.mark.asyncio
async def test_retrieve_memories_preserves_qdrant_relevance_order(session_factory, create_test_user):
    """Regression test: a lower-importance-but-semantically-relevant memory
    returned first by Qdrant must stay first in the final result - it must not
    get reordered behind a higher-importance-but-less-relevant SQL fallback hit."""
    from app.services.memory import create_memory, retrieve_memories

    user = await create_test_user("orderuser@example.com", "pass123")
    async with session_factory() as session:
        relevant_low_importance = await create_memory(
            session, user.id, "chat", "fact", "The user's favorite color is teal", 0.2, []
        )
        irrelevant_high_importance = await create_memory(
            session, user.id, "chat", "fact", "The user works in finance", 0.95, []
        )
        await session.commit()

    async with session_factory() as session:
        with patch(
            "app.services.memory.retrieve_memories_qdrant",
            AsyncMock(return_value=[relevant_low_importance]),
        ), patch(
            "app.services.memory.retrieve_memories_sql",
            AsyncMock(return_value=[irrelevant_high_importance]),
        ):
            results = await retrieve_memories(session, user.id, "chat", "what color do I like?", limit=5)

    assert [m.id for m in results] == [relevant_low_importance.id, irrelevant_high_importance.id]


@pytest.mark.asyncio
async def test_extract_memories_returns_list():
    mock_response = MagicMock()
    mock_response.content = (
        '{"memories": [{"category": "preference", "content": "Likes short answers", '
        '"importance": 0.8, "tags": ["communication"]}], "resolved_commitment_ids": []}'
    )

    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("app.services.memory.get_chat_model", return_value=mock_llm):
        from app.services.memory import extract_memories
        result = await extract_memories("Give me a quick summary", "Here's a brief summary.", [])

    assert len(result["memories"]) == 1
    assert result["memories"][0]["category"] == "preference"
    assert result["memories"][0]["content"] == "Likes short answers"
    assert result["resolved_commitment_ids"] == []


@pytest.mark.asyncio
async def test_extract_memories_failure_returns_empty():
    with patch("app.services.memory.get_chat_model", side_effect=Exception("LLM down")):
        from app.services.memory import extract_memories
        result = await extract_memories("hi", "hello", [])

    assert result == {"memories": [], "resolved_commitment_ids": []}


@pytest.mark.asyncio
async def test_extract_memories_flags_resolved_commitment(session_factory, create_test_user):
    """A commitment id returned by the LLM must be echoed back only if it
    matches one of the open commitments actually passed in - guards against
    the model hallucinating an id that doesn't correspond to a real row."""
    from app.services.memory import create_memory, extract_memories

    user = await create_test_user("resolveuser@example.com", "pass123")
    async with session_factory() as session:
        commitment = await create_memory(
            session, user.id, "chat", "commitment", "Will send the report Friday", 0.8, []
        )
        await session.commit()

    mock_response = MagicMock()
    mock_response.content = (
        '{"memories": [], "resolved_commitment_ids": ["%s", "not-a-real-id"]}' % commitment.id
    )
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("app.services.memory.get_chat_model", return_value=mock_llm):
        result = await extract_memories(
            "Did you send the report?", "Yes, just sent it over.", [], [commitment]
        )

    assert result["resolved_commitment_ids"] == [str(commitment.id)]


@pytest.mark.asyncio
async def test_extract_memories_flags_supersession(session_factory, create_test_user):
    """A new fact that corrects an existing one should carry back the id it
    supersedes - but only if that id matches a real existing memory, guarding
    against a hallucinated id."""
    from app.services.memory import create_memory, extract_memories

    user = await create_test_user("supersedeuser@example.com", "pass123")
    async with session_factory() as session:
        old_fact = await create_memory(session, user.id, "chat", "fact", "Works at Google", 0.6, [])
        await session.commit()

    mock_response = MagicMock()
    mock_response.content = (
        '{"memories": [{"category": "fact", "content": "Works at Meta", "importance": 0.6, '
        '"tags": [], "supersedes_id": "%s"}], "resolved_commitment_ids": []}' % old_fact.id
    )
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("app.services.memory.get_chat_model", return_value=mock_llm):
        result = await extract_memories(
            "I changed jobs, I work at Meta now", "Got it, updated!", [old_fact]
        )

    assert len(result["memories"]) == 1
    assert result["memories"][0]["supersedes_id"] == str(old_fact.id)


@pytest.mark.asyncio
async def test_extract_memories_ignores_hallucinated_supersedes_id(session_factory, create_test_user):
    from app.services.memory import create_memory, extract_memories

    user = await create_test_user("supersedeuser2@example.com", "pass123")
    async with session_factory() as session:
        old_fact = await create_memory(session, user.id, "chat", "fact", "Works at Google", 0.6, [])
        await session.commit()

    mock_response = MagicMock()
    mock_response.content = (
        '{"memories": [{"category": "fact", "content": "Works at Meta", "importance": 0.6, '
        '"tags": [], "supersedes_id": "not-a-real-id"}], "resolved_commitment_ids": []}'
    )
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("app.services.memory.get_chat_model", return_value=mock_llm):
        result = await extract_memories("I work at Meta now", "Got it!", [old_fact])

    assert result["memories"][0]["supersedes_id"] is None


@pytest.mark.asyncio
async def test_find_merge_candidate_ignores_superseded_record(session_factory, create_test_user):
    from unittest.mock import AsyncMock as AM

    from app.services.memory import _find_merge_candidate, create_memory

    user = await create_test_user("supersededcandidate@example.com", "pass123")
    async with session_factory() as session:
        old_fact = await create_memory(session, user.id, "chat", "fact", "Works at Google", 0.6, [])
        old_fact.status = "superseded"
        old_fact.qdrant_point_id = str(old_fact.id)
        await session.commit()
        old_fact_id = old_fact.id

    fake_hit = MagicMock()
    fake_hit.id = str(old_fact_id)
    fake_hit.score = 0.95

    mock_client = MagicMock()
    mock_client.search = AM(return_value=[fake_hit])

    async with session_factory() as session:
        with patch("app.services.memory._get_qdrant", return_value=mock_client), patch(
            "app.services.memory._get_embeddings"
        ) as mock_get_embeddings:
            mock_get_embeddings.return_value.aembed_query = AM(return_value=[0.1] * 1536)
            result = await _find_merge_candidate(session, user.id, "chat", "Works at Meta now")

    assert result is None


@pytest.mark.asyncio
async def test_get_memories_includes_superseded_but_ranks_current_first(session_factory, create_test_user):
    """A superseded fact (e.g. a past employer) is still true, just not current -
    it should stay retrievable (so "what companies have you worked at" still
    surfaces it) but rank below a current fact of similar importance."""
    from app.services.memory import create_memory, get_memories

    user = await create_test_user("rankcurrentfirst@example.com", "pass123")
    async with session_factory() as session:
        old_fact = await create_memory(session, user.id, "chat", "fact", "Works at Google", 0.6, [])
        old_fact.status = "superseded"
        await create_memory(session, user.id, "chat", "fact", "Works at Meta", 0.6, [])
        await session.commit()

    async with session_factory() as session:
        results = await get_memories(session, user.id, "chat")

    contents = [m.content for m in results]
    assert set(contents) == {"Works at Google", "Works at Meta"}
    assert contents[0] == "Works at Meta"


def test_format_commitments_context_empty():
    from app.services.memory import format_commitments_context
    assert format_commitments_context([]) == ""


def test_format_commitments_context_with_commitments():
    from app.services.memory import format_commitments_context

    c1 = MagicMock(spec=AgentMemory)
    c1.content = "Will check with the infra team and follow up by Friday"

    result = format_commitments_context([c1])
    assert "Follow Up" in result
    assert "infra team" in result


@pytest.mark.asyncio
async def test_get_recent_commitments_only_returns_commitment_category(session_factory, create_test_user):
    from app.services.memory import create_memory, get_recent_commitments

    user = await create_test_user("commituser@example.com", "pass123")
    async with session_factory() as session:
        await create_memory(session, user.id, "chat", "fact", "Works in finance", 0.6, [])
        await create_memory(session, user.id, "chat", "commitment", "Will send the report Friday", 0.8, [])
        await session.commit()

    async with session_factory() as session:
        results = await get_recent_commitments(session, user.id, "chat")
        assert len(results) == 1
        assert results[0].category == "commitment"
        assert "report Friday" in results[0].content


@pytest.mark.asyncio
async def test_get_recent_commitments_excludes_resolved(session_factory, create_test_user):
    from app.services.memory import create_memory, get_recent_commitments

    user = await create_test_user("resolvedcommituser@example.com", "pass123")
    async with session_factory() as session:
        await create_memory(session, user.id, "chat", "commitment", "Will send the report Friday", 0.8, [])
        resolved = await create_memory(session, user.id, "chat", "commitment", "Will check with infra team", 0.8, [])
        resolved.status = "resolved"
        await session.commit()

    async with session_factory() as session:
        results = await get_recent_commitments(session, user.id, "chat")
        assert len(results) == 1
        assert "report Friday" in results[0].content


@pytest.mark.asyncio
async def test_consolidate_and_store_memory_creates_when_no_candidate(session_factory, create_test_user):
    from app.services.memory import consolidate_and_store_memory, get_memories

    user = await create_test_user("consolidate1@example.com", "pass123")
    async with session_factory() as session:
        with patch("app.services.memory._find_merge_candidate", AsyncMock(return_value=None)):
            await consolidate_and_store_memory(
                session, user.id, "chat", "fact", "Likes concise answers", 0.6, []
            )
        await session.commit()

    async with session_factory() as session:
        memories = await get_memories(session, user.id, "chat")
        assert len(memories) == 1
        assert memories[0].content == "Likes concise answers"


@pytest.mark.asyncio
async def test_consolidate_and_store_memory_auto_merges_near_verbatim(session_factory, create_test_user):
    """A very high embedding similarity should merge without needing an LLM
    confirmation call at all."""
    from app.services.memory import consolidate_and_store_memory, create_memory, get_memories

    user = await create_test_user("consolidate2@example.com", "pass123")
    async with session_factory() as session:
        existing = await create_memory(
            session, user.id, "chat", "preference", "Prefers dark mode", 0.5, ["ui"]
        )
        await session.commit()
        existing_id = existing.id

    async with session_factory() as session:
        existing_row = await session.get(AgentMemory, existing_id)
        same_check = AsyncMock()
        with patch(
            "app.services.memory._find_merge_candidate",
            AsyncMock(return_value=(existing_row, 0.97)),
        ), patch("app.services.memory._same_underlying_memory", same_check), patch(
            "app.services.memory._sync_memory_to_qdrant", AsyncMock(return_value="pt")
        ):
            await consolidate_and_store_memory(
                session, user.id, "chat", "preference", "Strongly prefers dark mode everywhere", 0.9, ["theme"]
            )
        await session.commit()

    same_check.assert_not_called()  

    async with session_factory() as session:
        memories = await get_memories(session, user.id, "chat")
        assert len(memories) == 1
        assert memories[0].id == existing_id
        assert memories[0].importance_score == 0.9
        assert set(memories[0].tags) == {"ui", "theme"}
        assert memories[0].content == "Strongly prefers dark mode everywhere"


@pytest.mark.asyncio
async def test_consolidate_and_store_memory_merges_after_llm_confirmation(session_factory, create_test_user):
    """A borderline embedding score (candidate but below the auto-merge bar) should
    still merge if the LLM confirms it's the same underlying fact - this is the
    real-world case a flat similarity cutoff misses: a short fact vs. a longer,
    differently-worded restatement of the same thing."""
    from app.services.memory import consolidate_and_store_memory, create_memory, get_memories

    user = await create_test_user("consolidate3@example.com", "pass123")
    async with session_factory() as session:
        existing = await create_memory(
            session, user.id, "chat", "preference", "User prefers dark mode.", 0.65, ["dark-mode"]
        )
        await session.commit()
        existing_id = existing.id

    async with session_factory() as session:
        existing_row = await session.get(AgentMemory, existing_id)
        with patch(
            "app.services.memory._find_merge_candidate",
            AsyncMock(return_value=(existing_row, 0.82)),
        ), patch(
            "app.services.memory._same_underlying_memory", AsyncMock(return_value=True)
        ), patch("app.services.memory._sync_memory_to_qdrant", AsyncMock(return_value="pt")):
            await consolidate_and_store_memory(
                session, user.id, "chat", "preference",
                "User strongly prefers using dark mode everywhere and all the time.", 0.85, ["dark-mode", "preference"],
            )
        await session.commit()

    async with session_factory() as session:
        memories = await get_memories(session, user.id, "chat")
        assert len(memories) == 1
        assert memories[0].id == existing_id
        assert memories[0].importance_score == 0.85
        assert memories[0].content == "User strongly prefers using dark mode everywhere and all the time."


@pytest.mark.asyncio
async def test_consolidate_and_store_memory_creates_new_when_llm_rejects_match(session_factory, create_test_user):
    """Below the auto-merge bar and the LLM says they're different facts -> don't merge."""
    from app.services.memory import consolidate_and_store_memory, create_memory, get_memories

    user = await create_test_user("consolidate4@example.com", "pass123")
    async with session_factory() as session:
        existing = await create_memory(
            session, user.id, "chat", "preference", "Prefers dark mode", 0.5, ["ui"]
        )
        await session.commit()
        existing_id = existing.id

    async with session_factory() as session:
        existing_row = await session.get(AgentMemory, existing_id)
        with patch(
            "app.services.memory._find_merge_candidate",
            AsyncMock(return_value=(existing_row, 0.80)),
        ), patch("app.services.memory._same_underlying_memory", AsyncMock(return_value=False)):
            await consolidate_and_store_memory(
                session, user.id, "chat", "fact", "Works the night shift", 0.5, []
            )
        await session.commit()

    async with session_factory() as session:
        memories = await get_memories(session, user.id, "chat")
        assert len(memories) == 2
        contents = {m.content for m in memories}
        assert contents == {"Prefers dark mode", "Works the night shift"}


@pytest.mark.asyncio
async def test_same_underlying_memory_true():
    mock_response = MagicMock()
    mock_response.content = "same"
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("app.services.memory.get_chat_model", return_value=mock_llm):
        from app.services.memory import _same_underlying_memory
        result = await _same_underlying_memory("Prefers dark mode.", "Really likes dark mode everywhere.")

    assert result is True


@pytest.mark.asyncio
async def test_same_underlying_memory_false():
    mock_response = MagicMock()
    mock_response.content = "different"
    mock_llm = AsyncMock()
    mock_llm.ainvoke = AsyncMock(return_value=mock_response)

    with patch("app.services.memory.get_chat_model", return_value=mock_llm):
        from app.services.memory import _same_underlying_memory
        result = await _same_underlying_memory("Prefers dark mode.", "Works in finance.")

    assert result is False


@pytest.mark.asyncio
async def test_same_underlying_memory_failure_returns_false():
    with patch("app.services.memory.get_chat_model", side_effect=Exception("LLM down")):
        from app.services.memory import _same_underlying_memory
        result = await _same_underlying_memory("A", "B")

    assert result is False
