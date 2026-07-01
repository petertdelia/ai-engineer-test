import io
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode

import boto3
import structlog
from PIL import Image, ImageDraw, ImageFont

from app.core.config import settings

logger = structlog.get_logger()

CERTIFICATE_WIDTH = 800
CERTIFICATE_HEIGHT = 600
BACKGROUND_COLOR = (15, 23, 42)       # dark navy
ACCENT_COLOR = (99, 102, 241)          # indigo
TEXT_COLOR = (248, 250, 252)           # near-white
SCORE_COLOR = (52, 211, 153)           # emerald


def _draw_certificate(
    user_name: str,
    score_data: dict,
    session_id: uuid.UUID,
    issued_date: datetime,
) -> bytes:
    """Generate a certificate image and return PNG bytes."""
    img = Image.new("RGB", (CERTIFICATE_WIDTH, CERTIFICATE_HEIGHT), BACKGROUND_COLOR)
    draw = ImageDraw.Draw(img)

    # Try to load a font, fall back to default
    try:
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36)
        subtitle_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
        body_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except OSError:
        title_font = ImageFont.load_default()
        subtitle_font = title_font
        body_font = title_font
        small_font = title_font

    # Border
    draw.rectangle([10, 10, CERTIFICATE_WIDTH - 10, CERTIFICATE_HEIGHT - 10], outline=ACCENT_COLOR, width=3)

    # Title
    draw.text((CERTIFICATE_WIDTH // 2, 60), "CRUCIBLE", font=title_font, fill=ACCENT_COLOR, anchor="mm")
    draw.text((CERTIFICATE_WIDTH // 2, 95), "AI Engineering Assessment Certificate", font=subtitle_font, fill=TEXT_COLOR, anchor="mm")

    # Divider
    draw.line([(80, 120), (CERTIFICATE_WIDTH - 80, 120)], fill=ACCENT_COLOR, width=1)

    # Recipient
    draw.text((CERTIFICATE_WIDTH // 2, 165), "This certifies that", font=body_font, fill=TEXT_COLOR, anchor="mm")
    draw.text((CERTIFICATE_WIDTH // 2, 205), user_name, font=title_font, fill=TEXT_COLOR, anchor="mm")
    draw.text((CERTIFICATE_WIDTH // 2, 245), "has demonstrated AI engineering proficiency", font=body_font, fill=TEXT_COLOR, anchor="mm")

    # Score section
    total_score = score_data.get("total_score", 0)
    draw.text((CERTIFICATE_WIDTH // 2, 295), f"Overall Score: {total_score:.1f}/100", font=subtitle_font, fill=SCORE_COLOR, anchor="mm")

    # Dimension scores
    dims = [
        ("Engineering Skill", score_data.get("engineering_skill", 0)),
        ("AI Collaboration", score_data.get("ai_collaboration", 0)),
        ("AI Trust Calibration", score_data.get("ai_trust_calibration", 0)),
        ("Engineering Judgement", score_data.get("engineering_judgement", 0)),
    ]
    x_start = 100
    y_pos = 340
    for i, (dim_name, dim_score) in enumerate(dims):
        x = x_start + (i % 2) * 300
        y = y_pos + (i // 2) * 50
        draw.text((x, y), f"{dim_name}:", font=small_font, fill=TEXT_COLOR)
        draw.text((x + 180, y), f"{dim_score:.1f}", font=small_font, fill=SCORE_COLOR)

    # Divider
    draw.line([(80, 460), (CERTIFICATE_WIDTH - 80, 460)], fill=ACCENT_COLOR, width=1)

    # Footer
    date_str = issued_date.strftime("%B %d, %Y")
    draw.text((CERTIFICATE_WIDTH // 2, 490), f"Issued: {date_str}", font=small_font, fill=TEXT_COLOR, anchor="mm")
    session_str = f"Session: {str(session_id)[:8]}..."
    draw.text((CERTIFICATE_WIDTH // 2, 515), session_str, font=small_font, fill=TEXT_COLOR, anchor="mm")
    draw.text((CERTIFICATE_WIDTH // 2, 545), "crucible.ai", font=small_font, fill=ACCENT_COLOR, anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _upload_to_s3(image_bytes: bytes, key: str) -> str:
    """Upload bytes to S3 and return the public URL."""
    s3 = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_DEFAULT_REGION,
    )
    s3.put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=key,
        Body=image_bytes,
        ContentType="image/png",
        ACL="public-read",
    )
    return f"https://{settings.S3_BUCKET_NAME}.s3.{settings.AWS_DEFAULT_REGION}.amazonaws.com/{key}"


def _build_linkedin_url(image_url: str, user_name: str, total_score: float) -> str:
    params = {
        "mini": "true",
        "url": image_url,
        "title": f"{user_name} — Crucible AI Engineering Certificate",
        "summary": f"Achieved a score of {total_score:.1f}/100 on the Crucible AI Engineering Assessment",
        "source": "Crucible",
    }
    return "https://www.linkedin.com/shareArticle?" + urlencode(params)


async def generate_certificate_image(
    user_name: str,
    score_data: dict,
    session_id: uuid.UUID,
    share_token: uuid.UUID,
) -> tuple[str, str]:
    """
    Generate and upload certificate image.
    Returns (image_url, linkedin_url).
    """
    issued_date = datetime.now(timezone.utc)
    image_bytes = _draw_certificate(user_name, score_data, session_id, issued_date)

    s3_key = f"certificates/{share_token}.png"

    try:
        image_url = _upload_to_s3(image_bytes, s3_key)
    except Exception as e:
        logger.error("s3_upload_failed", error=str(e))
        # Fallback: use a placeholder URL (in production this should raise)
        image_url = f"/certificates/{share_token}.png"

    linkedin_url = _build_linkedin_url(image_url, user_name, score_data.get("total_score", 0))
    return image_url, linkedin_url
