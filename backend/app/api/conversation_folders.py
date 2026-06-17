import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models import Conversation, ConversationFolder
from app.schemas.chat import (
    ConversationFolderCreate,
    ConversationFolderOut,
    ConversationFolderUpdate,
)

router = APIRouter(prefix="/conversation-folders", tags=["conversation-folders"])


async def get_owned_folder(
    folder_id: uuid.UUID, user_id: uuid.UUID, db
) -> ConversationFolder:
    folder = await db.get(ConversationFolder, folder_id)
    if folder is None or folder.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found"
        )
    return folder


@router.get("", response_model=list[ConversationFolderOut])
async def list_folders(user: CurrentUser, db: DbSession) -> list[ConversationFolderOut]:
    result = await db.scalars(
        select(ConversationFolder)
        .where(ConversationFolder.user_id == user.id)
        .order_by(ConversationFolder.name.asc())
    )
    return [ConversationFolderOut.model_validate(f) for f in result.all()]


@router.post("", response_model=ConversationFolderOut, status_code=status.HTTP_201_CREATED)
async def create_folder(
    body: ConversationFolderCreate, user: CurrentUser, db: DbSession
) -> ConversationFolderOut:
    folder = ConversationFolder(user_id=user.id, name=body.name, color=body.color)
    db.add(folder)
    await db.commit()
    await db.refresh(folder)
    return ConversationFolderOut.model_validate(folder)


@router.put("/{folder_id}", response_model=ConversationFolderOut)
async def update_folder(
    folder_id: uuid.UUID,
    body: ConversationFolderUpdate,
    user: CurrentUser,
    db: DbSession,
) -> ConversationFolderOut:
    folder = await get_owned_folder(folder_id, user.id, db)
    if body.name is not None:
        folder.name = body.name
    if body.color is not None:
        folder.color = body.color
    await db.commit()
    await db.refresh(folder)
    return ConversationFolderOut.model_validate(folder)


@router.delete("/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_folder(
    folder_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> None:
    folder = await get_owned_folder(folder_id, user.id, db)
    await db.delete(folder)
    await db.commit()
