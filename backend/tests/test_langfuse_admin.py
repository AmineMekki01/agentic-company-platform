"""Tests for Langfuse trace purging (retention + per-tenant erasure)."""
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.langfuse_admin import (
    purge_tenant_traces,
    purge_traces_older_than,
    tenant_tag,
)


def _fake_client(pages):
    """Client whose trace.list returns each page in turn."""
    client = MagicMock()
    client.api.trace.list.side_effect = [SimpleNamespace(data=p) for p in pages]
    return client


def _traces(n, prefix="t"):
    return [SimpleNamespace(id=f"{prefix}{i}") for i in range(n)]


def test_tenant_tag_format():
    tid = uuid.uuid4()
    assert tenant_tag(tid) == f"tenant:{tid}"


def test_purge_noop_when_unconfigured(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "langfuse_public_key", "")
    monkeypatch.setattr(settings, "langfuse_secret_key", "")
    assert purge_traces_older_than(30) == 0
    assert purge_tenant_traces(uuid.uuid4()) == 0


def test_retention_disabled_when_days_zero():
    with patch("app.services.langfuse_admin._client") as c:
        assert purge_traces_older_than(0) == 0
        c.assert_not_called()


def test_retention_deletes_old_traces():
    client = _fake_client([_traces(2)])
    with patch("app.services.langfuse_admin._client", return_value=client):
        deleted = purge_traces_older_than(30)

    assert deleted == 2
    assert "to_timestamp" in client.api.trace.list.call_args.kwargs
    client.api.trace.delete_multiple.assert_called_once_with(trace_ids=["t0", "t1"])


def test_retention_survives_api_failure():
    client = MagicMock()
    client.api.trace.list.side_effect = RuntimeError("langfuse down")
    with patch("app.services.langfuse_admin._client", return_value=client):
        assert purge_traces_older_than(30) == 0


def test_tenant_purge_filters_by_tenant_tag():
    tid = uuid.uuid4()
    client = _fake_client([_traces(3)])
    with patch("app.services.langfuse_admin._client", return_value=client):
        deleted = purge_tenant_traces(tid)

    assert deleted == 3
    assert client.api.trace.list.call_args.kwargs["tags"] == [f"tenant:{tid}"]
    client.api.trace.delete_multiple.assert_called_once_with(trace_ids=["t0", "t1", "t2"])


def test_tenant_purge_raises_on_failure():
    """Erasure must not fail silently - a swallowed error means we would claim
    a tenant's data was deleted when their prompts still exist."""
    client = MagicMock()
    client.api.trace.list.side_effect = RuntimeError("langfuse down")
    with patch("app.services.langfuse_admin._client", return_value=client):
        with pytest.raises(RuntimeError):
            purge_tenant_traces(uuid.uuid4())


def test_tenant_purge_paginates():
    """A tenant with more traces than one page must be fully purged."""
    client = _fake_client([_traces(100, "a"), _traces(5, "b")])
    with patch("app.services.langfuse_admin._client", return_value=client):
        deleted = purge_tenant_traces(uuid.uuid4())

    assert deleted == 105
    assert client.api.trace.list.call_count == 2
    assert client.api.trace.delete_multiple.call_count == 2
