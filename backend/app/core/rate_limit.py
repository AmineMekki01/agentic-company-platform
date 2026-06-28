from limits import parse
from slowapi import Limiter
from starlette.requests import Request

from app.core.config import settings
from app.core.security import decode_access_token


def _user_key(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        try:
            payload = decode_access_token(token)
            return f"user:{payload['sub']}"
        except Exception:
            pass
    client = request.client
    return f"ip:{client.host if client else 'unknown'}"


limiter = Limiter(key_func=_user_key, storage_uri=settings.rate_limit_storage_uri)


def check_rate_limit(identifier: str, limit_str: str) -> bool:
    """Hit the rate limit and return True if within bounds."""
    return limiter._limiter.hit(parse(limit_str), identifier)
