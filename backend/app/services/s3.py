import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.celery_app import celery_app
from app.core.encryption import EncryptionService
from app.db.celery_session import run_async
from app.tasks.base import TenantTask
from app.services.parsers import _detect_file_type, parse_upload
from app.services.rag import get_rag_service

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".doc", ".txt", ".md", ".csv", ".xlsx")


def _get_s3_client(credentials: dict[str, Any]):
    """
    Build a boto3 S3 client from decrypted credentials.

    Args:
        credentials: Decrypted S3 credentials dictionary
        
    Returns:
        boto3.S3.Client: Configured S3 client
    """
    import boto3

    kwargs = {
        "aws_access_key_id": credentials.get("access_key"),
        "aws_secret_access_key": credentials.get("secret_key"),
        "region_name": credentials.get("region", "us-east-1"),
    }
    endpoint = credentials.get("endpoint_url")
    if endpoint:
        kwargs["endpoint_url"] = endpoint

    return boto3.client("s3", **kwargs)


def _decrypt_credentials(credentials_encrypted: str) -> dict[str, Any]:
    """
    Decrypt and parse connector credentials.
    
    Args:
        credentials_encrypted: Encrypted credentials string
        
    Returns:
        dict[str, Any]: Decrypted credentials dictionary
    """
    crypto = EncryptionService()
    creds_str = crypto.decrypt(credentials_encrypted)
    try:
        return json.loads(creds_str)
    except json.JSONDecodeError:
        import ast
        return ast.literal_eval(creds_str)


def _list_objects(client, bucket: str, prefix: str) -> list[dict]:
    """
    List all objects under the given prefix. Returns list of dicts with Key and Size.
    
    Args:
        client: boto3 S3 client
        bucket: S3 bucket name
        prefix: Object key prefix to filter
        
    Returns:
        list[dict]: List of object dictionaries with Key and Size
    """
    paginator = client.get_paginator("list_objects_v2")
    objects = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key: str = obj["Key"]
            if key.endswith("/"):
                continue
            if not key.lower().endswith(SUPPORTED_EXTENSIONS):
                logger.info("Skipping unsupported file: %s", key)
                continue
            objects.append(obj)
    return objects


def _download_object(client, bucket: str, key: str) -> bytes:
    """
    Download an object from S3.
    
    Args:
        client: boto3 S3 client
        bucket: S3 bucket name
        key: Object key to download
        
    Returns:
        bytes: Object content
    """
    resp = client.get_object(Bucket=bucket, Key=key)
    return resp["Body"].read()


def _build_s3_url(credentials: dict[str, Any], bucket: str, key: str) -> str:
    """
    Build a public or virtual-hosted S3 URL for the object.
    
    Args:
        credentials: S3 credentials dictionary
        bucket: S3 bucket name
        key: Object key
        
    Returns:
        str: S3 URL
    """
    endpoint = credentials.get("endpoint_url")
    if endpoint:
        return f"{endpoint.rstrip('/')}/{bucket}/{key}"
    region = credentials.get("region", "us-east-1")
    if region == "us-east-1":
        return f"https://s3.amazonaws.com/{bucket}/{key}"
    return f"https://s3.{region}.amazonaws.com/{bucket}/{key}"


@celery_app.task(bind=True, base=TenantTask, max_retries=3)
def sync_s3_prefix(
    self,
    bucket: str,
    prefix: str,
    source_title: str,
    connector_credentials: str,
    knowledge_source_id: str | None = None,
    slug: str | None = None,
    force_full: bool = False,
    tenant_id: str | None = None,
) -> dict:
    """Celery task: sync all files under an S3 prefix into the knowledge base.

    Incremental by default: only downloads and re-embeds objects that are new or modified
    since the last sync. Set force_full=True to delete and re-ingest everything.

    Args:
        bucket: S3 bucket name.
        prefix: Path prefix (folder) inside the bucket.
        source_title: Prefix for document titles in the RAG index.
        connector_credentials: Encrypted credentials string from a Connector row.
        knowledge_source_id: UUID of the KnowledgeSource row.
        slug: Knowledge source slug for status updates.
        force_full: If True, delete all and re-ingest from scratch.
    
    Returns:
        dict: Sync results with status, objects count, and chunks count
    """
    slug = slug or source_title
    try:
        creds = _decrypt_credentials(connector_credentials)
        client = _get_s3_client(creds)

        objects = _list_objects(client, bucket, prefix)
        logger.info("Found %d supported objects under s3://%s/%s", len(objects), bucket, prefix)

        if not objects:
            run_async(_update_source_status(slug, 0))
            return {"status": "ok", "objects": 0, "chunks": 0}

        async def _sync_all() -> int:
            rag = get_rag_service()
            ks_id = knowledge_source_id or slug

            if force_full:
                await rag.delete_by_knowledge_source(ks_id)
                existing: dict[str, dict[str, Any]] = {}
            else:
                existing = await rag.get_source_metadata(ks_id)

            source_obj_map: dict[str, dict] = {}
            for obj in objects:
                key: str = obj["Key"]
                sid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"s3://{bucket}/{key}"))
                source_obj_map[sid] = obj

            total = 0
            skipped = 0
            for sid_str, obj in source_obj_map.items():
                key = obj["Key"]
                modified = obj.get("LastModified")
                modified_str = modified.isoformat() if hasattr(modified, "isoformat") else str(modified)

                prev = existing.get(sid_str)
                if prev and prev.get("source_modified_at") == modified_str:
                    total += prev["chunk_count"]
                    skipped += 1
                    continue

                try:
                    if prev:
                        await rag.delete_by_source_id(ks_id, sid_str)

                    content = _download_object(client, bucket, key)
                    text = parse_upload(content, None, key)
                    if not text.strip():
                        logger.info("Empty content for %s, skipping", key)
                        continue

                    source_url = _build_s3_url(creds, bucket, key)
                    extra = {
                        "knowledge_source_slug": slug,
                        "knowledge_source_name": source_title,
                        "source_type": "s3",
                        "s3_bucket": bucket,
                        "s3_key": key,
                        "file_name": key.split("/")[-1],
                        "file_type": _detect_file_type("", key),
                        "source_url": source_url,
                        "source_modified_at": modified_str,
                        "ingested_at": datetime.now(timezone.utc).isoformat(),
                    }
                    chunks = await rag.ingest_document(
                        source_id=uuid.UUID(sid_str),
                        title=f"{source_title} - {key}",
                        content=text,
                        knowledge_source_id=ks_id,
                        extra_payload=extra,
                    )
                    total += chunks
                except Exception:
                    logger.exception("Failed to ingest S3 object %s", key)
                    continue

            for sid_str in existing:
                if sid_str not in source_obj_map:
                    await rag.delete_by_source_id(ks_id, sid_str)

            await _update_source_status(slug, total)
            logger.info("S3 sync complete: %d total chunks, %d objects skipped (unchanged)", total, skipped)
            return total

        total_chunks = run_async(_sync_all())
        return {"status": "ok", "objects": len(objects), "chunks": total_chunks}
    except Exception as exc:
        logger.exception("S3 sync failed for s3://%s/%s", bucket, prefix)
        run_async(_update_source_status(slug, 0, status="error"))
        raise self.retry(exc=exc, countdown=60)


async def _update_source_status(slug: str, chunk_count: int, status: str = "ready") -> None:
    """Update KnowledgeSource status and chunk_count after sync."""
    from sqlalchemy import select

    from app.db.celery_session import tenant_scoped_session
    from app.models import KnowledgeSource

    async with tenant_scoped_session() as db:
        try:
            result = await db.execute(
                select(KnowledgeSource).where(KnowledgeSource.slug == slug)
            )
            source = result.scalar_one_or_none()
            if source:
                source.status = status
                source.chunk_count = chunk_count
                source.last_sync_at = datetime.now(timezone.utc)
                await db.commit()
        except Exception:
            logger.exception("Failed to update source status for %s", slug)
            await db.rollback()
