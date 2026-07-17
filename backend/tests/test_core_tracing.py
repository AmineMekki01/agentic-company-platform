"""Tests for the Langfuse tracing helper (app.core.tracing)."""

from unittest.mock import MagicMock, patch

from app.core.config import settings
from app.core.tracing import get_langfuse_handler, new_langfuse_handler, trace_config, trace_url_for


def test_get_langfuse_handler_none_when_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "langfuse_public_key", "")
    monkeypatch.setattr(settings, "langfuse_secret_key", "")
    monkeypatch.setattr("app.core.tracing._handler", None)
    monkeypatch.setattr("app.core.tracing._handler_init_attempted", False)

    assert get_langfuse_handler() is None


def test_get_langfuse_handler_caches_result(monkeypatch):
    monkeypatch.setattr(settings, "langfuse_public_key", "pk-test")
    monkeypatch.setattr(settings, "langfuse_secret_key", "sk-test")
    monkeypatch.setattr("app.core.tracing._handler", None)
    monkeypatch.setattr("app.core.tracing._handler_init_attempted", False)

    fake_handler = MagicMock()
    with patch("langfuse.langchain.CallbackHandler", return_value=fake_handler) as mock_ctor:
        first = get_langfuse_handler()
        second = get_langfuse_handler()

    assert first is fake_handler
    assert second is fake_handler
    mock_ctor.assert_called_once()


def test_get_langfuse_handler_swallows_init_failure(monkeypatch):
    monkeypatch.setattr(settings, "langfuse_public_key", "pk-test")
    monkeypatch.setattr(settings, "langfuse_secret_key", "sk-test")
    monkeypatch.setattr("app.core.tracing._handler", None)
    monkeypatch.setattr("app.core.tracing._handler_init_attempted", False)

    with patch("langfuse.langchain.CallbackHandler", side_effect=Exception("unreachable")):
        assert get_langfuse_handler() is None


def test_trace_config_noop_when_disabled(monkeypatch):
    monkeypatch.setattr("app.core.tracing.get_langfuse_handler", lambda: None)

    base = {"configurable": {"thread_id": "abc"}}
    result = trace_config(base, conversation_id="c1", user_id="u1", agent_slug="chat")

    assert result == base


def test_trace_config_merges_callback_and_metadata(monkeypatch):
    fake_handler = MagicMock()
    monkeypatch.setattr("app.core.tracing.get_langfuse_handler", lambda: fake_handler)

    base = {"configurable": {"thread_id": "abc"}}
    result = trace_config(base, conversation_id="c1", user_id="u1", agent_slug="chat", tags=["eval"])

    assert result["configurable"] == {"thread_id": "abc"}
    assert result["callbacks"] == [fake_handler]
    assert result["metadata"]["langfuse_session_id"] == "c1"
    assert result["metadata"]["langfuse_user_id"] == "u1"

    from app.core.tenant_context import get_current_tenant
    tenant_tag = f"tenant:{get_current_tenant()}"
    assert result["metadata"]["langfuse_tags"] == ["chat", tenant_tag, "eval"]
    assert result["metadata"]["tenant_id"] == str(get_current_tenant())
    assert "callbacks" not in base


def test_trace_config_drops_falsy_tags(monkeypatch):
    fake_handler = MagicMock()
    monkeypatch.setattr("app.core.tracing.get_langfuse_handler", lambda: fake_handler)

    result = trace_config({}, agent_slug=None, tags=None)

    from app.core.tenant_context import get_current_tenant
    assert result["metadata"]["langfuse_tags"] == [f"tenant:{get_current_tenant()}"]


def test_trace_config_preserves_existing_callbacks(monkeypatch):
    fake_handler = MagicMock()
    monkeypatch.setattr("app.core.tracing.get_langfuse_handler", lambda: fake_handler)

    existing_callback = MagicMock()
    base = {"callbacks": [existing_callback]}
    result = trace_config(base, agent_slug="chat")

    assert result["callbacks"] == [existing_callback, fake_handler]


def test_new_langfuse_handler_none_when_unconfigured(monkeypatch):
    monkeypatch.setattr(settings, "langfuse_public_key", "")
    monkeypatch.setattr(settings, "langfuse_secret_key", "")

    assert new_langfuse_handler() is None


def test_new_langfuse_handler_returns_fresh_instance_each_call(monkeypatch):
    """Unlike get_langfuse_handler's cached singleton, this must construct a new
    instance every call - callers rely on reading back this specific instance's
    last_trace_id without racing other concurrent traced calls."""
    monkeypatch.setattr(settings, "langfuse_public_key", "pk-test")
    monkeypatch.setattr(settings, "langfuse_secret_key", "sk-test")

    with patch("langfuse.langchain.CallbackHandler", side_effect=lambda: MagicMock()) as mock_ctor:
        first = new_langfuse_handler()
        second = new_langfuse_handler()

    assert first is not second
    assert mock_ctor.call_count == 2


def test_new_langfuse_handler_swallows_init_failure(monkeypatch):
    monkeypatch.setattr(settings, "langfuse_public_key", "pk-test")
    monkeypatch.setattr(settings, "langfuse_secret_key", "sk-test")

    with patch("langfuse.langchain.CallbackHandler", side_effect=Exception("unreachable")):
        assert new_langfuse_handler() is None


def test_trace_url_for_none_when_handler_none():
    assert trace_url_for(None) is None


def test_trace_url_for_none_when_no_trace_recorded(monkeypatch):
    monkeypatch.setattr(settings, "langfuse_public_host", "http://localhost:3000")
    handler = MagicMock()
    handler.last_trace_id = None

    assert trace_url_for(handler) is None


def test_trace_url_for_none_when_public_host_unset(monkeypatch):
    monkeypatch.setattr(settings, "langfuse_public_host", "")
    handler = MagicMock()
    handler.last_trace_id = "abc123"

    assert trace_url_for(handler) is None


def test_trace_url_for_builds_url(monkeypatch):
    monkeypatch.setattr(settings, "langfuse_public_host", "http://localhost:3000/")
    handler = MagicMock()
    handler.last_trace_id = "abc123"

    assert trace_url_for(handler) == "http://localhost:3000/trace/abc123"


def test_trace_config_off_mode_records_nothing(monkeypatch):
    """tracing_mode='off' means no callback is attached at all."""
    from app.core.tracing import reset_tracing_mode, set_tracing_mode

    fake_handler = MagicMock()
    monkeypatch.setattr("app.core.tracing.get_langfuse_handler", lambda: fake_handler)

    base = {"configurable": {"thread_id": "abc"}}
    token = set_tracing_mode("off")
    try:
        result = trace_config(base, conversation_id="c1", agent_slug="chat")
    finally:
        reset_tracing_mode(token)

    assert result == base
    assert "callbacks" not in result


def test_mask_redacts_only_in_masked_mode():
    from app.core.tracing import MASK_PLACEHOLDER, _mask, reset_tracing_mode, set_tracing_mode

    payload = {"prompt": "confidential customer document"}

    token = set_tracing_mode("full")
    try:
        assert _mask(data=payload) == payload
    finally:
        reset_tracing_mode(token)

    token = set_tracing_mode("masked")
    try:
        assert _mask(data=payload) == MASK_PLACEHOLDER
    finally:
        reset_tracing_mode(token)


def test_tracing_mode_defaults_to_full():
    from app.core.tracing import get_tracing_mode
    assert get_tracing_mode() == "full"


def test_invalid_tracing_mode_falls_back_to_default():
    from app.core.tracing import get_tracing_mode, reset_tracing_mode, set_tracing_mode

    token = set_tracing_mode("bogus")
    try:
        assert get_tracing_mode() == "full"
    finally:
        reset_tracing_mode(token)
