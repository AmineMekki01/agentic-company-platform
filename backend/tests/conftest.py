from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app as fastapi_app
import app.models  # register models on Base.metadata
from app.models.user import User, UserRole


@pytest.fixture
async def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest.fixture
async def client(db_engine, session_factory) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        async with session_factory() as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
async def create_test_user(session_factory):
    async def _create(email: str, password: str, role: UserRole = UserRole.USER):
        async with session_factory() as session:
            user = User(
                email=email.lower(),
                password_hash=hash_password(password),
                role=role,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            return user
    return _create


@pytest.fixture
async def auth_headers(client, create_test_user) -> dict[str, str]:
    user = await create_test_user("tester@example.com", "password123")
    from app.core.security import create_access_token
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}
