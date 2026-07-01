import uuid

import httpx
import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    create_access_token,
    create_email_verification_token,
    create_password_reset_token,
    create_refresh_token,
    hash_password,
    verify_email_token,
    verify_password,
    verify_password_reset_token,
    verify_token,
)
from app.core.database import get_db
from app.core.email import send_password_reset_email, send_verification_email
from app.core.errors import InvalidCredentials, InvalidToken, UserNotFound
from app.core.rate_limit import rate_limit
from app.core.redis import (
    invalidate_refresh_token,
    is_refresh_token_valid,
    sliding_window_rate_limit,
    store_refresh_token,
)
from app.repository.users import UserRepository
from app.schemas.auth import (
    ForgotPasswordRequest,
    GoogleAuthRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = structlog.get_logger()

REFRESH_TOKEN_TTL = 30 * 24 * 3600  # 30 days in seconds


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(
    request: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    repo = UserRepository(db)
    existing = await repo.get_by_email(request.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    hashed_pw = hash_password(request.password)
    user = await repo.create(
        email=request.email,
        name=request.name,
        hashed_password=hashed_pw,
        auth_provider="email",
        is_email_verified=False,
    )

    verify_token_str = create_email_verification_token(str(user.id), hashed_pw)
    background_tasks.add_task(send_verification_email, user.email, verify_token_str)

    access_token = create_access_token(str(user.id))
    refresh_token, jti = create_refresh_token(str(user.id))
    await store_refresh_token(str(user.id), jti, REFRESH_TOKEN_TTL)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Rate limit: 10 req / 15 min per IP
    client_ip = http_request.client.host if http_request.client else "unknown"
    allowed, retry_after = await sliding_window_rate_limit(
        f"rl:login:{client_ip}", 10, 15 * 60
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={"error": "RATE_LIMIT_EXCEEDED", "message": "Too many login attempts", "retry_after": retry_after},
            headers={"Retry-After": str(retry_after)},
        )

    repo = UserRepository(db)
    user = await repo.get_by_email(request.email)
    if not user or not user.hashed_password:
        raise InvalidCredentials()
    if not verify_password(request.password, user.hashed_password):
        raise InvalidCredentials()
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")

    access_token = create_access_token(str(user.id))
    refresh_token, jti = create_refresh_token(str(user.id))
    await store_refresh_token(str(user.id), jti, REFRESH_TOKEN_TTL)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/google", response_model=TokenResponse)
async def google_oauth(
    request: GoogleAuthRequest,
    db: AsyncSession = Depends(get_db),
):
    """Verify Google id_token and upsert user."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": request.id_token},
        )
    if resp.status_code != 200:
        raise InvalidToken("Invalid Google token")

    data = resp.json()
    if data.get("aud") != __import__("app.core.config", fromlist=["settings"]).settings.GOOGLE_CLIENT_ID:
        raise InvalidToken("Token audience mismatch")

    email = data.get("email")
    name = data.get("name") or email.split("@")[0]
    avatar_url = data.get("picture")

    repo = UserRepository(db)
    user = await repo.get_by_email(email)
    if not user:
        user = await repo.create(
            email=email,
            name=name,
            auth_provider="google",
            avatar_url=avatar_url,
            is_email_verified=True,
        )
    else:
        await repo.update(user.id, avatar_url=avatar_url, is_email_verified=True)
        user = await repo.get_by_id(user.id)

    access_token = create_access_token(str(user.id))
    refresh_token, jti = create_refresh_token(str(user.id))
    await store_refresh_token(str(user.id), jti, REFRESH_TOKEN_TTL)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    payload = verify_token(request.refresh_token, expected_type="refresh")
    user_id = payload["sub"]
    jti = payload["jti"]

    if not await is_refresh_token_valid(user_id, jti):
        raise InvalidToken("Refresh token has been revoked or expired")

    # Rotate: invalidate old, issue new
    await invalidate_refresh_token(user_id, jti)

    repo = UserRepository(db)
    user = await repo.get_by_id(uuid.UUID(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    new_access_token = create_access_token(user_id)
    new_refresh_token, new_jti = create_refresh_token(user_id)
    await store_refresh_token(user_id, new_jti, REFRESH_TOKEN_TTL)

    return TokenResponse(access_token=new_access_token, refresh_token=new_refresh_token)


@router.post("/logout", status_code=204)
async def logout(
    request: RefreshRequest,
):
    try:
        payload = verify_token(request.refresh_token, expected_type="refresh")
        await invalidate_refresh_token(payload["sub"], payload["jti"])
    except InvalidToken:
        pass  # Logout is idempotent
    return None


@router.get("/verify-email")
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    payload = verify_email_token(token)
    user_id = uuid.UUID(payload["sub"])
    pw_hash_claim = payload.get("pw_hash")

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise UserNotFound()

    # Verify the password hash matches (invalidates tokens after password change)
    import hashlib
    expected_pw_hash = hashlib.sha256(user.hashed_password.encode()).hexdigest()[:16] if user.hashed_password else "no-pw"
    if pw_hash_claim != expected_pw_hash:
        raise InvalidToken("Verification link is no longer valid")

    await repo.update(user_id, is_email_verified=True)
    return {"message": "Email verified successfully"}


@router.post("/resend-verification", status_code=202)
async def resend_verification(
    request: ResendVerificationRequest,
    http_request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    # Rate limit: 3 req / hour per email
    allowed, retry_after = await sliding_window_rate_limit(
        f"rl:resend:{request.email}", 3, 3600
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={"error": "RATE_LIMIT_EXCEEDED", "message": "Too many resend requests", "retry_after": retry_after},
            headers={"Retry-After": str(retry_after)},
        )

    repo = UserRepository(db)
    user = await repo.get_by_email(request.email)
    if user and not user.is_email_verified:
        verify_token_str = create_email_verification_token(
            str(user.id), user.hashed_password or ""
        )
        background_tasks.add_task(send_verification_email, user.email, verify_token_str)
    # Always return 202 to avoid email enumeration
    return {"message": "If the address is registered and unverified, a new email will be sent"}


@router.post("/forgot-password", status_code=202)
async def forgot_password(
    request: ForgotPasswordRequest,
    http_request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    # Rate limit: 3 req / hour per email
    allowed, retry_after = await sliding_window_rate_limit(
        f"rl:forgot:{request.email}", 3, 3600
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={"error": "RATE_LIMIT_EXCEEDED", "message": "Too many requests", "retry_after": retry_after},
            headers={"Retry-After": str(retry_after)},
        )

    repo = UserRepository(db)
    user = await repo.get_by_email(request.email)
    if user and user.hashed_password:
        reset_token = create_password_reset_token(str(user.id), user.hashed_password)
        background_tasks.add_task(send_password_reset_email, user.email, reset_token)
    return {"message": "If the address is registered, a reset email will be sent"}


@router.post("/reset-password", status_code=200)
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    payload = verify_password_reset_token(request.token)
    user_id = uuid.UUID(payload["sub"])
    pw_hash_claim = payload.get("pw_hash")

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise UserNotFound()

    import hashlib
    expected_pw_hash = hashlib.sha256(user.hashed_password.encode()).hexdigest()[:16] if user.hashed_password else "no-pw"
    if pw_hash_claim != expected_pw_hash:
        raise InvalidToken("Reset link has already been used")

    new_hashed = hash_password(request.new_password)
    await repo.update(user_id, hashed_password=new_hashed)
    return {"message": "Password reset successfully"}
