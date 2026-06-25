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


def _fetch_page_metadata(page_id: str, token: str) -> dict:
    """Fetch a Notion page's metadata (last_edited_time, title)."""
    client = _notion_client(token)
    try:
        page = client.pages.retrieve(page_id)
        return {
            "last_edited_time": page.get("last_edited_time", ""),
            "title": (
                page.get("properties", {})
                .get("title", {})
                .get("title", [{}])[0]
                .get("plain_text", page_id)
                if page.get("properties")
                else page.get("url", "").split("/")[-1] if page.get("url") else page_id
            ),
        }
    except Exception:
        logger.exception("Failed to fetch Notion page metadata for %s", page_id)
        return {"last_edited_time": "", "title": page_id}


async def _ingest_page_tree_async(
    page_id: str,
    title: str,
    source_title: str,
    token: str,
    rag: RAGService,
    visited: set[str] | None = None,
    knowledge_source_id: str | None = None,
    knowledge_source_slug: str | None = None,
    existing_metadata: dict[str, dict[str, Any]] | None = None,
    ks_id: str | None = None,
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
        existing_metadata: Existing document metadata from Qdrant for incremental sync
        ks_id: Resolved knowledge source ID for incremental operations
        
    Returns:
        Total number of chunks ingested
    """
    if visited is None:
        visited = set()
    if page_id in visited:
        return 0
    visited.add(page_id)

    meta = _fetch_page_metadata(page_id, token)
    last_edited = meta.get("last_edited_time", "")
    sid_str = str(uuid.UUID(page_id.replace("-", "")))

    # unchanged ?
    if existing_metadata is not None and ks_id is not None:
        prev = existing_metadata.get(sid_str)
        if prev and prev.get("source_modified_at") == last_edited and last_edited:
            # unchanged , we count and skip
            return prev["chunk_count"]

    text = fetch_page_content(page_id, token)
    total = 0
    if text.strip():
        # delete old chunks if this document existed
        if existing_metadata is not None and ks_id is not None:
            prev = existing_metadata.get(sid_str)
            if prev:
                await rag.delete_by_source_id(ks_id, sid_str)

        resolved_ks_id = ks_id or knowledge_source_id or knowledge_source_slug or source_title
        extra = {
            "knowledge_source_slug": knowledge_source_slug or source_title,
            "knowledge_source_name": source_title,
            "source_type": "notion",
            "notion_page_id": page_id,
            "notion_page_url": f"https://www.notion.so/{page_id.replace('-', '')}",
            "file_name": title,
            "file_type": "notion_page",
            "source_modified_at": last_edited,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }
        total += await rag.ingest_document(
            source_id=uuid.UUID(page_id.replace("-", "")),
            title=f"{source_title} - {title}",
            content=text,
            knowledge_source_id=resolved_ks_id,
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
            existing_metadata,
            ks_id,
        )

    return total


@celery_app.task(bind=True, max_retries=3)
def sync_notion_database(
    self, database_id: str, source_title: str, connector_credentials: str | None = None, knowledge_source_id: str | None = None, slug: str | None = None, force_full: bool = False
) -> dict:
    """
    Celery task: sync a Notion database into the knowledge base.
    
    Incremental by default: only fetches and re-embeds pages that are new or modified
    since the last sync. Set force_full=True to delete and re-ingest everything.
    
    Args:
        database_id: Notion database ID to sync.
        source_title: Prefix for document titles in the RAG index.
        connector_credentials: Encrypted credentials string from a Connector row.
            If omitted, falls back to the deprecated global NOTION_TOKEN.
        knowledge_source_id: Optional knowledge source ID to associate with documents.
        slug: Optional slug for the knowledge source.
        force_full: If True, delete all and re-ingest from scratch.
    
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
            ks_id = knowledge_source_id or slug

            if force_full:
                await rag.delete_by_knowledge_source(ks_id)
                existing: dict[str, dict[str, Any]] = {}
            else:
                existing = await rag.get_source_metadata(ks_id)

            source_page_map: dict[str, dict] = {}
            for p in pages:
                page_id = p["id"]
                sid = str(uuid.UUID(page_id.replace("-", "")))
                source_page_map[sid] = p

            total = 0
            skipped = 0
            for sid_str, p in source_page_map.items():
                page_id = p["id"]
                title = (
                    p.get("properties", {})
                    .get("Name", {})
                    .get("title", [{}])[0]
                    .get("plain_text", page_id)
                )
                last_edited = p.get("last_edited_time", "")

                # Skip unchanged pages
                prev = existing.get(sid_str)
                if prev and prev.get("source_modified_at") == last_edited and last_edited:
                    total += prev["chunk_count"]
                    skipped += 1
                    continue

                try:
                    if prev:
                        await rag.delete_by_source_id(ks_id, sid_str)

                    text = fetch_page_content(page_id, token)
                    if not text.strip():
                        continue
                    extra = {
                        "knowledge_source_slug": slug,
                        "knowledge_source_name": source_title,
                        "source_type": "notion",
                        "notion_page_id": page_id,
                        "notion_page_url": f"https://www.notion.so/{page_id.replace('-', '')}",
                        "file_name": title,
                        "file_type": "notion_page",
                        "source_modified_at": last_edited,
                        "ingested_at": datetime.now(timezone.utc).isoformat(),
                    }
                    chunks = await rag.ingest_document(
                        source_id=uuid.UUID(page_id.replace("-", "")),
                        title=f"{source_title} - {title}",
                        content=text,
                        knowledge_source_id=ks_id,
                        extra_payload=extra,
                    )
                    total += chunks
                except Exception:
                    logger.exception("Failed to ingest Notion page %s", page_id)
                    continue

            for sid_str in existing:
                if sid_str not in source_page_map:
                    await rag.delete_by_source_id(ks_id, sid_str)

            await _update_source_status(slug, total)
            logger.info("Notion DB sync complete: %d total chunks, %d pages skipped (unchanged)", total, skipped)
            return total

        total_chunks = asyncio.run(_sync_all())
        return {"status": "ok", "pages": len(pages), "chunks": total_chunks}
    except Exception as exc:
        logger.exception("Notion sync failed for DB %s", database_id)
        asyncio.run(_update_source_status(slug, 0, status="error"))
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(bind=True, max_retries=3)
def sync_notion_page(
    self, page_id: str, page_title: str, source_title: str, connector_credentials: str | None = None, knowledge_source_id: str | None = None, slug: str | None = None, force_full: bool = False
) -> dict:
    """Celery task: sync a Notion page (with all subpages) into the knowledge base.

    Incremental by default: only fetches and re-embeds pages that are new or modified
    since the last sync. Set force_full=True to delete and re-ingest everything.

    Args:
        page_id: Notion page ID to sync.
        page_title: Title of the root page.
        source_title: Prefix for document titles in the RAG index.
        connector_credentials: Encrypted credentials string from a Connector row.
        knowledge_source_id: Optional knowledge source ID to associate with documents.
        slug: Optional slug for the knowledge source.
        force_full: If True, delete all and re-ingest from scratch.

    Returns:
        Dictionary with sync results
    """
    slug = slug or source_title
    try:
        token = _resolve_token(connector_credentials)

        async def _sync() -> int:
            rag = RAGService()
            ks_id = knowledge_source_id or slug

            if force_full:
                await rag.delete_by_knowledge_source(ks_id)
                existing: dict[str, dict[str, Any]] | None = None
            else:
                existing = await rag.get_source_metadata(ks_id)

            total = await _ingest_page_tree_async(
                page_id, page_title, source_title, token, rag,
                knowledge_source_id=knowledge_source_id,
                knowledge_source_slug=slug,
                existing_metadata=existing,
                ks_id=ks_id if existing is not None else None,
            )
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
