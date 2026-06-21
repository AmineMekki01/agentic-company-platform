import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.models import Conversation, Message
from app.schemas.chat import ConversationDetail, ConversationOut, MessageOut, MoveToFolderRequest

router = APIRouter(prefix="/conversations", tags=["conversations"])


async def get_owned_conversation(
    conversation_id: uuid.UUID, user_id: uuid.UUID, db
) -> Conversation:
    """
    Fetch a conversation and verify the requesting user owns it.
    
    Args:
        conversation_id: The conversation ID
        user_id: The user ID
        db: Database session
        
    Returns:
        Conversation object
        
    Raises:
        HTTPException: If conversation not found or not owned by user
    """
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None or conversation.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found"
        )
    return conversation


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    user: CurrentUser,
    db: DbSession,
    folder_id: uuid.UUID | None = Query(None),
) -> list[ConversationOut]:
    """
    List all conversations for the current user.
    
    Optionally filter by folder_id. Pass folder_id=null to get unfiled conversations.
    
    Args:
        user: The authenticated user
        db: Database session
        folder_id: Optional folder ID filter
        
    Returns:
        List of ConversationOut objects
    """
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
    )
    if folder_id is not None:
        stmt = stmt.where(Conversation.folder_id == folder_id)
    else:
        pass
    result = await db.scalars(stmt)
    return [ConversationOut.model_validate(c) for c in result.all()]


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(user: CurrentUser, db: DbSession) -> ConversationOut:
    """
    Create a new empty conversation.
    
    Args:
        user: The authenticated user
        db: Database session
        
    Returns:
        ConversationOut object representing the created conversation
    """
    conversation = Conversation(user_id=user.id)
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return ConversationOut.model_validate(conversation)


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> ConversationDetail:
    """
    Get a single conversation with all its messages.
    
    Args:
        conversation_id: The conversation ID
        user: The authenticated user
        db: Database session
        
    Returns:
        ConversationDetail object with messages
        
    Raises:
        HTTPException: If conversation not found or not owned by user
    """
    conversation = await get_owned_conversation(conversation_id, user.id, db)
    result = await db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.asc())
        .options(selectinload(Message.attachments))
    )
    messages = [MessageOut.model_validate(m) for m in result.all()]
    return ConversationDetail(
        **ConversationOut.model_validate(conversation).model_dump(),
        messages=messages,
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> None:
    """
    Delete a conversation and all its messages.
    
    Args:
        conversation_id: The conversation ID
        user: The authenticated user
        db: Database session
        
    Raises:
        HTTPException: If conversation not found or not owned by user
    """
    conversation = await get_owned_conversation(conversation_id, user.id, db)
    await db.delete(conversation)
    await db.commit()


@router.patch("/{conversation_id}/folder", response_model=ConversationOut)
async def move_conversation_to_folder(
    conversation_id: uuid.UUID,
    body: MoveToFolderRequest,
    user: CurrentUser,
    db: DbSession,
) -> ConversationOut:
    """
    Move a conversation to a folder (or remove from folder).
    
    Args:
        conversation_id: The conversation ID
        body: Move request with target folder_id or null
        user: The authenticated user
        db: Database session
        
    Returns:
        Updated ConversationOut object
        
    Raises:
        HTTPException: If conversation not found or not owned by user
    """
    conversation = await get_owned_conversation(conversation_id, user.id, db)
    if body.folder_id is not None:
        from app.models import ConversationFolder
        folder = await db.get(ConversationFolder, body.folder_id)
        if folder is None or folder.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found"
            )
    conversation.folder_id = body.folder_id
    await db.commit()
    await db.refresh(conversation)
    return ConversationOut.model_validate(conversation)
