"""Knowledge sources admin API."""

import uuid

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import AdminUser, DbSession
from app.models import AgentSettings, Connector, KnowledgeSource
from app.schemas.knowledge_source import KnowledgeSourceCreate, KnowledgeSourceOut, KnowledgeSourceUpdate, SyncDocumentStatus, SyncStatusOut
from app.services.gdrive import sync_gdrive_folder
from app.services.notion import sync_notion_database, sync_notion_page
from app.services.rag import get_rag_service
from app.services.s3 import sync_s3_prefix

router = APIRouter(prefix="/admin/knowledge-sources", tags=["admin"])


@router.get("", response_model=list[KnowledgeSourceOut])
async def list_knowledge_sources(user: AdminUser, db: DbSession) -> list[KnowledgeSourceOut]:
    """
    List all knowledge sources.
    
    Args:
        user: The authenticated admin user
        db: Database session
        
    Returns:
        List of KnowledgeSourceOut objects
    """
    result = await db.scalars(
        select(KnowledgeSource)
        .options(selectinload(KnowledgeSource.connector))
        .order_by(KnowledgeSource.created_at.desc())
    )
    return [KnowledgeSourceOut.model_validate(r) for r in result.all()]


@router.post("", response_model=KnowledgeSourceOut, status_code=201)
async def create_knowledge_source(
    user: AdminUser,
    db: DbSession,
    body: KnowledgeSourceCreate,
) -> KnowledgeSourceOut:
    """
    Create a new knowledge source.
    
    Args:
        user: The authenticated admin user
        db: Database session
        body: Knowledge source creation data
        
    Returns:
        KnowledgeSourceOut object representing the created knowledge source
        
    Raises:
        HTTPException: If slug already exists
    """
    body.slug = body.slug.strip()
    existing = await db.scalar(select(KnowledgeSource).where(KnowledgeSource.slug == body.slug))
    if existing:
        raise HTTPException(status_code=409, detail="Slug already exists")
    ks = KnowledgeSource(**body.model_dump(exclude_unset=True))
    db.add(ks)
    await db.commit()
    await db.refresh(ks)
    return KnowledgeSourceOut.model_validate(ks)


@router.delete("/{slug}", status_code=204)
async def delete_knowledge_source(slug: str, user: AdminUser, db: DbSession, request: Request):
    """
    Delete a knowledge source and clean up its vectors.

    Args:
        slug: The knowledge source slug
        user: The authenticated admin user
        db: Database session
        request: FastAPI request to access runtime

    Raises:
        HTTPException: If knowledge source not found
    """
    slug = slug.strip()
    ks = await db.scalar(select(KnowledgeSource).where(func.trim(KnowledgeSource.slug) == slug))
    if ks is None:
        raise HTTPException(status_code=404, detail="Knowledge source not found")
    rag = get_rag_service()
    await rag.delete_by_knowledge_source(str(ks.id))
    await db.delete(ks)
    await db.commit()

    result = await db.scalars(select(AgentSettings))
    changed = False
    for agent in result.all():
        sources = agent.connected_sources or []
        cleaned = [s for s in sources if s != ks.slug and s != str(ks.id)]
        if len(cleaned) != len(sources):
            agent.connected_sources = cleaned
            changed = True
    if changed:
        await db.commit()

    runtime = getattr(request.app.state, "runtime", None)
    if runtime and changed:
        await runtime.refresh_graph()


@router.patch("/{slug}", response_model=KnowledgeSourceOut)
async def update_knowledge_source(
    slug: str,
    user: AdminUser,
    db: DbSession,
    body: KnowledgeSourceUpdate,
) -> KnowledgeSourceOut:
    """Update a knowledge source's name, connector, or config."""
    slug = slug.strip()
    ks = await db.scalar(
        select(KnowledgeSource)
        .options(selectinload(KnowledgeSource.connector))
        .where(func.trim(KnowledgeSource.slug) == slug)
    )
    if ks is None:
        raise HTTPException(status_code=404, detail="Knowledge source not found")

    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(ks, key, value)

    await db.commit()
    await db.refresh(ks)
    return KnowledgeSourceOut.model_validate(ks)


@router.get("/{slug}/sync-status", response_model=SyncStatusOut)
async def get_sync_status(slug: str, user: AdminUser, db: DbSession) -> SyncStatusOut:
    """Get per-document sync status for a knowledge source."""
    slug = slug.strip()
    ks = await db.scalar(select(KnowledgeSource).where(func.trim(KnowledgeSource.slug) == slug))
    if ks is None:
        raise HTTPException(status_code=404, detail="Knowledge source not found")

    rag = get_rag_service()
    ks_id = str(ks.id)
    metadata = await rag.get_source_metadata(ks_id)

    documents: list[SyncDocumentStatus] = []
    for source_id, meta in sorted(metadata.items(), key=lambda x: x[1].get("title", "")):
        documents.append(SyncDocumentStatus(
            source_id=source_id,
            title=meta.get("title", "Untitled"),
            chunk_count=meta.get("chunk_count", 0),
            source_modified_at=meta.get("source_modified_at"),
        ))

    return SyncStatusOut(
        slug=ks.slug,
        status=ks.status,
        last_sync_at=ks.last_sync_at,
        chunk_count=ks.chunk_count,
        document_count=len(documents),
        documents=documents,
    )


@router.post("/{slug}/sync", status_code=status.HTTP_202_ACCEPTED)
async def trigger_knowledge_source_sync(
    slug: str,
    user: AdminUser,
    db: DbSession,
    force_full: bool = False,
):
    """
    Trigger a sync for a knowledge source.
    
    Args:
        slug: The knowledge source slug
        user: The authenticated admin user
        db: Database session
        
    Raises:
        HTTPException: If knowledge source not found
    """
    slug = slug.strip()
    ks = await db.scalar(
        select(KnowledgeSource)
        .options(selectinload(KnowledgeSource.connector))
        .where(func.trim(KnowledgeSource.slug) == slug)
    )
    if ks is None:
        raise HTTPException(status_code=404, detail="Knowledge source not found")

    ks.status = "syncing"
    await db.commit()

    if ks.source_type == "notion":
        config = ks.config or {}
        database_id = config.get("database_id")
        page_id = config.get("page_id")

        if not database_id and not page_id:
            raise HTTPException(status_code=400, detail="No database_id or page_id configured for this source")

        connector = ks.connector
        if connector is None:
            raise HTTPException(status_code=400, detail="No connector linked to this Notion source")

        if database_id:
            task = sync_notion_database.delay(
                database_id=str(database_id),
                source_title=ks.name,
                connector_credentials=connector.credentials_encrypted,
                slug=ks.slug,
                knowledge_source_id=str(ks.id),
                force_full=force_full,
            )
        else:
            page_title = config.get("page_title", "Untitled")
            task = sync_notion_page.delay(
                page_id=str(page_id),
                page_title=str(page_title),
                source_title=ks.name,
                connector_credentials=connector.credentials_encrypted,
                slug=ks.slug,
                knowledge_source_id=str(ks.id),
                force_full=force_full,
            )
        return {"task_id": task.id, "status": "queued"}

    if ks.source_type == "s3":
        config = ks.config or {}
        bucket = config.get("bucket")
        prefix = config.get("prefix", "")

        if not bucket:
            raise HTTPException(status_code=400, detail="No bucket configured for this S3 source")

        connector = ks.connector
        if connector is None:
            raise HTTPException(status_code=400, detail="No connector linked to this S3 source")

        task = sync_s3_prefix.delay(
            bucket=str(bucket),
            prefix=str(prefix),
            source_title=ks.name,
            connector_credentials=connector.credentials_encrypted,
            slug=ks.slug,
            knowledge_source_id=str(ks.id),
            force_full=force_full,
        )
        return {"task_id": task.id, "status": "queued"}

    if ks.source_type == "gdrive":
        config = ks.config or {}
        folder_id = config.get("folder_id")

        if not folder_id:
            raise HTTPException(status_code=400, detail="No folder_id configured for this Google Drive source")

        connector = ks.connector
        if connector is None:
            raise HTTPException(status_code=400, detail="No connector linked to this Google Drive source")

        task = sync_gdrive_folder.delay(
            folder_id=str(folder_id),
            source_title=ks.name,
            connector_credentials=connector.credentials_encrypted,
            slug=ks.slug,
            knowledge_source_id=str(ks.id),
            force_full=force_full,
        )
        return {"task_id": task.id, "status": "queued"}

    raise HTTPException(status_code=400, detail="Sync not supported for this source type")
