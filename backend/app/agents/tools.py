"""Tools available to agents."""

import json
import logging
from typing import Annotated

from langchain_core.tools import tool

from app.services.rag import RAGService, RetrievedChunk

logger = logging.getLogger(__name__)

async def _retrieve_and_format(
    query: str,
    source_ids: list[str] | None = None,
    top_k: int = 5,
) -> tuple[str, list[dict]]:
    """Retrieve chunks and return both formatted text and structured sources.

    Args:
        query: The search query
        source_ids: Optional list of source IDs to filter by
        top_k: Number of chunks to retrieve

    Returns:
        Tuple of (formatted_text, source_metadata_list)
    """
    rag = RAGService()
    chunks: list[RetrievedChunk] = await rag.retrieve(query, source_ids=source_ids, top_k=top_k)

    if not chunks:
        return "No relevant documents found in the knowledge base.", []

    lines = []
    sources = []
    for c in chunks:
        lines.append(
            f"[{c.rank}] {c.source_title}\nScore: {c.score:.3f}\n{c.text}"
        )
        sources.append({"rank": c.rank, "title": c.source_title, "id": c.source_id, "url": c.source_url})
    return "\n\n---\n\n".join(lines), sources


@tool
async def retrieve(
    query: Annotated[str, "The search query"],
    sources: Annotated[list[str] | None, "Optional list of source IDs to filter by"] = None,
) -> str:
    """
    Search the company knowledge base for relevant documents.
    
    Use this when the user asks about company policies, procedures, HR topics,
    IT runbooks, or any internal document. Returns top relevant passages with
    source titles and citation numbers.
    
    Args:
        query: The search query
        sources: Optional list of source IDs to filter by
        
    Returns:
        Top relevant passages with source titles and citation numbers
    """
    text, srcs = await _retrieve_and_format(query, source_ids=sources)
    logger.info("Retrieve tool called with query: %s, sources: %s", query, sources)
    return json.dumps({"text": text, "sources": srcs})


@tool
async def web_search(query: Annotated[str, "The web search query"]) -> str:
    """
    Search the public web for real-time information.
    
    Use this for current events, external facts, market data, or anything not
    covered by the internal knowledge base. Returns a summary of top results.
    
    Args:
        query: The web search query
        
    Returns:
        Summary of top web search results
    """
    from app.core.config import settings

    if not settings.tavily_api_key:
        return "Web search is not configured (missing TAVILY_API_KEY)."

    try:
        from tavily import AsyncTavilyClient

        client = AsyncTavilyClient(api_key=settings.tavily_api_key)
        resp = await client.search(query, max_results=5, search_depth="basic")
        results = resp.get("results", [])
        if not results:
            return "No results found on the web."

        lines = []
        for i, r in enumerate(results, start=1):
            title = r.get("title", "Untitled")
            url = r.get("url", "")
            content = r.get("content", "")
            lines.append(f"[{i}] {title}\n{url}\n{content[:600]}")
        return "\n\n---\n\n".join(lines)
    except Exception as exc:
        logger.exception("Tavily search failed")
        return f"Web search error: {exc}"
