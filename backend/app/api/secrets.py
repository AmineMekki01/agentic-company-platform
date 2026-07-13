"""Secret credential vault API (admin-only). Connectors reference these instead of
storing their own credentials - see app/services/secrets.py and secret_schemas.py."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from app.api.deps import AdminUser, DbSession
from app.models import Connector, Secret
from app.schemas.secret import SecretCreate, SecretDetailOut, SecretOut, SecretUpdate
from app.services.secret_schemas import non_sensitive_fields, validate_credentials
from app.services.secrets import decrypt_credentials, encrypt_credentials

router = APIRouter(prefix="/admin/secrets", tags=["admin"])


async def _connector_counts(db: DbSession) -> dict:
    result = await db.execute(
        select(Connector.secret_id, func.count(Connector.id))
        .where(Connector.secret_id.is_not(None))
        .group_by(Connector.secret_id)
    )
    return {secret_id: count for secret_id, count in result.all()}


@router.get("", response_model=list[SecretOut])
async def list_secrets(user: AdminUser, db: DbSession) -> list[SecretOut]:
    """List all secrets. Never includes credential values."""
    counts = await _connector_counts(db)
    result = await db.scalars(select(Secret).order_by(Secret.created_at.desc()))
    return [
        SecretOut(
            id=s.id, slug=s.slug, name=s.name, secret_type=s.secret_type,
            connector_count=counts.get(s.id, 0),
            created_at=s.created_at, updated_at=s.updated_at,
        )
        for s in result.all()
    ]


@router.post("", response_model=SecretOut, status_code=201)
async def create_secret(user: AdminUser, db: DbSession, body: SecretCreate) -> SecretOut:
    """Create a new secret. Validates required fields for typed secret_types."""
    existing = await db.scalar(select(Secret).where(Secret.slug == body.slug))
    if existing:
        raise HTTPException(status_code=409, detail="Slug already exists")

    missing = validate_credentials(body.secret_type, body.credentials)
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required field(s): {', '.join(missing)}")

    secret = Secret(
        slug=body.slug,
        name=body.name,
        secret_type=body.secret_type,
        credentials_encrypted=encrypt_credentials(body.credentials),
    )
    db.add(secret)
    await db.commit()
    await db.refresh(secret)
    return SecretOut(
        id=secret.id, slug=secret.slug, name=secret.name, secret_type=secret.secret_type,
        connector_count=0, created_at=secret.created_at, updated_at=secret.updated_at,
    )


@router.get("/{slug}", response_model=SecretDetailOut)
async def get_secret(slug: str, user: AdminUser, db: DbSession) -> SecretDetailOut:
    """Fetch one secret with non-sensitive credential fields revealed for editing."""
    secret = await db.scalar(select(Secret).where(Secret.slug == slug))
    if secret is None:
        raise HTTPException(status_code=404, detail="Secret not found")

    counts = await _connector_counts(db)
    credentials = decrypt_credentials(secret.credentials_encrypted)
    return SecretDetailOut(
        id=secret.id, slug=secret.slug, name=secret.name, secret_type=secret.secret_type,
        connector_count=counts.get(secret.id, 0),
        created_at=secret.created_at, updated_at=secret.updated_at,
        non_sensitive_credentials=non_sensitive_fields(secret.secret_type, credentials),
    )


@router.patch("/{slug}", response_model=SecretOut)
async def update_secret(slug: str, user: AdminUser, db: DbSession, body: SecretUpdate) -> SecretOut:
    """Rename and/or rotate credentials. `credentials` is merged into the existing
    stored dict - only the fields you send are overwritten."""
    secret = await db.scalar(select(Secret).where(Secret.slug == slug))
    if secret is None:
        raise HTTPException(status_code=404, detail="Secret not found")

    if body.name is not None:
        secret.name = body.name

    if body.credentials is not None:
        existing = decrypt_credentials(secret.credentials_encrypted)
        merged = {**existing, **{k: v for k, v in body.credentials.items() if v}}
        missing = validate_credentials(secret.secret_type, merged)
        if missing:
            raise HTTPException(status_code=400, detail=f"Missing required field(s): {', '.join(missing)}")
        secret.credentials_encrypted = encrypt_credentials(merged)

    await db.commit()
    await db.refresh(secret)
    counts = await _connector_counts(db)
    return SecretOut(
        id=secret.id, slug=secret.slug, name=secret.name, secret_type=secret.secret_type,
        connector_count=counts.get(secret.id, 0),
        created_at=secret.created_at, updated_at=secret.updated_at,
    )


@router.delete("/{slug}", status_code=204)
async def delete_secret(slug: str, user: AdminUser, db: DbSession):
    """Delete a secret. Blocked if any connector still references it."""
    secret = await db.scalar(select(Secret).where(Secret.slug == slug))
    if secret is None:
        raise HTTPException(status_code=404, detail="Secret not found")

    result = await db.scalars(select(Connector).where(Connector.secret_id == secret.id))
    in_use = [c.name for c in result.all()]
    if in_use:
        raise HTTPException(
            status_code=409,
            detail=f"Secret is used by connector(s): {', '.join(in_use)}",
        )

    await db.delete(secret)
    await db.commit()
