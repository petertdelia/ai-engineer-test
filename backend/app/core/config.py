from typing import Any, List, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://crucible:crucible@localhost:5432/crucible"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    SECRET_KEY: str = "change-me-in-production"

    # Anthropic
    ANTHROPIC_API_KEY: str = ""

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # AWS / S3
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_DEFAULT_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "crucible-certificates"

    # Sentry
    SENTRY_DSN: Optional[str] = None

    # Email
    RESEND_API_KEY: str = ""

    # Business constants
    CERTIFICATE_MIN_SCORE: float = 75.0
    LEADERBOARD_MIN_POPULATION: int = 100

    # Session inactivity timeouts (seconds) per mode
    INACTIVITY_TIMEOUT_TRIAL: int = 600       # 10 minutes
    INACTIVITY_TIMEOUT_PRACTICE: int = 900    # 15 minutes
    INACTIVITY_TIMEOUT_EXAM: int = 1800       # 30 minutes

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def fix_postgres_scheme(cls, v: Any) -> str:
        if isinstance(v, str) and v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        return v

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except Exception:
                return [origin.strip() for origin in v.split(",")]
        return v


settings = Settings()
