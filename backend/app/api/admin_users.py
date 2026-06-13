"""Admin users API."""

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import AdminUser, DbSession
from app.models import User
from app.schemas.auth import UserOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
async def list_users(user: AdminUser, db: DbSession) -> list[UserOut]:
    """
    List all registered users.

    Args:
        user: Admin user
        db: Database session

    Returns:
        List of users
    """
    result = await db.scalars(select(User).order_by(User.email))
    rows = result.all()
    return [UserOut.model_validate(r) for r in rows]
