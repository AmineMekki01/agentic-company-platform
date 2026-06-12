import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class LoginRequest(BaseModel):
    """
    Login request schema.
    
    This schema represents the login request data that can be sent
    by clients, including:
    - User email
    - User password
    """
    email: EmailStr
    password: str


class UserOut(BaseModel):
    """
    User output schema.
    """
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    first_name: str | None
    last_name: str | None
    occupation: str | None
    role: str
    created_at: datetime


class TokenResponse(BaseModel):
    """
    Token response schema.
    
    This schema represents the token response data that can be returned to clients,
    including:
    - Access token
    - Token type
    - User data
    """
    access_token: str
    token_type: str = "bearer"
    user: UserOut
