"""Tests for agent tools module."""

import json

import pytest

pytestmark = pytest.mark.asyncio


async def test_retrieve_tool(monkeypatch):
    from app.agents import tools

    async def fake_retrieve_and_format(query, source_ids=None):
        return "Relevant info here", [{"rank": 1, "title": "Doc 1", "id": "src1"}]

    monkeypatch.setattr(tools, "_retrieve_and_format", fake_retrieve_and_format)

    result = await tools.retrieve.ainvoke({"query": "vacation policy"})
    data = json.loads(result)
    assert "text" in data
    assert data["text"] == "Relevant info here"
    assert len(data["sources"]) == 1


async def test_retrieve_tool_no_results(monkeypatch):
    from app.agents import tools

    async def fake_retrieve_and_format(query, source_ids=None):
        return "No relevant documents found.", []

    monkeypatch.setattr(tools, "_retrieve_and_format", fake_retrieve_and_format)

    result = await tools.retrieve.ainvoke({"query": "nonexistent topic"})
    data = json.loads(result)
    assert data["sources"] == []


async def test_retrieve_tool_with_source_filter(monkeypatch):
    from app.agents import tools

    captured = {}

    async def fake_retrieve_and_format(query, source_ids=None):
        captured["source_ids"] = source_ids
        return "info", []

    monkeypatch.setattr(tools, "_retrieve_and_format", fake_retrieve_and_format)

    await tools.retrieve.ainvoke({"query": "test", "sources": ["src1", "src2"]})
    assert captured["source_ids"] == ["src1", "src2"]


async def test_web_search_no_api_key(monkeypatch):
    from app.agents import tools
    from app.core.config import settings

    monkeypatch.setattr(settings, "tavily_api_key", "")
    result = await tools.web_search.ainvoke({"query": "test query"})
    data = json.loads(result)
    assert "not configured" in data["text"].lower()


async def test_web_search_success(monkeypatch):
    from app.agents import tools
    from app.core.config import settings

    monkeypatch.setattr(settings, "tavily_api_key", "fake-key")

    class FakeTavilyClient:
        async def search(self, query, max_results=5, search_depth="basic"):
            return {
                "results": [
                    {"title": "Result 1", "url": "http://example.com", "content": "Content here"}
                ]
            }

    monkeypatch.setattr("tavily.AsyncTavilyClient", lambda api_key: FakeTavilyClient())
    result = await tools.web_search.ainvoke({"query": "test"})
    data = json.loads(result)
    assert len(data["sources"]) == 1
    assert data["sources"][0]["title"] == "Result 1"


async def test_web_search_uses_configured_max_results(monkeypatch):
    from app.agents import tools
    from app.core.config import settings

    monkeypatch.setattr(settings, "tavily_api_key", "fake-key")
    captured = {}

    class FakeTavilyClient:
        async def search(self, query, max_results=5, search_depth="basic"):
            captured["max_results"] = max_results
            return {"results": []}

    monkeypatch.setattr("tavily.AsyncTavilyClient", lambda api_key: FakeTavilyClient())
    await tools.web_search.ainvoke({"query": "test", "max_results": 3})
    assert captured["max_results"] == 3


async def test_web_search_clamps_max_results(monkeypatch):
    from app.agents import tools
    from app.core.config import settings

    monkeypatch.setattr(settings, "tavily_api_key", "fake-key")
    captured = {}

    class FakeTavilyClient:
        async def search(self, query, max_results=5, search_depth="basic"):
            captured["max_results"] = max_results
            return {"results": []}

    monkeypatch.setattr("tavily.AsyncTavilyClient", lambda api_key: FakeTavilyClient())
    await tools.web_search.ainvoke({"query": "test", "max_results": 100})
    assert captured["max_results"] == 20


async def test_web_search_no_results(monkeypatch):
    from app.agents import tools
    from app.core.config import settings

    monkeypatch.setattr(settings, "tavily_api_key", "fake-key")

    class FakeTavilyClient:
        async def search(self, query, max_results=5, search_depth="basic"):
            return {"results": []}

    monkeypatch.setattr("tavily.AsyncTavilyClient", lambda api_key: FakeTavilyClient())
    result = await tools.web_search.ainvoke({"query": "test"})
    data = json.loads(result)
    assert "No results" in data["text"]


async def test_web_search_error(monkeypatch):
    from app.agents import tools
    from app.core.config import settings

    monkeypatch.setattr(settings, "tavily_api_key", "fake-key")

    class FakeTavilyClient:
        async def search(self, query, max_results=5, search_depth="basic"):
            raise RuntimeError("API error")

    monkeypatch.setattr("tavily.AsyncTavilyClient", lambda api_key: FakeTavilyClient())
    result = await tools.web_search.ainvoke({"query": "test"})
    data = json.loads(result)
    assert "error" in data["text"].lower()
