"""
Repository test conftest.

Repository tests hit a REAL PostgreSQL database.
Set DATABASE_URL to a test PostgreSQL instance before running.

Each test gets a transaction that rolls back at teardown — fully isolated.

Run with:
    DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/test \
    uv run pytest tests/repository/ -v

Skip without PostgreSQL:
    uv run pytest tests/repository/ --ignore-glob="*" -v
"""
import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base

# Marker for tests that need a real PostgreSQL connection
requires_postgres = pytest.mark.skipif(
    not os.getenv("DATABASE_URL", "").startswith("postgresql"),
    reason="Requires real PostgreSQL — set DATABASE_URL=postgresql+asyncpg://...",
)


@pytest_asyncio.fixture(scope="session")
async def pg_engine():
    """Create the async engine for the test PostgreSQL database."""
    url = os.getenv("DATABASE_URL")
    if not url or not url.startswith("postgresql"):
        pytest.skip("PostgreSQL not available — skipping repository tests")

    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def pg_session(pg_engine) -> AsyncSession:
    """
    Provide a rollback-per-test AsyncSession.
    Each test runs inside a transaction that is rolled back on teardown.
    """
    session_factory = async_sessionmaker(pg_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()
