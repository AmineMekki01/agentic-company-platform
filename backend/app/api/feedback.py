"""Message feedback endpoints."""

import logging
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

import re
from datetime import datetime, timedelta, timezone

from fastapi import UploadFile

from app.api.conversations import get_owned_conversation
from app.api.deps import AdminUser, CurrentUser, DbSession
from app.core.encryption import EncryptionService
from app.models import (
    Conversation,
    FeedbackAttachment,
    Message,
    MessageFeedback,
    UploadSettings,
    User,
)
from app.schemas.chat import (
    AgentFeedbackSummary,
    ChatAttachmentOut,
    MessageFeedbackCreate,
    MessageFeedbackOut,
    MessageFeedbackUserOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["feedback"])


@router.post("/chat/{conversation_id}/messages/{message_id}/feedback")
async def submit_feedback(
    conversation_id: uuid.UUID,
    message_id: uuid.UUID,
    body: MessageFeedbackCreate,
    user: CurrentUser,
    db: DbSession,
) -> MessageFeedbackUserOut:
    """
    Submit thumbs up/down feedback for an assistant message.
    One feedback per user per message (upsert).
    """
    # Verify conversation ownership
    await get_owned_conversation(conversation_id, user.id, db)

    # Verify message exists, is assistant role, belongs to conversation
    message = await db.get(Message, message_id)
    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Message not found"
        )
    if message.conversation_id != conversation_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message does not belong to this conversation",
        )
    if message.role != "assistant":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Feedback can only be submitted on assistant messages",
        )

    # Validate screenshot attachment exists and belongs to this user
    if body.screenshot_attachment_id:
        att = await db.get(FeedbackAttachment, body.screenshot_attachment_id)
        if att is None or att.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid screenshot attachment",
            )

    # Build conversation snapshot (all messages in conversation)
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()
    snapshot = [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "agent_id": m.agent_id,
            "citations": m.citations,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in messages
    ]

    # Extract conversation actions from system messages (Jira tickets, etc.)
    actions = []
    for m in messages:
        if m.role == "assistant" and m.agent_id == "system":
            content = m.content or ""
            if "Created Jira ticket" in content:
                import re
                match = re.search(r"\[(\w+-\d+)\]\(([^)]+)\):\s*(.+)", content)
                if match:
                    actions.append({
                        "type": "jira_ticket_created",
                        "ticket_key": match.group(1),
                        "ticket_url": match.group(2),
                        "summary": match.group(3),
                        "message_id": str(m.id),
                        "created_at": m.created_at.isoformat() if m.created_at else None,
                    })
                else:
                    actions.append({
                        "type": "jira_ticket_created",
                        "raw": content,
                        "message_id": str(m.id),
                        "created_at": m.created_at.isoformat() if m.created_at else None,
                    })

    # Check for existing feedback from this user on this message
    existing_stmt = select(MessageFeedback).where(
        MessageFeedback.message_id == message_id,
        MessageFeedback.user_id == user.id,
    )
    existing_result = await db.execute(existing_stmt)
    existing = existing_result.scalar_one_or_none()

    if existing:
        existing.thumbs_up = body.thumbs_up
        existing.comment = body.comment
        existing.screenshot_attachment_id = body.screenshot_attachment_id
        existing.conversation_snapshot = snapshot
        existing.tool_calls_log = message.tool_calls_log
        existing.retrieved_sources = message.citations
        existing.conversation_actions = actions
        await db.commit()
        await db.refresh(existing)
        return MessageFeedbackUserOut.model_validate(existing)

    feedback = MessageFeedback(
        message_id=message_id,
        conversation_id=conversation_id,
        user_id=user.id,
        agent_id=message.agent_id or "",
        thumbs_up=body.thumbs_up,
        comment=body.comment,
        screenshot_attachment_id=body.screenshot_attachment_id,
        conversation_snapshot=snapshot,
        tool_calls_log=message.tool_calls_log,
        retrieved_sources=message.citations,
        conversation_actions=actions,
    )
    db.add(feedback)
    await db.commit()
    await db.refresh(feedback)

    return MessageFeedbackUserOut.model_validate(feedback)


@router.get("/admin/agents/{slug}/feedback/summary", response_model=AgentFeedbackSummary)
async def get_agent_feedback_summary(
    slug: str,
    user: AdminUser,
    db: DbSession,
) -> AgentFeedbackSummary:
    """Get feedback summary for an agent (admin only)."""
    total_stmt = select(func.count()).where(MessageFeedback.agent_id == slug)
    up_stmt = select(func.count()).where(
        MessageFeedback.agent_id == slug, MessageFeedback.thumbs_up == True  # noqa: E712
    )
    down_stmt = select(func.count()).where(
        MessageFeedback.agent_id == slug, MessageFeedback.thumbs_up == False  # noqa: E712
    )

    total = (await db.execute(total_stmt)).scalar() or 0
    thumbs_up = (await db.execute(up_stmt)).scalar() or 0
    thumbs_down = (await db.execute(down_stmt)).scalar() or 0

    up_rate_pct = (thumbs_up / total * 100) if total > 0 else 0.0

    return AgentFeedbackSummary(
        total=total,
        thumbs_up=thumbs_up,
        thumbs_down=thumbs_down,
        up_rate_pct=round(up_rate_pct, 1),
    )


@router.get("/admin/agents/{slug}/feedback", response_model=list[MessageFeedbackOut])
async def list_agent_feedback(
    slug: str,
    user: AdminUser,
    db: DbSession,
    thumbs_up: bool | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> list[MessageFeedbackOut]:
    """List all feedback for an agent (admin only)."""
    stmt = (
        select(MessageFeedback)
        .where(MessageFeedback.agent_id == slug)
        .options(selectinload(MessageFeedback.user))
        .order_by(MessageFeedback.created_at.desc())
        .offset(skip)
        .limit(limit)
    )

    if thumbs_up is not None:
        stmt = stmt.where(MessageFeedback.thumbs_up == thumbs_up)

    result = await db.execute(stmt)
    rows = result.scalars().all()

    return [MessageFeedbackOut.model_validate(r) for r in rows]


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


@router.post("/feedback/upload-screenshot", response_model=ChatAttachmentOut)
async def upload_feedback_screenshot(
    file: UploadFile,
    user: CurrentUser,
    db: DbSession,
) -> ChatAttachmentOut:
    """
    Upload a screenshot for message feedback.

    Stored in S3 under uploads/feedback/. Returns an attachment ID
    to be passed to the feedback submission endpoint.
    """
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image files are allowed",
        )

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

    from sqlalchemy import select as sa_select
    from app.models import Connector

    connector = None
    if settings.s3_connector_id:
        connector = await db.scalar(
            sa_select(Connector).where(Connector.id == settings.s3_connector_id)
        )
    if connector is None:
        connector = await db.scalar(
            sa_select(Connector).where(Connector.connector_type == "s3")
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
    s3_key = f"{base_prefix}feedback/{user.id}/{timestamp}_{safe_name}"

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
            "original_name": file.filename or "upload",
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
        },
        **extra_args,
    )

    attachment = FeedbackAttachment(
        id=uuid.uuid4(),
        user_id=user.id,
        filename=file.filename or "upload",
        mime_type=file.content_type,
        file_size=len(content),
        s3_bucket=settings.s3_bucket,
        s3_key=s3_key,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)

    return ChatAttachmentOut(
        id=attachment.id,
        filename=attachment.filename,
        mime_type=attachment.mime_type,
        file_size=attachment.file_size,
        extracted_text=None,
        created_at=attachment.created_at,
    )
