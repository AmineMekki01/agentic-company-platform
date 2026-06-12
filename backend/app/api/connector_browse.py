"""Browse Notion content (databases, pages) and S3 buckets from a connector credential."""

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from notion_client import Client
from notion_client.errors import APIResponseError
from sqlalchemy import select

from app.api.deps import AdminUser, DbSession
from app.core.encryption import EncryptionService
from app.models import Connector
from app.schemas.connector import NotionResource, S3Bucket
from app.services.s3 import _decrypt_credentials, _get_s3_client

router = APIRouter(prefix="/admin/connectors/{slug}/browse", tags=["admin"])


def _get_notion_client(connector: Connector) -> Any:
    """
    Get a Notion client from the connector.
    
    Args:
        connector: The connector to get the client from
        
    Returns:
        Notion client
        
    Raises:
        HTTPException: If no Notion token is found in the connector credentials
    """
    crypto = EncryptionService()
    creds_str = crypto.decrypt(connector.credentials_encrypted)
    creds = json.loads(creds_str.replace("'", '"'))
    token = creds.get("token") or creds.get("api_key") or creds.get("integration_token")
    if not token:
        raise HTTPException(status_code=400, detail="No Notion token found in connector credentials")
    return Client(auth=token)


def _handle_notion_error(exc: APIResponseError) -> None:
    """
    Convert Notion API errors into proper HTTPExceptions.
    
    Args:
        exc: The Notion API response error
        
    Raises:
        HTTPException: With appropriate status code and detail message
    """
    if exc.code == "unauthorized":
        raise HTTPException(status_code=401, detail="Invalid Notion API token")
    if exc.code == "restricted_resource":
        raise HTTPException(status_code=403, detail="Notion token lacks access to this resource")
    raise HTTPException(status_code=502, detail=f"Notion API error: {exc.code}")


@router.get("/notion/databases", response_model=list[NotionResource])
async def list_notion_databases(
    slug: str,
    user: AdminUser,
    db: DbSession,
) -> list[NotionResource]:
    """
    List all databases accessible by this Notion connector.
    
    Args:
        slug: The connector slug
        user: The authenticated admin user
        db: Database session
        
    Returns:
        List of NotionResource objects representing databases
        
    Raises:
        HTTPException: If connector not found or not a Notion connector
    """
    conn = await db.scalar(select(Connector).where(Connector.slug == slug))
    if conn is None:
        raise HTTPException(status_code=404, detail="Connector not found")
    if conn.connector_type != "notion":
        raise HTTPException(status_code=400, detail="Connector is not a Notion connector")

    client = _get_notion_client(conn)
    results = []
    cursor = None
    try:
        while True:
            resp = client.search(start_cursor=cursor, page_size=100)
            for item in resp.get("results", []):
                obj_type = item.get("object")
                if obj_type not in ("database", "data_source"):
                    continue

                try:
                    full = client.databases.retrieve(item["id"])
                    title_data = full.get("title", [])
                except Exception:
                    title_data = item.get("title", [])
                name = "".join(t.get("plain_text", "") for t in title_data) or "Untitled"
                results.append(
                    NotionResource(
                        id=item["id"],
                        name=name,
                        type="database",
                        url=item.get("url"),
                    )
                )
            cursor = resp.get("next_cursor")
            if not cursor:
                break
    except APIResponseError as exc:
        _handle_notion_error(exc)

    return results


@router.get("/notion/databases/{database_id}/pages", response_model=list[NotionResource])
async def list_notion_database_pages(
    slug: str,
    database_id: str,
    user: AdminUser,
    db: DbSession,
) -> list[NotionResource]:
    """
    List all pages within a specific Notion database.
    
    Args:
        slug: The connector slug
        database_id: The Notion database ID
        user: The authenticated admin user
        db: Database session
        
    Returns:
        List of NotionResource objects representing pages in the database
        
    Raises:
        HTTPException: If connector not found or not a Notion connector
    """
    conn = await db.scalar(select(Connector).where(Connector.slug == slug))
    if conn is None:
        raise HTTPException(status_code=404, detail="Connector not found")
    if conn.connector_type != "notion":
        raise HTTPException(status_code=400, detail="Connector is not a Notion connector")

    client = _get_notion_client(conn)
    results = []
    cursor = None
    try:
        while True:
            resp = client.databases.query(database_id=database_id, start_cursor=cursor, page_size=100)
            for item in resp.get("results", []):
                props = item.get("properties", {})
                name = "Untitled"

                for key in ["Name", "Title", "name", "title"]:
                    if key in props and "title" in props[key]:
                        parts = [t.get("plain_text", "") for t in props[key]["title"]]
                        name = "".join(parts) or "Untitled"
                        break
                results.append(
                    NotionResource(
                        id=item["id"],
                        name=name,
                        type="page",
                        url=item.get("url"),
                    )
                )
            cursor = resp.get("next_cursor")
            if not cursor:
                break
    except APIResponseError as exc:
        _handle_notion_error(exc)

    return results


@router.get("/notion/pages", response_model=list[NotionResource])
async def list_notion_pages(
    slug: str,
    user: AdminUser,
    db: DbSession,
) -> list[NotionResource]:
    """
    List top-level pages accessible by this Notion connector.
    
    Args:
        slug: The connector slug
        user: The authenticated admin user
        db: Database session
        
    Returns:
        List of NotionResource objects representing top-level pages
        
    Raises:
        HTTPException: If connector not found or not a Notion connector
    """
    conn = await db.scalar(select(Connector).where(Connector.slug == slug))
    if conn is None:
        raise HTTPException(status_code=404, detail="Connector not found")
    if conn.connector_type != "notion":
        raise HTTPException(status_code=400, detail="Connector is not a Notion connector")

    client = _get_notion_client(conn)
    results = []
    cursor = None
    count = 0
    max_results = 20
    try:
        while True:
            resp = client.search(start_cursor=cursor, page_size=100)
            for item in resp.get("results", []):
                if item.get("object") != "page":
                    continue

                parent = item.get("parent", {})
                if parent.get("type") != "workspace":
                    continue

                try:
                    full = client.pages.retrieve(item["id"])
                    props = full.get("properties", {})
                    title_data = props.get("title", {}).get("title", [])
                    name = "".join(t.get("plain_text", "") for t in title_data) or "Untitled"
                except Exception:
                    name = "Untitled"
                results.append(
                    NotionResource(
                        id=item["id"],
                        name=name,
                        type="page",
                        url=item.get("url"),
                    )
                )
                count += 1
                if count >= max_results:
                    break
            cursor = resp.get("next_cursor")
            if not cursor or count >= max_results:
                break
    except APIResponseError as exc:
        _handle_notion_error(exc)

    return results


@router.get("/notion/pages/{page_id}/children", response_model=list[NotionResource])
async def list_notion_page_children(
    slug: str,
    page_id: str,
    user: AdminUser,
    db: DbSession,
) -> list[NotionResource]:
    """
    List child pages of a specific Notion page.
    
    Args:
        slug: The connector slug
        page_id: The Notion page ID
        user: The authenticated admin user
        db: Database session
        
    Returns:
        List of NotionResource objects representing child pages
        
    Raises:
        HTTPException: If connector not found or not a Notion connector
    """
    conn = await db.scalar(select(Connector).where(Connector.slug == slug))
    if conn is None:
        raise HTTPException(status_code=404, detail="Connector not found")
    if conn.connector_type != "notion":
        raise HTTPException(status_code=400, detail="Connector is not a Notion connector")

    client = _get_notion_client(conn)
    results = []
    cursor = None
    try:
        while True:
            resp = client.blocks.children.list(page_id, start_cursor=cursor, page_size=100)
            for block in resp.get("results", []):
                if block.get("type") == "child_page":
                    child = block.get("child_page", {})
                    results.append(
                        NotionResource(
                            id=block["id"],
                            name=child.get("title", "Untitled"),
                            type="page",
                            url=None,
                        )
                    )
            cursor = resp.get("next_cursor")
            if not cursor:
                break
    except APIResponseError as exc:
        _handle_notion_error(exc)

    return results


@router.get("/notion/debug", response_model=dict)
async def debug_notion_search(
    slug: str,
    user: AdminUser,
    db: DbSession,
) -> dict:
    """
    Debug: dump raw Notion search results to diagnose browse issues.
    
    Args:
        slug: The connector slug
        user: The authenticated admin user
        db: Database session
        
    Returns:
        Dictionary with raw search results and enriched data
        
    Raises:
        HTTPException: If connector not found or not a Notion connector
    """
    conn = await db.scalar(select(Connector).where(Connector.slug == slug))
    if conn is None:
        raise HTTPException(status_code=404, detail="Connector not found")
    if conn.connector_type != "notion":
        raise HTTPException(status_code=400, detail="Connector is not a Notion connector")

    client = _get_notion_client(conn)
    try:
        resp = client.search(page_size=10)
        raw = resp.get("results", [])[:3]

        enriched = []
        for r in raw:
            obj_type = r.get("object")
            rid = r.get("id")
            title = None
            try:
                if obj_type == "database":
                    full = client.databases.retrieve(rid)
                    title = [t.get("plain_text", "") for t in full.get("title", [])]
                elif obj_type == "page":
                    full = client.pages.retrieve(rid)
                    title = [
                        t.get("plain_text", "")
                        for t in full.get("properties", {}).get("title", {}).get("title", [])
                    ]
            except Exception:
                pass
            enriched.append({
                "object": obj_type,
                "id": rid,
                "title_from_search": r.get("title") if obj_type == "database" else r.get("properties", {}).get("title"),
                "title_from_retrieve": title,
                "keys": list(r.keys()),
            })
        return {
            "has_more": resp.get("has_more"),
            "next_cursor": resp.get("next_cursor"),
            "results": enriched,
        }
    except APIResponseError as exc:
        _handle_notion_error(exc)


@router.get("/s3/buckets", response_model=list[S3Bucket])
async def list_s3_buckets(
    slug: str,
    user: AdminUser,
    db: DbSession,
) -> list[S3Bucket]:
    """
    List all S3 buckets accessible by this S3 connector.

    Args:
        slug: The connector slug
        user: The authenticated admin user
        db: Database session

    Returns:
        List of S3Bucket objects

    Raises:
        HTTPException: If connector not found or not an S3 connector
    """
    conn = await db.scalar(select(Connector).where(Connector.slug == slug))
    if conn is None:
        raise HTTPException(status_code=404, detail="Connector not found")
    if conn.connector_type != "s3":
        raise HTTPException(status_code=400, detail="Connector is not an S3 connector")

    try:
        creds = _decrypt_credentials(conn.credentials_encrypted)
        client = _get_s3_client(creds)
        resp = client.list_buckets()
        buckets = resp.get("Buckets", [])
        return [
            S3Bucket(
                name=b["Name"],
                created_at=b.get("CreationDate"),
            )
            for b in buckets
        ]
    except Exception as exc:
        logger = logging.getLogger(__name__)
        logger.exception("Failed to list S3 buckets for connector %s", slug)
        raise HTTPException(status_code=502, detail=f"S3 error: {exc}")
