"""Admin upload settings API."""

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import AdminUser, DbSession
from app.models import UploadSettings
from app.schemas.upload_settings import UploadSettingsOut, UploadSettingsUpdate

router = APIRouter(prefix="/admin/upload-settings", tags=["admin"])


@router.get("", response_model=UploadSettingsOut)
async def get_upload_settings(user: AdminUser, db: DbSession) -> UploadSettingsOut:
    """Return the singleton upload-settings row (create default if missing)."""
    row = await db.scalar(select(UploadSettings))
    if row is None:
        row = UploadSettings()
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return UploadSettingsOut.model_validate(row)


@router.put("", response_model=UploadSettingsOut)
async def update_upload_settings(
    user: AdminUser,
    db: DbSession,
    body: UploadSettingsUpdate,
) -> UploadSettingsOut:
    """Update the singleton upload-settings row."""
    row = await db.scalar(select(UploadSettings))
    if row is None:
        row = UploadSettings()
        db.add(row)

    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(row, key, value)

    await db.commit()
    await db.refresh(row)
    return UploadSettingsOut.model_validate(row)
