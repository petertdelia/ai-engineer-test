import uuid
import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ScoreStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"


class SessionScore(Base):
    __tablename__ = "session_scores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[ScoreStatus] = mapped_column(
        Enum(ScoreStatus, name="score_status"),
        nullable=False,
        default=ScoreStatus.pending,
    )
    engineering_skill: Mapped[Optional[float]] = mapped_column(nullable=True)
    ai_collaboration: Mapped[Optional[float]] = mapped_column(nullable=True)
    ai_trust_calibration: Mapped[Optional[float]] = mapped_column(nullable=True)
    engineering_judgement: Mapped[Optional[float]] = mapped_column(nullable=True)
    total_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    percentile_rank: Mapped[Optional[float]] = mapped_column(nullable=True)
    computed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
