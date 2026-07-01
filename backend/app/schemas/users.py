import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    name: str
    avatar_url: Optional[str]
    auth_provider: str
    is_email_verified: bool
    is_public_rank: bool
    is_active: bool
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    avatar_url: Optional[str] = Field(None, max_length=1024)


class TechStrength(BaseModel):
    technology: str
    average_score: float
    session_count: int


class ScoreTrend(BaseModel):
    session_id: uuid.UUID
    completed_at: datetime
    total_score: float
    mode: str


class StatsResponse(BaseModel):
    tech_strengths: list[TechStrength]
    score_trends: list[ScoreTrend]
    total_sessions: int
    completed_exams: int
    best_score: Optional[float]


class CertificateListItem(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    total_score: Optional[float]
    image_url: str
    share_token: uuid.UUID
    linkedin_url: str
    created_at: datetime

    model_config = {"from_attributes": True}
