"""Celery task: purge expired chat file attachments from S3 and DB."""

import logging

from app.celery_app import celery_app
from app.db.celery_session import run_async

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def purge_expired_attachments(self):
    """Delete S3 objects and DB rows for attachments past retention_until."""
    run_async(_purge())


async def _purge():
    from datetime import timezone

    from sqlalchemy import select

    from app.db.celery_session import get_celery_session_factory
    from app.models import ChatAttachment, Connector, UploadSettings

    session_factory = get_celery_session_factory()

    async with session_factory() as db:
        upload_settings = await db.scalar(select(UploadSettings))
        s3_client = None
        if upload_settings and upload_settings.s3_connector_id:
            connector = await db.scalar(
                select(Connector).where(Connector.id == upload_settings.s3_connector_id)
            )
            if connector:
                from app.services.secrets import get_connector_credentials

                credentials = get_connector_credentials(connector)

                import boto3

                kwargs = {
                    "aws_access_key_id": credentials.get("access_key"),
                    "aws_secret_access_key": credentials.get("secret_key"),
                    "region_name": credentials.get("region", "us-east-1"),
                }
                endpoint = credentials.get("endpoint_url")
                if endpoint:
                    kwargs["endpoint_url"] = endpoint
                s3_client = boto3.client("s3", **kwargs)

        from datetime import datetime

        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(ChatAttachment).where(ChatAttachment.retention_until <= now)
        )
        expired = result.scalars().all()

        deleted_count = 0
        for att in expired:
            if s3_client:
                try:
                    s3_client.delete_object(Bucket=att.s3_bucket, Key=att.s3_key)
                    logger.info("Deleted S3 object s3://%s/%s", att.s3_bucket, att.s3_key)
                except Exception:
                    logger.exception("Failed to delete S3 object %s", att.s3_key)
            await db.delete(att)
            deleted_count += 1

        await db.commit()
        logger.info("Purged %d expired chat attachments", deleted_count)
