import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, patch

from tests.conftest import auth_headers, create_test_user


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient, db_session: AsyncSession):
    with patch("app.routes.auth.send_verification_email", new_callable=AsyncMock):
        with patch("app.core.redis.get_redis") as mock_redis:
            mock = AsyncMock()
            mock.setex = AsyncMock()
            mock.zremrangebyscore = AsyncMock()
            mock.zadd = AsyncMock()
            mock.zcard = AsyncMock(return_value=0)
            mock.expire = AsyncMock()
            mock.zrange = AsyncMock(return_value=[])
            mock.execute = AsyncMock(return_value=[0, 1, 0, True])
            mock_redis.return_value = mock
            mock.pipeline.return_value = mock

            resp = await client.post("/auth/register", json={
                "email": "newuser@example.com",
                "password": "SecurePass123",
                "name": "New User",
            })
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, db_session: AsyncSession):
    await create_test_user(db_session, email="dup@example.com")
    with patch("app.core.redis.get_redis") as mock_redis:
        mock = AsyncMock()
        mock.setex = AsyncMock()
        mock.execute = AsyncMock(return_value=[0, 1, 0, True])
        mock.pipeline.return_value = mock
        mock_redis.return_value = mock

        resp = await client.post("/auth/register", json={
            "email": "dup@example.com",
            "password": "SecurePass123",
            "name": "Dup User",
        })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, db_session: AsyncSession):
    await create_test_user(db_session, email="login@example.com")
    with patch("app.core.redis.get_redis") as mock_redis:
        mock = AsyncMock()
        mock.setex = AsyncMock()
        mock.zremrangebyscore = AsyncMock()
        mock.zadd = AsyncMock()
        mock.zcard = AsyncMock(return_value=1)
        mock.expire = AsyncMock()
        mock.zrange = AsyncMock(return_value=[])
        mock.execute = AsyncMock(return_value=[0, 1, 1, True])
        mock.pipeline.return_value = mock
        mock_redis.return_value = mock

        resp = await client.post("/auth/login", json={
            "email": "login@example.com",
            "password": "TestPassword123",
        })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, db_session: AsyncSession):
    await create_test_user(db_session, email="wrongpw@example.com")
    with patch("app.core.redis.get_redis") as mock_redis:
        mock = AsyncMock()
        mock.zremrangebyscore = AsyncMock()
        mock.zadd = AsyncMock()
        mock.zcard = AsyncMock(return_value=1)
        mock.expire = AsyncMock()
        mock.zrange = AsyncMock(return_value=[])
        mock.execute = AsyncMock(return_value=[0, 1, 1, True])
        mock.pipeline.return_value = mock
        mock_redis.return_value = mock

        resp = await client.post("/auth/login", json={
            "email": "wrongpw@example.com",
            "password": "WrongPassword!",
        })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, db_session: AsyncSession):
    user = await create_test_user(db_session, email="me@example.com")
    resp = await client.get("/users/me", headers=auth_headers(user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "me@example.com"
    assert data["name"] == "Test User"


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client: AsyncClient):
    resp = await client.get("/users/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_token_refresh(client: AsyncClient, db_session: AsyncSession):
    user = await create_test_user(db_session, email="refresh@example.com")
    from app.core.auth import create_refresh_token
    refresh_token, jti = create_refresh_token(str(user.id))

    with patch("app.core.redis.get_redis") as mock_redis:
        mock = AsyncMock()
        mock.get = AsyncMock(return_value="valid")
        mock.delete = AsyncMock()
        mock.setex = AsyncMock()
        mock_redis.return_value = mock

        resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_email_verification(client: AsyncClient, db_session: AsyncSession):
    user = await create_test_user(db_session, email="verify@example.com", is_email_verified=False)
    from app.core.auth import create_email_verification_token
    token = create_email_verification_token(str(user.id), user.hashed_password or "")

    resp = await client.get(f"/auth/verify-email?token={token}")
    assert resp.status_code == 200
    data = resp.json()
    assert "verified" in data["message"].lower()


@pytest.mark.asyncio
async def test_forgot_password(client: AsyncClient, db_session: AsyncSession):
    await create_test_user(db_session, email="forgot@example.com")
    with patch("app.routes.auth.send_password_reset_email", new_callable=AsyncMock):
        with patch("app.core.redis.get_redis") as mock_redis:
            mock = AsyncMock()
            mock.zremrangebyscore = AsyncMock()
            mock.zadd = AsyncMock()
            mock.zcard = AsyncMock(return_value=1)
            mock.expire = AsyncMock()
            mock.zrange = AsyncMock(return_value=[])
            mock.execute = AsyncMock(return_value=[0, 1, 1, True])
            mock.pipeline.return_value = mock
            mock_redis.return_value = mock

            resp = await client.post("/auth/forgot-password", json={"email": "forgot@example.com"})
    assert resp.status_code == 202


@pytest.mark.asyncio
async def test_reset_password(client: AsyncClient, db_session: AsyncSession):
    user = await create_test_user(db_session, email="reset@example.com")
    from app.core.auth import create_password_reset_token
    token = create_password_reset_token(str(user.id), user.hashed_password or "")

    resp = await client.post("/auth/reset-password", json={
        "token": token,
        "new_password": "NewSecurePass456",
    })
    assert resp.status_code == 200
