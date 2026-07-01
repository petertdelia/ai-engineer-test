import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    mode: str = Field(pattern="^(trial|practice|exam)$")
    difficulty: str = Field(pattern="^(low|medium|high)$")


class AIInteraction(BaseModel):
    role: str
    content: str
    timestamp: Optional[datetime] = None


class QuestionInSession(BaseModel):
    id: uuid.UUID
    question_id: uuid.UUID
    order_index: int
    title: str
    scenario: str
    supporting_code: Optional[str]
    supporting_logs: Optional[str]
    supporting_metrics: Optional[Any]
    category: str
    technologies: list[str]
    difficulty: str
    response_text: Optional[str]
    code_response: Optional[str]
    ai_interactions: list[dict]
    started_at: Optional[datetime]
    submitted_at: Optional[datetime]

    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    id: uuid.UUID
    mode: str
    difficulty: str
    status: str
    time_limit_seconds: int
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    ai_assistant_disabled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class StartSessionResponse(BaseModel):
    id: uuid.UUID
    mode: str
    difficulty: str
    status: str
    time_limit_seconds: int
    started_at: Optional[datetime]
    questions: list[QuestionInSession]
    ai_assistant_disabled: bool

    model_config = {"from_attributes": True}


class SessionDetailResponse(BaseModel):
    id: uuid.UUID
    mode: str
    difficulty: str
    status: str
    time_limit_seconds: int
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    ai_assistant_disabled: bool
    is_flagged_for_review: bool
    questions: list[QuestionInSession]
    created_at: datetime

    model_config = {"from_attributes": True}


class RespondRequest(BaseModel):
    response_text: str = Field(max_length=50000)
    code_response: Optional[str] = Field(None, max_length=50000)


class AutosaveRequest(BaseModel):
    response_text: str = Field(max_length=50000)
    code_response: Optional[str] = Field(None, max_length=50000)


class AIChatRequest(BaseModel):
    message: str = Field(max_length=2000)


class SessionEventRequest(BaseModel):
    event_type: str
    metadata: Optional[dict] = None


class SessionListItem(BaseModel):
    id: uuid.UUID
    mode: str
    difficulty: str
    status: str
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}
