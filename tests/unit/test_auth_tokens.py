"""
Unit tests for auth token helpers in app/core/auth.py.

No database, no HTTP. Tests JWT creation/verification, expiry, password
hash round-trip, and email verification token invalidation on password change.
"""
import time
import uuid
from datetime import timedelta

import pytest

from app.core.auth import (
    create_access_token,
    create_email_verification_token,
    create_password_reset_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
    verify_email_token,
    verify_password_reset_token,
)


# ── Password hashing ───────────────────────────────────────────────────────────

def test_hash_password_is_not_plaintext():
    plain = "SuperSecret123!"
    hashed = hash_password(plain)
    assert hashed != plain


def test_hash_password_different_each_call():
    plain = "SamePassword"
    h1 = hash_password(plain)
    h2 = hash_password(plain)
    assert h1 != h2  # bcrypt uses random salt


def test_verify_password_correct():
    plain = "CorrectHorseBatteryStaple"
    hashed = hash_password(plain)
    assert verify_password(plain, hashed) is True


def test_verify_password_wrong():
    plain = "CorrectHorseBatteryStaple"
    hashed = hash_password(plain)
    assert verify_password("WrongPassword", hashed) is False


def test_verify_password_empty_fails():
    hashed = hash_password("SomePassword")
    assert verify_password("", hashed) is False


# ── Access tokens ──────────────────────────────────────────────────────────────

def test_create_access_token_returns_string():
    user_id = str(uuid.uuid4())
    token = create_access_token(user_id)
    assert isinstance(token, str)
    assert len(token) > 20


def test_verify_access_token_returns_correct_sub():
    user_id = str(uuid.uuid4())
    token = create_access_token(user_id)
    payload = verify_token(token, expected_type="access")
    assert payload["sub"] == user_id


def test_verify_access_token_type():
    user_id = str(uuid.uuid4())
    token = create_access_token(user_id)
    payload = verify_token(token, expected_type="access")
    assert payload.get("type") == "access"


def test_expired_access_token_raises():
    import jwt as _jwt
    from datetime import datetime, timezone
    import app.core.config as _cfg
    user_id = str(uuid.uuid4())
    # Manually encode a token that is already expired
    from app.core.auth import ALGORITHM
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(seconds=-1),
    }
    token = _jwt.encode(payload, _cfg.settings.SECRET_KEY, algorithm=ALGORITHM)
    with pytest.raises(Exception):  # jwt.ExpiredSignatureError or our wrapper
        verify_token(token, expected_type="access")


def test_tampered_token_raises():
    user_id = str(uuid.uuid4())
    token = create_access_token(user_id)
    # Flip one character in the signature
    tampered = token[:-3] + "XXX"
    with pytest.raises(Exception):
        verify_token(tampered, expected_type="access")


# ── Refresh tokens ─────────────────────────────────────────────────────────────

def test_create_refresh_token_returns_string_and_jti():
    user_id = str(uuid.uuid4())
    token, jti = create_refresh_token(user_id)
    assert isinstance(token, str)
    assert isinstance(jti, str)
    assert len(jti) > 0


def test_refresh_token_jti_unique():
    user_id = str(uuid.uuid4())
    _, jti1 = create_refresh_token(user_id)
    _, jti2 = create_refresh_token(user_id)
    assert jti1 != jti2


def test_refresh_token_type():
    user_id = str(uuid.uuid4())
    token, _ = create_refresh_token(user_id)
    payload = verify_token(token, expected_type="refresh")
    assert payload.get("type") == "refresh"


# ── Email verification tokens ──────────────────────────────────────────────────

def test_email_verification_token_is_string():
    user_id = str(uuid.uuid4())
    hashed_pw = hash_password("SomePassword")
    token = create_email_verification_token(user_id, hashed_pw)
    assert isinstance(token, str)
    assert len(token) > 20


def test_email_verification_token_verifies():
    user_id = str(uuid.uuid4())
    hashed_pw = hash_password("SomePassword")
    token = create_email_verification_token(user_id, hashed_pw)
    payload = verify_email_token(token)
    assert payload["sub"] == user_id


def test_email_verification_token_invalidated_after_pw_change():
    """
    Token embeds a hash of the first 16 chars of hashed_password.
    If the password changes, the new token's pw_hash will differ — the old
    token is stale and the route should reject it.

    This test verifies that two different passwords produce different pw_hash
    values in the payload, simulating the invalidation logic.
    """
    user_id = str(uuid.uuid4())
    old_hashed_pw = hash_password("OldPassword123")
    new_hashed_pw = hash_password("NewPassword456")

    old_token = create_email_verification_token(user_id, old_hashed_pw)
    new_token = create_email_verification_token(user_id, new_hashed_pw)

    old_payload = verify_email_token(old_token)
    new_payload = verify_email_token(new_token)

    # The embedded pw_hash fingerprint must differ so old token is invalidated
    assert old_payload.get("pw_hash") != new_payload.get("pw_hash")


# ── Password reset tokens ──────────────────────────────────────────────────────

def test_password_reset_token_is_string():
    user_id = str(uuid.uuid4())
    hashed_pw = hash_password("ResetMyPassword99")
    token = create_password_reset_token(user_id, hashed_pw)
    assert isinstance(token, str)


def test_password_reset_token_type():
    user_id = str(uuid.uuid4())
    hashed_pw = hash_password("ResetMyPassword99")
    token = create_password_reset_token(user_id, hashed_pw)
    payload = verify_password_reset_token(token)
    assert payload.get("purpose") == "password_reset"
    assert payload["sub"] == user_id
