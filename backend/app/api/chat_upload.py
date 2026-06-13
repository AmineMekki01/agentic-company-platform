"""Chat file upload endpoint."""

import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, UploadFile, status
from sqlalchemy import select

from app.api.conversations import get_owned_conversation
from app.api.deps import CurrentUser, DbSession
from app.core.encryption import EncryptionService
from app.models import ChatAttachment, Connector, UploadSettings
from app.schemas.chat import ChatAttachmentOut
from app.services.parsers import parse_upload

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


def _sanitize_filename(name: str) -> str:
    """Remove path traversal and unsafe chars from a filename."""
    name = re.sub(r"[^\w.\-]", "_", name)
    return name.strip("._") or "upload"


def _get_s3_client(credentials: dict):
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


@router.post("/chat/{conversation_id}/upload", response_model=ChatAttachmentOut)
async def upload_chat_file(
    conversation_id: uuid.UUID,
    file: UploadFile,
    user: CurrentUser,
    db: DbSession,
):
    """
    Upload a file into a chat conversation.

    The file is stored in S3 under the configured bucket/prefix.
    Extracted text is returned so the frontend can inline it into the message.
    """
    await get_owned_conversation(conversation_id, user.id, db)

    settings = await db.scalar(select(UploadSettings))
    if settings is None or not settings.enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File uploads are disabled",
        )

    if not settings.s3_bucket:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Upload bucket not configured",
        )

    content = await file.read()
    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.max_file_size_mb} MB limit",
        )

    connector = None
    if settings.s3_connector_id:
        connector = await db.scalar(
            select(Connector).where(Connector.id == settings.s3_connector_id)
        )
    if connector is None:
        connector = await db.scalar(
            select(Connector).where(Connector.connector_type == "s3")
        )
    if connector is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No S3 connector available for uploads",
        )

    crypto = EncryptionService()
    creds_str = crypto.decrypt(connector.credentials_encrypted)
    try:
        import json

        credentials = json.loads(creds_str)
    except Exception:
        import ast

        credentials = ast.literal_eval(creds_str)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_name = _sanitize_filename(file.filename or "upload")
    base_prefix = settings.s3_base_prefix
    if base_prefix and not base_prefix.endswith("/"):
        base_prefix += "/"
    s3_key = f"{base_prefix}{user.id}/{conversation_id}/{timestamp}_{safe_name}"

    s3_client = _get_s3_client(credentials)
    extra_args = {}
    if settings.encryption == "AES256":
        extra_args["ServerSideEncryption"] = "AES256"
    elif settings.encryption == "aws:kms":
        extra_args["ServerSideEncryption"] = "aws:kms"

    s3_client.put_object(
        Bucket=settings.s3_bucket,
        Key=s3_key,
        Body=content,
        ContentType=file.content_type or "application/octet-stream",
        Metadata={
            "user_id": str(user.id),
            "conversation_id": str(conversation_id),
            "original_name": file.filename or "upload",
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        },
        **extra_args,
    )

    text = ""
    try:
        text = parse_upload(content, file.content_type, file.filename or "")
    except Exception:
        logger.exception("Failed to extract text from uploaded file")

    retention_until = None
    if settings.retention_days > 0:
        retention_until = datetime.now(timezone.utc) + timedelta(days=settings.retention_days)

    attachment = ChatAttachment(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        user_id=user.id,
        filename=file.filename or "upload",
        mime_type=file.content_type,
        file_size=len(content),
        s3_bucket=settings.s3_bucket,
        s3_key=s3_key,
        extracted_text=text or None,
        retention_until=retention_until,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)

    return ChatAttachmentOut(
        id=attachment.id,
        filename=attachment.filename,
        mime_type=attachment.mime_type,
        file_size=attachment.file_size,
        extracted_text=attachment.extracted_text,
        created_at=attachment.created_at,
    )
