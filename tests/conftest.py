"""
Root conftest — shared fixtures and helpers for all test layers.

SQLite is used for API/worker tests (no Docker). Repository tests
use real PostgreSQL (see tests/repository/conftest.py).
"""
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.auth import create_access_token, hash_password
from app.core.database import get_db
from app.main import app
from app.models import Base, User

# Long-enough key for JWT (avoids InsecureKeyLengthWarning)
TEST_SECRET_KEY = "test-secret-key-that-is-long-enough-for-jwt-hmac"

# SQLite for fast, no-Docker tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"


def _patch_jsonb_for_sqlite():
    """Replace PostgreSQL JSONB columns with JSON so SQLite can create the schema."""
    import sqlalchemy as sa
    from sqlalchemy.dialects.postgresql import JSONB

    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, JSONB):
                col.type = sa.JSON()


# Patch before creating engine
_patch_jsonb_for_sqlite()

# Override SECRET_KEY in settings so test JWTs use a long-enough key
import app.core.config as _cfg
_cfg.settings.SECRET_KEY = TEST_SECRET_KEY


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


def _make_redis_mock():
    from unittest.mock import AsyncMock, MagicMock
    mock = AsyncMock()
    mock.zremrangebyscore = AsyncMock()
    mock.zadd = AsyncMock()
    mock.zcard = AsyncMock(return_value=0)
    mock.expire = AsyncMock()
    mock.zrange = AsyncMock(return_value=[])
    mock.execute = AsyncMock(return_value=[0, 1, 0, True])
    mock.setex = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.delete = AsyncMock()
    mock.ping = AsyncMock(return_value=True)
    mock.set = AsyncMock()
    mock.pipeline.return_value = mock
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=None)
    return mock


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient with the real app. DB and Redis are mocked."""
    from unittest.mock import patch

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    redis_mock = _make_redis_mock()

    with patch("app.core.redis.get_redis", return_value=redis_mock), \
         patch("app.routes.public.get_redis", return_value=redis_mock):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac

    app.dependency_overrides.clear()


async def create_test_user(
    db: AsyncSession,
    email: str = "test@example.com",
    name: str = "Test User",
    is_admin: bool = False,
    is_email_verified: bool = True,
) -> User:
    user = User(
        email=email,
        name=name,
        hashed_password=hash_password("TestPassword123"),
        auth_provider="email",
        is_email_verified=is_email_verified,
        is_admin=is_admin,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


def auth_headers(user: User) -> dict:
    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def make_user(db_session):
    async def _make(email=None, name="Test User", is_admin=False, is_email_verified=True):
        email = email or f"user-{uuid.uuid4().hex[:8]}@example.com"
        return await create_test_user(
            db_session, email=email, name=name,
            is_admin=is_admin, is_email_verified=is_email_verified,
        )
    return _make
