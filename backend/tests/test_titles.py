"""Tests for titles service."""

import pytest

from app.services.titles import _truncate, generate_title



def test_truncate_short():
    assert _truncate("hello") == "hello"


def test_truncate_long():
    text = "a" * 100
    result = _truncate(text, limit=60)
    assert len(result) == 60
    assert result.endswith("…")


def test_truncate_collapses_whitespace():
    assert _truncate("hello    world") == "hello world"


async def test_generate_title_no_api_key(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "openai_api_key", "")
    title = await generate_title("What is the vacation policy?")
    assert "vacation" in title.lower()


async def test_generate_title_with_llm(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "openai_api_key", "fake-key")

    class FakeLLM:
        async def ainvoke(self, messages):
            class Resp:
                content = "Vacation Policy Inquiry"
            return Resp()

    monkeypatch.setattr("app.services.titles.get_chat_model", lambda model, **kw: FakeLLM())
    title = await generate_title("What is the vacation policy?")
    assert title == "Vacation Policy Inquiry"


async def test_generate_title_llm_failure(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "openai_api_key", "fake-key")

    class FakeLLM:
        async def ainvoke(self, messages):
            raise RuntimeError("LLM error")

    monkeypatch.setattr("app.services.titles.get_chat_model", lambda model, **kw: FakeLLM())
    title = await generate_title("What is the vacation policy?")
    assert "vacation" in title.lower()
