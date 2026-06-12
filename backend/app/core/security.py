import uuid
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """
    Hash a plaintext password using Argon2.
    
    Args:
        password: The plaintext password to hash
        
    Returns:
        The hashed password
    """
    return _password_hash.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify a plaintext password against a stored hash.
    
    Args:
        plain: The plaintext password to verify
        hashed: The stored hash to verify against
        
    Returns:
        True if the password matches, False otherwise
    """
    return _password_hash.verify(plain, hashed)


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    """
    Create a JWT access token for a user.
    
    Args:
        user_id: The user ID
        role: The user role
        
    Returns:
        The JWT access token
    """
    payload = {
        "sub": str(user_id),
        "role": role,
        "exp": datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Decode and verify a JWT access token.
    
    Args:
        token: The JWT access token to decode
        
    Returns:
        The decoded token payload
    """
    return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
