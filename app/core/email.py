import resend
import structlog

from app.core.config import settings

logger = structlog.get_logger()

FROM_ADDRESS = "noreply@crucible.ai"
APP_BASE_URL = "https://crucible.ai"


def _configure_resend() -> None:
    resend.api_key = settings.RESEND_API_KEY


async def send_verification_email(email: str, token: str) -> None:
    _configure_resend()
    verify_url = f"{APP_BASE_URL}/auth/verify-email?token={token}"
    html_content = f"""
    <html>
    <body style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h1 style="color: #6366f1;">Verify your Crucible account</h1>
        <p>Click the link below to verify your email address. This link expires in 24 hours.</p>
        <a href="{verify_url}" style="display: inline-block; background: #6366f1; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
            Verify Email
        </a>
        <p style="color: #6b7280; margin-top: 24px; font-size: 14px;">
            If you didn't create a Crucible account, you can safely ignore this email.
        </p>
    </body>
    </html>
    """
    try:
        params: resend.Emails.SendParams = {
            "from": FROM_ADDRESS,
            "to": [email],
            "subject": "Verify your Crucible account",
            "html": html_content,
        }
        resend.Emails.send(params)
        logger.info("verification_email_sent", email=email)
    except Exception as e:
        logger.error("verification_email_failed", email=email, error=str(e))


async def send_password_reset_email(email: str, token: str) -> None:
    _configure_resend()
    reset_url = f"{APP_BASE_URL}/auth/reset-password?token={token}"
    html_content = f"""
    <html>
    <body style="font-family: sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h1 style="color: #6366f1;">Reset your Crucible password</h1>
        <p>Click the link below to reset your password. This link expires in 1 hour.</p>
        <a href="{reset_url}" style="display: inline-block; background: #6366f1; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px;">
            Reset Password
        </a>
        <p style="color: #6b7280; margin-top: 24px; font-size: 14px;">
            If you didn't request a password reset, you can safely ignore this email.
        </p>
    </body>
    </html>
    """
    try:
        params: resend.Emails.SendParams = {
            "from": FROM_ADDRESS,
            "to": [email],
            "subject": "Reset your Crucible password",
            "html": html_content,
        }
        resend.Emails.send(params)
        logger.info("password_reset_email_sent", email=email)
    except Exception as e:
        logger.error("password_reset_email_failed", email=email, error=str(e))
