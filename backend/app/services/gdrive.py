"""Google Drive connector: sync files from Drive folders into the knowledge base."""

import asyncio
import io
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.celery_app import celery_app
from app.core.encryption import EncryptionService
from app.services.parsers import _detect_file_type, parse_upload
from app.services.rag import RAGService

logger = logging.getLogger(__name__)

SUPPORTED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
    "text/csv",
    "text/markdown",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.google-apps.document",
    "application/vnd.google-apps.spreadsheet",
    "application/vnd.google-apps.presentation",
}

EXPORT_MIME_MAP = {
    "application/vnd.google-apps.document": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}

FILE_EXTENSION_MAP = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
    "text/plain": ".txt",
    "text/csv": ".csv",
    "text/markdown": ".md",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
}


def _get_drive_service(credentials_encrypted: str):
    """Build a Google Drive API service from encrypted connector credentials."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    crypto = EncryptionService()
    creds_str = crypto.decrypt(credentials_encrypted)
    try:
        creds_dict = json.loads(creds_str)
    except json.JSONDecodeError:
        import ast
        creds_dict = ast.literal_eval(creds_str)

    if isinstance(creds_dict, str):
        creds_dict = json.loads(creds_dict)

    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    delegated_user = creds_dict.pop("delegated_user", None)

    sa_json_str = creds_dict.get("service_account_json") or creds_dict.get("service_account") or ""
    if isinstance(sa_json_str, str) and sa_json_str.strip():
        sa_info = json.loads(sa_json_str)
    elif isinstance(sa_json_str, dict):
        sa_info = sa_json_str
    else:
        sa_info = creds_dict

    credentials = service_account.Credentials.from_service_account_info(
        sa_info, scopes=scopes
    )
    if delegated_user:
        credentials = credentials.with_subject(delegated_user)

    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def _list_folder_files(service, folder_id: str) -> list[dict]:
    """Recursively list all supported files under a Drive folder."""
    files: list[dict] = []

    def _walk(parent_id: str):
        page_token = None
        while True:
            resp = (
                service.files()
                .list(
                    q=f"'{parent_id}' in parents and trashed = false",
                    fields="nextPageToken, files(id, name, mimeType, modifiedTime, webViewLink)",
                    pageSize=200,
                    pageToken=page_token,
                )
                .execute()
            )
            for item in resp.get("files", []):
                mime = item.get("mimeType", "")
                if mime == "application/vnd.google-apps.folder":
                    _walk(item["id"])
                elif mime in SUPPORTED_MIME_TYPES:
                    files.append(item)
                else:
                    logger.debug("Skipping unsupported file: %s (%s)", item.get("name"), mime)

            page_token = resp.get("nextPageToken")
            if not page_token:
                break

    _walk(folder_id)
    return files


def _download_file_content(service, file_id: str, mime_type: str) -> tuple[bytes, str]:
    """Download or export a file. Returns (content_bytes, effective_mime_type)."""
    if mime_type in EXPORT_MIME_MAP:
        export_mime = EXPORT_MIME_MAP[mime_type]
        request = service.files().export_media(fileId=file_id, mimeType=export_mime)
        content = request.execute()
        return content, export_mime

    request = service.files().get_media(fileId=file_id)
    content = request.execute()
    return content, mime_type


def _extract_text(content: bytes, mime_type: str, filename: str) -> str:
    """Extract plain text from downloaded content."""
    ext = FILE_EXTENSION_MAP.get(mime_type, "")
    fn = filename if filename.endswith(ext) else filename + ext
    return parse_upload(content, mime_type, fn)


@celery_app.task(bind=True, max_retries=3)
def sync_gdrive_folder(
    self,
    folder_id: str,
    source_title: str,
    connector_credentials: str,
    knowledge_source_id: str | None = None,
    slug: str | None = None,
    force_full: bool = False,
) -> dict:
    """Celery task: sync all files under a Google Drive folder into the knowledge base.

    Incremental by default: only downloads and re-embeds files that are new or modified
    since the last sync. Set force_full=True to delete and re-ingest everything.
    """
    slug = slug or source_title
    try:
        service = _get_drive_service(connector_credentials)
        files = _list_folder_files(service, folder_id)
        logger.info("Found %d supported files in Google Drive folder %s", len(files), folder_id)

        if not files:
            asyncio.run(_update_source_status(slug, 0))
            return {"status": "ok", "files": 0, "chunks": 0}

        async def _sync_all() -> int:
            rag = RAGService()
            ks_id = knowledge_source_id or slug

            if force_full:
                await rag.delete_by_knowledge_source(ks_id)
                existing: dict[str, dict[str, Any]] = {}
            else:
                existing = await rag.get_source_metadata(ks_id)

            source_file_map: dict[str, dict] = {}
            for f in files:
                sid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"gdrive://{f['id']}"))
                source_file_map[sid] = f

            total = 0
            skipped = 0
            for sid_str, f in source_file_map.items():
                file_id = f["id"]
                name = f.get("name", file_id)
                mime = f.get("mimeType", "")
                modified = f.get("modifiedTime", "")

                prev = existing.get(sid_str)
                if prev and prev.get("source_modified_at") == modified:
                    total += prev["chunk_count"]
                    skipped += 1
                    continue

                try:
                    if prev:
                        await rag.delete_by_source_id(ks_id, sid_str)

                    content, effective_mime = _download_file_content(service, file_id, mime)
                    text = _extract_text(content, effective_mime, name)
                    if not text.strip():
                        logger.info("Empty content for %s, skipping", name)
                        continue

                    extra = {
                        "knowledge_source_slug": slug,
                        "knowledge_source_name": source_title,
                        "source_type": "gdrive",
                        "gdrive_file_id": file_id,
                        "gdrive_file_url": f.get("webViewLink"),
                        "gdrive_folder_id": folder_id,
                        "file_name": name,
                        "file_type": _detect_file_type(effective_mime, name),
                        "source_modified_at": modified,
                        "ingested_at": datetime.now(timezone.utc).isoformat(),
                    }
                    chunks = await rag.ingest_document(
                        source_id=uuid.UUID(sid_str),
                        title=f"{source_title} - {name}",
                        content=text,
                        knowledge_source_id=ks_id,
                        extra_payload=extra,
                    )
                    total += chunks
                except Exception:
                    logger.exception("Failed to ingest Google Drive file %s", name)
                    continue

            for sid_str in existing:
                if sid_str not in source_file_map:
                    await rag.delete_by_source_id(ks_id, sid_str)

            await _update_source_status(slug, total)
            logger.info("Google Drive sync complete: %d total chunks, %d files skipped (unchanged)", total, skipped)
            return total

        total_chunks = asyncio.run(_sync_all())
        return {"status": "ok", "files": len(files), "chunks": total_chunks}
    except Exception as exc:
        logger.exception("Google Drive sync failed for folder %s", folder_id)
        asyncio.run(_update_source_status(slug, 0, status="error"))
        raise self.retry(exc=exc, countdown=60)


async def _update_source_status(slug: str, chunk_count: int, status: str = "ready") -> None:
    """Update KnowledgeSource status and chunk_count after sync."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.core.config import settings
    from app.models import KnowledgeSource

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with session_factory() as db:
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
    finally:
        await engine.dispose()
