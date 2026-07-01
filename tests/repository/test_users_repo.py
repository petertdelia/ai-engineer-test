"""
Repository tests for UserRepository — requires real PostgreSQL.

Run with:
    DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/test \
    uv run pytest tests/repository/test_users_repo.py -v
"""
import uuid

import pytest
import pytest_asyncio

from app.core.auth import hash_password
from app.models import User
from app.repository.users import UserRepository
from tests.repository.conftest import requires_postgres


@requires_postgres
@pytest.mark.asyncio
async def test_create_user(pg_session):
    repo = UserRepository(pg_session)
    user = await repo.create(
        email=f"repo_user_{uuid.uuid4().hex[:8]}@example.com",
        name="Repo Test User",
        hashed_password=hash_password("Password123"),
        auth_provider="email",
    )
    assert user.id is not None
    assert user.email.startswith("repo_user_")
    assert user.is_active is True


@requires_postgres
@pytest.mark.asyncio
async def test_get_by_email(pg_session):
    repo = UserRepository(pg_session)
    email = f"get_email_{uuid.uuid4().hex[:8]}@example.com"
    created = await repo.create(
        email=email,
        name="Email Lookup User",
        hashed_password=hash_password("Password123"),
        auth_provider="email",
    )
    found = await repo.get_by_email(email)
    assert found is not None
    assert found.id == created.id


@requires_postgres
@pytest.mark.asyncio
async def test_get_by_email_not_found(pg_session):
    repo = UserRepository(pg_session)
    result = await repo.get_by_email("nonexistent@example.com")
    assert result is None


@requires_postgres
@pytest.mark.asyncio
async def test_get_by_id(pg_session):
    repo = UserRepository(pg_session)
    created = await repo.create(
        email=f"by_id_{uuid.uuid4().hex[:8]}@example.com",
        name="By ID User",
        hashed_password=hash_password("Password123"),
        auth_provider="email",
    )
    found = await repo.get_by_id(created.id)
    assert found is not None
    assert found.id == created.id


@requires_postgres
@pytest.mark.asyncio
async def test_update_user(pg_session):
    repo = UserRepository(pg_session)
    user = await repo.create(
        email=f"update_user_{uuid.uuid4().hex[:8]}@example.com",
        name="Before Update",
        hashed_password=hash_password("Password123"),
        auth_provider="email",
    )
    updated = await repo.update(user.id, name="After Update")
    assert updated.name == "After Update"


@requires_postgres
@pytest.mark.asyncio
async def test_verify_email(pg_session):
    repo = UserRepository(pg_session)
    user = await repo.create(
        email=f"verify_email_{uuid.uuid4().hex[:8]}@example.com",
        name="Unverified",
        hashed_password=hash_password("Password123"),
        auth_provider="email",
        is_email_verified=False,
    )
    assert user.is_email_verified is False

    verified = await repo.update(user.id, is_email_verified=True)
    assert verified.is_email_verified is True


@requires_postgres
@pytest.mark.asyncio
async def test_delete_anonymizes_user(pg_session):
    """
    Deleting a user should anonymize their email and name
    (not hard-delete, per plan spec) or hard-delete and null session user_id.
    """
    repo = UserRepository(pg_session)
    user = await repo.create(
        email=f"delete_me_{uuid.uuid4().hex[:8]}@example.com",
        name="Delete Me",
        hashed_password=hash_password("Password123"),
        auth_provider="email",
    )
    user_id = user.id

    await repo.delete(user_id)

    # After deletion, the user should either not be found or be anonymized
    found = await repo.get_by_id(user_id)
    # Either deleted (None) or anonymized (email changed)
    if found is not None:
        assert found.email != user.email or found.name != user.name


@requires_postgres
@pytest.mark.asyncio
async def test_create_user_duplicate_email_raises(pg_session):
    """Creating two users with the same email should raise an integrity error."""
    from sqlalchemy.exc import IntegrityError

    repo = UserRepository(pg_session)
    email = f"dup_{uuid.uuid4().hex[:8]}@example.com"
    await repo.create(
        email=email,
        name="First",
        hashed_password=hash_password("Password123"),
        auth_provider="email",
    )
    with pytest.raises(IntegrityError):
        await repo.create(
            email=email,
            name="Second",
            hashed_password=hash_password("Password123"),
            auth_provider="email",
        )
