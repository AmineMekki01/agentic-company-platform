"""Connector credentials management API (admin-only)."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import AdminUser, DbSession
from app.core.encryption import EncryptionService
from app.models import Connector
from app.schemas.connector import ConnectorCreate, ConnectorOut

router = APIRouter(prefix="/admin/connectors", tags=["admin"])


@router.get("", response_model=list[ConnectorOut])
async def list_connectors(user: AdminUser, db: DbSession) -> list[ConnectorOut]:
    """
    List all connector credentials.
    
    Args:
        user: The authenticated admin user
        db: Database session
        
    Returns:
        List of ConnectorOut objects
    """
    result = await db.scalars(select(Connector).order_by(Connector.created_at.desc()))
    return [ConnectorOut.model_validate(r) for r in result.all()]


@router.post("", response_model=ConnectorOut, status_code=201)
async def create_connector(
    user: AdminUser,
    db: DbSession,
    body: ConnectorCreate,
) -> ConnectorOut:
    """
    Create a new connector credential.
    
    Args:
        user: The authenticated admin user
        db: Database session
        body: ConnectorCreate request body
        
    Returns:
        ConnectorOut object representing the created connector
        
    Raises:
        HTTPException: If slug already exists
    """
    existing = await db.scalar(select(Connector).where(Connector.slug == body.slug))
    if existing:
        raise HTTPException(status_code=409, detail="Slug already exists")

    crypto = EncryptionService()
    encrypted = crypto.encrypt(str(body.credentials))

    conn = Connector(
        slug=body.slug,
        name=body.name,
        connector_type=body.connector_type,
        credentials_encrypted=encrypted,
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)
    return ConnectorOut.model_validate(conn)


@router.delete("/{slug}", status_code=204)
async def delete_connector(slug: str, user: AdminUser, db: DbSession):
    """
    Delete a connector credential.
    
    Args:
        slug: The connector slug
        user: The authenticated admin user
        db: Database session
        
    Raises:
        HTTPException: If connector not found
    """
    conn = await db.scalar(select(Connector).where(Connector.slug == slug))
    if conn is None:
        raise HTTPException(status_code=404, detail="Connector not found")
    await db.delete(conn)
    await db.commit()
