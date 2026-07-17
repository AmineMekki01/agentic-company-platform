"""Regression tests: one tenant's LLM config must never leak into another's."""

from unittest.mock import patch

from app.agents.llm import (
    get_ollama_base_url,
    reset_ollama_base_url,
    set_ollama_base_url,
)
from app.core.config import settings


def test_falls_back_to_deployment_default_when_tenant_has_none():
    token = set_ollama_base_url(None)
    try:
        assert get_ollama_base_url() == settings.ollama_base_url
    finally:
        reset_ollama_base_url(token)


def test_tenant_value_overrides_default():
    token = set_ollama_base_url("http://acme-ollama:11434/v1")
    try:
        assert get_ollama_base_url() == "http://acme-ollama:11434/v1"
    finally:
        reset_ollama_base_url(token)


def test_one_tenant_url_does_not_leak_into_another():
    """The core regression: tenant A's endpoint must not persist into tenant B."""
    a = set_ollama_base_url("http://acme-ollama:11434/v1")
    assert get_ollama_base_url() == "http://acme-ollama:11434/v1"
    reset_ollama_base_url(a)

    b = set_ollama_base_url("http://guild-ollama:11434/v1")
    assert get_ollama_base_url() == "http://guild-ollama:11434/v1"
    reset_ollama_base_url(b)

    assert settings.ollama_base_url not in (
        "http://acme-ollama:11434/v1",
        "http://guild-ollama:11434/v1",
    )


def test_get_chat_model_uses_the_tenant_endpoint():
    from app.agents.llm import get_chat_model

    token = set_ollama_base_url("http://acme-ollama:11434/v1")
    try:
        with patch("app.agents.llm.ChatOpenAI") as mock_cls:
            get_chat_model("ollama/qwen3.5:2b")
        assert mock_cls.call_args.kwargs["base_url"] == "http://acme-ollama:11434/v1"
    finally:
        reset_ollama_base_url(token)


def test_saving_settings_does_not_mutate_global(monkeypatch):
    """admin_llm_settings must not write tenant config into app settings."""
    import inspect

    import app.api.admin_llm_settings as mod

    src = inspect.getsource(mod)
    assert "app_settings.ollama_enabled =" not in src
    assert "app_settings.ollama_base_url =" not in src
    assert "_sync_to_runtime" not in src
