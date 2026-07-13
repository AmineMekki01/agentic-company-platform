"""Connector management API (admin-only). Connectors reference a Secret for
credentials - see app/api/secrets.py."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import AdminUser, DbSession
from app.models import Connector, Secret
from app.schemas.connector import ConnectorCreate, ConnectorOut, ConnectorUpdate

router = APIRouter(prefix="/admin/connectors", tags=["admin"])


async def _get_secret_or_404(secret_id, db: DbSession) -> Secret:
    secret = await db.get(Secret, secret_id)
    if secret is None:
        raise HTTPException(status_code=404, detail="Secret not found")
    return secret


@router.get("", response_model=list[ConnectorOut])
async def list_connectors(user: AdminUser, db: DbSession) -> list[ConnectorOut]:
    """List all connectors."""
    result = await db.scalars(select(Connector).order_by(Connector.created_at.desc()))
    return [ConnectorOut.model_validate(r) for r in result.all()]


@router.post("", response_model=ConnectorOut, status_code=201)
async def create_connector(
    user: AdminUser,
    db: DbSession,
    body: ConnectorCreate,
) -> ConnectorOut:
    """
    Create a new connector, referencing an existing secret for credentials.

    Raises:
        HTTPException: If slug already exists, secret not found, or the
            secret's type doesn't match connector_type.
    """
    existing = await db.scalar(select(Connector).where(Connector.slug == body.slug))
    if existing:
        raise HTTPException(status_code=409, detail="Slug already exists")

    secret = await _get_secret_or_404(body.secret_id, db)
    if secret.secret_type != body.connector_type:
        raise HTTPException(
            status_code=400,
            detail=f"Secret type '{secret.secret_type}' does not match connector_type '{body.connector_type}'",
        )

    conn = Connector(
        slug=body.slug,
        name=body.name,
        connector_type=body.connector_type,
        secret_id=body.secret_id,
        config=body.config,
    )
    db.add(conn)
    await db.commit()
    await db.refresh(conn)
    return ConnectorOut.model_validate(conn)


@router.patch("/{slug}", response_model=ConnectorOut)
async def update_connector(
    slug: str,
    user: AdminUser,
    db: DbSession,
    body: ConnectorUpdate,
) -> ConnectorOut:
    """Rename a connector, re-point it to a different secret, or change its config."""
    conn = await db.scalar(select(Connector).where(Connector.slug == slug))
    if conn is None:
        raise HTTPException(status_code=404, detail="Connector not found")

    if body.name is not None:
        conn.name = body.name
    if body.secret_id is not None:
        secret = await _get_secret_or_404(body.secret_id, db)
        if secret.secret_type != conn.connector_type:
            raise HTTPException(
                status_code=400,
                detail=f"Secret type '{secret.secret_type}' does not match connector_type '{conn.connector_type}'",
            )
        conn.secret_id = body.secret_id
    if body.config is not None:
        conn.config = body.config

    await db.commit()
    await db.refresh(conn)
    return ConnectorOut.model_validate(conn)


@router.delete("/{slug}", status_code=204)
async def delete_connector(slug: str, user: AdminUser, db: DbSession):
    """
    Delete a connector.

    Raises:
        HTTPException: If connector not found
    """
    conn = await db.scalar(select(Connector).where(Connector.slug == slug))
    if conn is None:
        raise HTTPException(status_code=404, detail="Connector not found")
    await db.delete(conn)
    await db.commit()
