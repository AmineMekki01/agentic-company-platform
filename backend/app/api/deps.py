import uuid
from collections.abc import AsyncIterator
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User, UserRole

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AsyncIterator[User]:
    """
    Validate the bearer token and return the authenticated user.
    
    Args:
        credentials: The HTTP authorization credentials
        db: Database session
        
    Returns:
        User object
        
    Raises:
        HTTPException: If authentication fails
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    resets: list = []
    if user.tenant_id is not None:
        from app.agents.llm import reset_ollama_base_url, set_ollama_base_url
        from app.core.tenant_settings_cache import get_tenant_runtime
        from app.core.tracing import reset_tracing_mode, set_tracing_mode

        runtime = await get_tenant_runtime(db, user.tenant_id)
        resets.append((reset_tracing_mode, set_tracing_mode(runtime.tracing_mode)))
        resets.append((reset_ollama_base_url, set_ollama_base_url(runtime.ollama_base_url)))

    try:
        yield user
    finally:
        for reset, token in reversed(resets):
            try:
                reset(token)
            except Exception:
                pass


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(user: CurrentUser) -> User:
    """
    Ensure the current user has admin privileges.
    
    Args:
        user: The authenticated user
        
    Returns:
        User object
        
    Raises:
        HTTPException: If user is not an admin
    """
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


AdminUser = Annotated[User, Depends(require_admin)]
DbSession = Annotated[AsyncSession, Depends(get_db)]
