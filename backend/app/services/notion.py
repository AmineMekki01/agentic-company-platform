import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.celery_app import celery_app
from app.core.config import settings
from app.core.encryption import EncryptionService
from app.services.parsers import parse_upload
from app.services.rag import RAGService

logger = logging.getLogger(__name__)


def _notion_client(token: str) -> Any:
    """
    Create a Notion API client.
    
    Args:
        token: Notion integration token
        
    Returns:
        Notion API client
    """
    from notion_client import Client
    return Client(auth=token)


def _get_token_from_connector(credentials_encrypted: str) -> str:
    """
    Decrypt connector credentials and extract the Notion integration token.
    
    Args:
        credentials_encrypted: Encrypted credentials string
        
    Returns:
        Notion integration token
    """
    crypto = EncryptionService()
    creds_str = crypto.decrypt(credentials_encrypted)
    try:
        creds = json.loads(creds_str)
    except json.JSONDecodeError:
        import ast
        creds = ast.literal_eval(creds_str)
    return creds.get("token") or creds.get("api_key") or creds.get("integration_token", "")


def fetch_database_pages(database_id: str, token: str) -> list[dict]:
    """
    Fetch all pages from a Notion database.
    
    Args:
        database_id: Notion database ID
        token: Notion integration token
        
    Returns:
        List of page objects
    """
    client = _notion_client(token)
    pages = []
    cursor = None
    while True:
        resp = client.databases.query(
            database_id=database_id, start_cursor=cursor, page_size=100
        )
        pages.extend(resp.get("results", []))
        cursor = resp.get("next_cursor")
        if not cursor:
            break
    return pages


def _extract_text_from_block(block: dict) -> str:
    """
    Recursively extract plain text from a Notion block.
    
    Args:
        block: Notion block object
        
    Returns:
        Extracted plain text
    """
    block_type = block.get("type", "")
    body = block.get(block_type, {})
    texts = [r.get("plain_text", "") for r in body.get("rich_text", [])]
    text = "".join(texts)

    children = block.get("children", [])
    if not children and body.get("children"):
        children = body.get("children", [])

    child_texts = [_extract_text_from_block(c) for c in children]
    child_text = "\n".join(c for c in child_texts if c)

    if child_text:
        return f"{text}\n{child_text}".strip()
    return text.strip()


def fetch_page_content(page_id: str, token: str) -> str:
    """
    Fetch all block content for a Notion page and return plain text.
    
    Args:
        page_id: Notion page ID
        token: Notion integration token
        
    Returns:
        Plain text content
    """
    client = _notion_client(token)
    blocks = []
    cursor = None
    while True:
        resp = client.blocks.children.list(page_id, start_cursor=cursor, page_size=100)
        blocks.extend(resp.get("results", []))
        cursor = resp.get("next_cursor")
        if not cursor:
            break

    parts = []
    for b in blocks:
        text = _extract_text_from_block(b)
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def _find_child_pages(page_id: str, token: str) -> list[dict]:
    """
    Recursively find all child_page blocks under a Notion page.
    
    Args:
        page_id: Notion page ID
        token: Notion integration token
        
    Returns:
        List of child page objects
    """
    client = _notion_client(token)
    children = []
    cursor = None
    while True:
        resp = client.blocks.children.list(page_id, start_cursor=cursor, page_size=100)
        for block in resp.get("results", []):
            if block.get("type") == "child_page":
                children.append({
                    "id": block["id"],
                    "title": block.get("child_page", {}).get("title", "Untitled"),
                })

            if block.get("has_children"):
                children.extend(_find_child_pages(block["id"], token))
        cursor = resp.get("next_cursor")
        if not cursor:
            break
    return children


async def _ingest_page_tree_async(
    page_id: str,
    title: str,
    source_title: str,
    token: str,
    rag: RAGService,
    visited: set[str] | None = None,
    knowledge_source_id: str | None = None,
    knowledge_source_slug: str | None = None,
) -> int:
    """
    Ingest a page and all its subpages recursively. Returns total chunks.
    
    Args:
        page_id: Notion page ID to ingest
        title: Page title
        source_title: Prefix for document titles in the RAG index
        token: Notion integration token
        rag: RAG service instance
        visited: Set of visited page IDs to prevent cycles
        knowledge_source_id: Optional knowledge source ID to associate with documents
        knowledge_source_slug: Optional slug for the knowledge source
        
    Returns:
        Total number of chunks ingested
    """
    if visited is None:
        visited = set()
    if page_id in visited:
        return 0
    visited.add(page_id)

    text = fetch_page_content(page_id, token)
    total = 0
    if text.strip():
        extra = {
            "knowledge_source_id": knowledge_source_id or knowledge_source_slug or source_title,
            "knowledge_source_slug": knowledge_source_slug or source_title,
            "knowledge_source_name": source_title,
            "source_type": "notion",
            "notion_page_id": page_id,
            "notion_page_url": f"https://www.notion.so/{page_id.replace('-', '')}",
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }
        total += await rag.ingest_document(
            source_id=uuid.UUID(page_id.replace("-", "")),
            title=f"{source_title} - {title}",
            content=text,
            extra_payload=extra,
        )

    for child in _find_child_pages(page_id, token):
        total += await _ingest_page_tree_async(
            child["id"],
            child["title"],
            source_title,
            token,
            rag,
            visited,
            knowledge_source_id,
            knowledge_source_slug,
        )

    return total


@celery_app.task(bind=True, max_retries=3)
def sync_notion_database(
    self, database_id: str, source_title: str, connector_credentials: str | None = None, knowledge_source_id: str | None = None, slug: str | None = None
) -> dict:
    """
    Celery task: sync a Notion database into the knowledge base.
    
    Args:
        database_id: Notion database ID to sync.
        source_title: Prefix for document titles in the RAG index.
        connector_credentials: Encrypted credentials string from a Connector row.
            If omitted, falls back to the deprecated global NOTION_TOKEN.
        knowledge_source_id: Optional knowledge source ID to associate with documents.
        slug: Optional slug for the knowledge source.
    
    Returns:
        Dictionary with sync results
    """
    slug = slug or source_title
    try:
        token = _resolve_token(connector_credentials)
        pages = fetch_database_pages(database_id, token)
        logger.info("Fetched %d pages from Notion DB %s", len(pages), database_id)

        async def _sync_all() -> int:
            rag = RAGService()

            await rag.delete_by_knowledge_source(knowledge_source_id or slug)
            total = 0
            for p in pages:
                page_id = p["id"]
                title = (
                    p.get("properties", {})
                    .get("Name", {})
                    .get("title", [{}])[0]
                    .get("plain_text", page_id)
                )
                text = fetch_page_content(page_id, token)
                if not text.strip():
                    continue
                extra = {
                    "knowledge_source_id": knowledge_source_id or slug,
                    "knowledge_source_slug": slug,
                    "knowledge_source_name": source_title,
                    "source_type": "notion",
                    "notion_page_id": page_id,
                    "notion_page_url": f"https://www.notion.so/{page_id.replace('-', '')}",
                    "ingested_at": datetime.now(timezone.utc).isoformat(),
                }
                chunks = await rag.ingest_document(
                    source_id=uuid.UUID(page_id.replace("-", "")),
                    title=f"{source_title} - {title}",
                    content=text,
                    extra_payload=extra,
                )
                total += chunks
            await _update_source_status(slug, total)
            return total

        total_chunks = asyncio.run(_sync_all())
        return {"status": "ok", "pages": len(pages), "chunks": total_chunks}
    except Exception as exc:
        logger.exception("Notion sync failed for DB %s", database_id)
        asyncio.run(_update_source_status(slug, 0, status="error"))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def sync_notion_page(
    self, page_id: str, page_title: str, source_title: str, connector_credentials: str | None = None, knowledge_source_id: str | None = None, slug: str | None = None
) -> dict:
    """Celery task: sync a Notion page (with all subpages) into the knowledge base.

    Args:
        page_id: Notion page ID to sync.
        page_title: Title of the root page.
        source_title: Prefix for document titles in the RAG index.
        connector_credentials: Encrypted credentials string from a Connector row.
        knowledge_source_id: Optional knowledge source ID to associate with documents.
        slug: Optional slug for the knowledge source.

    Returns:
        Dictionary with sync results
    """
    slug = slug or source_title
    try:
        token = _resolve_token(connector_credentials)

        async def _sync() -> int:
            rag = RAGService()

            await rag.delete_by_knowledge_source(knowledge_source_id or slug)
            total = await _ingest_page_tree_async(page_id, page_title, source_title, token, rag, knowledge_source_id=knowledge_source_id, knowledge_source_slug=slug)
            await _update_source_status(slug, total)
            return total

        total_chunks = asyncio.run(_sync())
        return {"status": "ok", "chunks": total_chunks}
    except Exception as exc:
        logger.exception("Notion page sync failed for page %s", page_id)
        asyncio.run(_update_source_status(slug, 0, status="error"))
        raise self.retry(exc=exc, countdown=60)


def _resolve_token(connector_credentials: str | None) -> str:
    """
    Resolve Notion token from connector credentials or global settings.
    
    Args:
        connector_credentials: Encrypted credentials string from a Connector row.
        
    Returns:
        Notion integration token
        
    Raises:
        RuntimeError: If no token is available
    """
    if connector_credentials:
        return _get_token_from_connector(connector_credentials)
    token = settings.notion_token
    if not token:
        raise RuntimeError("No Notion token available")
    return token


async def _update_source_status(slug: str, chunk_count: int, status: str = "ready") -> None:
    """
    Update KnowledgeSource status and chunk_count after sync.
    
    Args:
        slug: Knowledge source slug
        chunk_count: Number of chunks ingested
        status: Status to set (default: "ready")
    
    Raises:
        Exception: If database update fails
    """
    from app.db.session import async_session_factory
    from app.models import KnowledgeSource
    from sqlalchemy import select

    async with async_session_factory() as db:
        try:
            result = await db.execute(select(KnowledgeSource).where(KnowledgeSource.slug == slug))
            source = result.scalar_one_or_none()
            if source:
                source.status = status
                source.chunk_count = chunk_count
                source.last_sync_at = datetime.now(timezone.utc)
                await db.commit()
        except Exception:
            logger.exception("Failed to update source status for %s", slug)
            await db.rollback()
