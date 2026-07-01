import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
import enum

from app.models.base import Base


class QuestionCategory(str, enum.Enum):
    software_engineering = "software_engineering"
    data_science = "data_science"
    data_engineering = "data_engineering"
    cyber_security = "cyber_security"


class QuestionDifficulty(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class GenerationSource(str, enum.Enum):
    human = "human"
    ai_pipeline = "ai_pipeline"


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    scenario: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    supporting_logs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    supporting_metrics: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    category: Mapped[QuestionCategory] = mapped_column(
        Enum(QuestionCategory, name="question_category"), nullable=False
    )
    technologies: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    difficulty: Mapped[QuestionDifficulty] = mapped_column(
        Enum(QuestionDifficulty, name="question_difficulty"), nullable=False
    )
    is_vetted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    generation_source: Mapped[GenerationSource] = mapped_column(
        Enum(GenerationSource, name="generation_source"), nullable=False, default=GenerationSource.human
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
