import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class QuestionResponse(BaseModel):
    id: uuid.UUID
    title: str
    scenario: str
    supporting_code: Optional[str]
    supporting_logs: Optional[str]
    supporting_metrics: Optional[Any]
    category: str
    technologies: list[str]
    difficulty: str
    is_vetted: bool
    is_active: bool
    generation_source: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreateQuestionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    scenario: str = Field(min_length=10)
    supporting_code: Optional[str] = None
    supporting_logs: Optional[str] = None
    supporting_metrics: Optional[Any] = None
    category: str = Field(pattern="^(software_engineering|data_science|data_engineering|cyber_security)$")
    technologies: list[str] = Field(min_length=1)
    difficulty: str = Field(pattern="^(low|medium|high)$")
    generation_source: str = Field(default="human", pattern="^(human|ai_pipeline)$")


class UpdateQuestionRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    scenario: Optional[str] = Field(None, min_length=10)
    supporting_code: Optional[str] = None
    supporting_logs: Optional[str] = None
    supporting_metrics: Optional[Any] = None
    category: Optional[str] = Field(None, pattern="^(software_engineering|data_science|data_engineering|cyber_security)$")
    technologies: Optional[list[str]] = None
    difficulty: Optional[str] = Field(None, pattern="^(low|medium|high)$")
    is_active: Optional[bool] = None
