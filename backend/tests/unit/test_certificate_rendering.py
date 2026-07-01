"""
Unit tests for certificate rendering in app/core/certificates.py.

Tests Pillow image generation, pixel dimensions, and PNG validity.
No S3 calls — mocked at the boundary.
"""
import io
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.core.certificates import (
    CERTIFICATE_HEIGHT,
    CERTIFICATE_WIDTH,
    _build_linkedin_url,
    _draw_certificate,
    _upload_to_s3,
    generate_certificate_image,
)


SAMPLE_SCORE_DATA = {
    "total_score": 82.5,
    "engineering_skill": 85.0,
    "ai_collaboration": 80.0,
    "ai_trust_calibration": 78.0,
    "engineering_judgement": 87.0,
}


# ── _draw_certificate ──────────────────────────────────────────────────────────

def test_draw_certificate_returns_bytes():
    result = _draw_certificate(
        user_name="Alice Engineer",
        score_data=SAMPLE_SCORE_DATA,
        session_id=uuid.uuid4(),
        issued_date=datetime.now(timezone.utc),
    )
    assert isinstance(result, bytes)
    assert len(result) > 0


def test_draw_certificate_produces_valid_png():
    """Output should be parse-able as a PNG by Pillow."""
    result = _draw_certificate(
        user_name="Bob Builder",
        score_data=SAMPLE_SCORE_DATA,
        session_id=uuid.uuid4(),
        issued_date=datetime.now(timezone.utc),
    )
    img = Image.open(io.BytesIO(result))
    assert img.format == "PNG"


def test_draw_certificate_correct_dimensions():
    result = _draw_certificate(
        user_name="Carol Candidate",
        score_data=SAMPLE_SCORE_DATA,
        session_id=uuid.uuid4(),
        issued_date=datetime.now(timezone.utc),
    )
    img = Image.open(io.BytesIO(result))
    assert img.size == (CERTIFICATE_WIDTH, CERTIFICATE_HEIGHT)


def test_draw_certificate_is_rgb():
    result = _draw_certificate(
        user_name="Dan Dev",
        score_data=SAMPLE_SCORE_DATA,
        session_id=uuid.uuid4(),
        issued_date=datetime.now(timezone.utc),
    )
    img = Image.open(io.BytesIO(result))
    assert img.mode == "RGB"


def test_draw_certificate_non_zero_bytes():
    """PNG bytes should be non-trivially sized (a meaningful image, not blank)."""
    result = _draw_certificate(
        user_name="Eve Expert",
        score_data=SAMPLE_SCORE_DATA,
        session_id=uuid.uuid4(),
        issued_date=datetime.now(timezone.utc),
    )
    assert len(result) > 5000  # A 800×600 image should be at least 5KB


def test_draw_certificate_missing_score_fields_does_not_crash():
    """_draw_certificate should handle missing score fields gracefully."""
    result = _draw_certificate(
        user_name="Frank",
        score_data={"total_score": 75.0},  # Missing dimension scores
        session_id=uuid.uuid4(),
        issued_date=datetime.now(timezone.utc),
    )
    assert isinstance(result, bytes)
    img = Image.open(io.BytesIO(result))
    assert img.format == "PNG"


def test_draw_certificate_zero_scores():
    result = _draw_certificate(
        user_name="Gina",
        score_data={
            "total_score": 0.0,
            "engineering_skill": 0.0,
            "ai_collaboration": 0.0,
            "ai_trust_calibration": 0.0,
            "engineering_judgement": 0.0,
        },
        session_id=uuid.uuid4(),
        issued_date=datetime.now(timezone.utc),
    )
    assert isinstance(result, bytes)


def test_draw_certificate_perfect_scores():
    result = _draw_certificate(
        user_name="Helena Perfect",
        score_data={
            "total_score": 100.0,
            "engineering_skill": 100.0,
            "ai_collaboration": 100.0,
            "ai_trust_calibration": 100.0,
            "engineering_judgement": 100.0,
        },
        session_id=uuid.uuid4(),
        issued_date=datetime.now(timezone.utc),
    )
    assert isinstance(result, bytes)


# ── _build_linkedin_url ────────────────────────────────────────────────────────

def test_build_linkedin_url_contains_linkedin():
    url = _build_linkedin_url(
        image_url="https://example.com/cert.png",
        user_name="Ivan",
        total_score=82.5,
    )
    assert "linkedin.com" in url


def test_build_linkedin_url_contains_score():
    url = _build_linkedin_url(
        image_url="https://example.com/cert.png",
        user_name="Julia",
        total_score=82.5,
    )
    assert "82.5" in url


def test_build_linkedin_url_contains_image_url():
    image_url = "https://mybucket.s3.amazonaws.com/certificates/abc123.png"
    url = _build_linkedin_url(image_url=image_url, user_name="Karl", total_score=77.0)
    assert "mybucket" in url or "certificates" in url


# ── generate_certificate_image (S3 mocked) ───────────────────────────────────

@pytest.mark.asyncio
async def test_generate_certificate_image_calls_s3_upload():
    """generate_certificate_image should call _upload_to_s3."""
    share_token = uuid.uuid4()
    session_id = uuid.uuid4()
    fake_url = f"https://bucket.s3.amazonaws.com/certificates/{share_token}.png"

    with patch("app.core.certificates._upload_to_s3", return_value=fake_url) as mock_upload:
        image_url, linkedin_url = await generate_certificate_image(
            user_name="Lena",
            score_data=SAMPLE_SCORE_DATA,
            session_id=session_id,
            share_token=share_token,
        )

    mock_upload.assert_called_once()
    assert image_url == fake_url


@pytest.mark.asyncio
async def test_generate_certificate_image_returns_linkedin_url():
    share_token = uuid.uuid4()
    session_id = uuid.uuid4()
    fake_url = f"https://bucket.s3.amazonaws.com/certificates/{share_token}.png"

    with patch("app.core.certificates._upload_to_s3", return_value=fake_url):
        image_url, linkedin_url = await generate_certificate_image(
            user_name="Mike",
            score_data=SAMPLE_SCORE_DATA,
            session_id=session_id,
            share_token=share_token,
        )

    assert "linkedin.com" in linkedin_url


@pytest.mark.asyncio
async def test_generate_certificate_image_s3_failure_returns_fallback():
    """When S3 upload fails, a fallback URL is returned instead of raising."""
    share_token = uuid.uuid4()
    session_id = uuid.uuid4()

    with patch("app.core.certificates._upload_to_s3", side_effect=Exception("S3 down")):
        image_url, linkedin_url = await generate_certificate_image(
            user_name="Nina",
            score_data=SAMPLE_SCORE_DATA,
            session_id=session_id,
            share_token=share_token,
        )

    # Fallback URL should still contain the share token
    assert str(share_token) in image_url
