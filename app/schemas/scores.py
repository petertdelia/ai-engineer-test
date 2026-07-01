import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class QuestionScoreDetail(BaseModel):
    question_id: uuid.UUID
    order_index: int
    title: str
    response_text: Optional[str]
    score_engineering_skill: Optional[float]
    score_ai_collaboration: Optional[float]
    score_ai_trust_calibration: Optional[float]
    score_engineering_judgement: Optional[float]
    scoring_notes: Optional[dict]
    ai_interactions: list[dict]

    model_config = {"from_attributes": True}


class ResultsResponse(BaseModel):
    status: str  # "pending" | "completed" | "failed" | "not_scored"
    mode: Optional[str] = None
    session_id: uuid.UUID
    engineering_skill: Optional[float] = None
    ai_collaboration: Optional[float] = None
    ai_trust_calibration: Optional[float] = None
    engineering_judgement: Optional[float] = None
    total_score: Optional[float] = None
    percentile_rank: Optional[float] = None
    computed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    question_details: Optional[list[QuestionScoreDetail]] = None


class ScoreStatus(BaseModel):
    status: str
    session_id: uuid.UUID
    failure_reason: Optional[str] = None
