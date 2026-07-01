import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt as _bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import InvalidToken, UnverifiedEmailRequired

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 30

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return _bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def create_access_token(user_id: str, extra_claims: Optional[dict] = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: str) -> tuple[str, str]:
    """Returns (token, jti) where jti is the unique identifier stored in Redis."""
    now = datetime.now(timezone.utc)
    jti = str(uuid.uuid4())
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": jti,
        "iat": now,
        "exp": now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)
    return token, jti


def verify_token(token: str, expected_type: str = "access") -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != expected_type:
            raise InvalidToken("Token type mismatch")
        return payload
    except jwt.ExpiredSignatureError:
        raise InvalidToken("Token has expired")
    except jwt.InvalidTokenError:
        raise InvalidToken("Invalid token")


def create_email_verification_token(user_id: str, hashed_password: str) -> str:
    now = datetime.now(timezone.utc)
    # Embed a hash of the hashed_password to invalidate on password change
    import hashlib
    pw_hash = hashlib.sha256(hashed_password.encode()).hexdigest()[:16] if hashed_password else "no-pw"
    payload = {
        "sub": str(user_id),
        "purpose": "email_verify",
        "pw_hash": pw_hash,
        "iat": now,
        "exp": now + timedelta(hours=24),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def verify_email_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("purpose") != "email_verify":
            raise InvalidToken("Invalid token purpose")
        return payload
    except jwt.ExpiredSignatureError:
        raise InvalidToken("Verification link has expired")
    except jwt.InvalidTokenError:
        raise InvalidToken("Invalid verification token")


def create_password_reset_token(user_id: str, hashed_password: str) -> str:
    now = datetime.now(timezone.utc)
    import hashlib
    pw_hash = hashlib.sha256(hashed_password.encode()).hexdigest()[:16] if hashed_password else "no-pw"
    payload = {
        "sub": str(user_id),
        "purpose": "password_reset",
        "pw_hash": pw_hash,
        "iat": now,
        "exp": now + timedelta(hours=1),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def verify_password_reset_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("purpose") != "password_reset":
            raise InvalidToken("Invalid token purpose")
        return payload
    except jwt.ExpiredSignatureError:
        raise InvalidToken("Reset link has expired")
    except jwt.InvalidTokenError:
        raise InvalidToken("Invalid reset token")


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
):
    from app.repository.users import UserRepository

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_token(credentials.credentials, expected_type="access")
    user_id = payload.get("sub")
    if not user_id:
        raise InvalidToken("Token missing subject")

    repo = UserRepository(db)
    user = await repo.get_by_id(uuid.UUID(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


async def require_verified_email(current_user=Depends(get_current_user)):
    if not current_user.is_email_verified:
        raise UnverifiedEmailRequired()
    return current_user


async def require_admin(current_user=Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
