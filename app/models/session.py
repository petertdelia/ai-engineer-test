import uuid
import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SessionMode(str, enum.Enum):
    trial = "trial"
    practice = "practice"
    exam = "exam"


class SessionDifficulty(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class SessionStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    abandoned = "abandoned"
    flagged = "flagged"


class EventType(str, enum.Enum):
    leave_page = "leave_page"
    return_to_page = "return_to_page"
    inactivity_warning = "inactivity_warning"
    tab_blur = "tab_blur"
    copy_paste = "copy_paste"


class AssessmentSession(Base):
    __tablename__ = "assessment_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    mode: Mapped[SessionMode] = mapped_column(
        Enum(SessionMode, name="session_mode"), nullable=False
    )
    difficulty: Mapped[SessionDifficulty] = mapped_column(
        Enum(SessionDifficulty, name="session_difficulty"), nullable=False
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    time_limit_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status"),
        nullable=False,
        default=SessionStatus.pending,
    )
    is_flagged_for_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    flag_reason: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    ai_assistant_disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SessionQuestion(Base):
    __tablename__ = "session_questions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("questions.id"), nullable=False
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    response_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    code_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_interactions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    score_engineering_skill: Mapped[Optional[float]] = mapped_column(nullable=True)
    score_ai_collaboration: Mapped[Optional[float]] = mapped_column(nullable=True)
    score_ai_trust_calibration: Mapped[Optional[float]] = mapped_column(nullable=True)
    score_engineering_judgement: Mapped[Optional[float]] = mapped_column(nullable=True)
    scoring_notes: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class SessionEvent(Base):
    __tablename__ = "session_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[EventType] = mapped_column(
        Enum(EventType, name="event_type"), nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)
