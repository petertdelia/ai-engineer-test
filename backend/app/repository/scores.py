import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.score import ScoreStatus, SessionScore


class ScoreRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_pending(self, session_id: uuid.UUID) -> SessionScore:
        score = SessionScore(
            session_id=session_id,
            status=ScoreStatus.pending,
        )
        self.db.add(score)
        await self.db.flush()
        await self.db.refresh(score)
        return score

    async def update_score(
        self,
        session_id: uuid.UUID,
        engineering_skill: float,
        ai_collaboration: float,
        ai_trust_calibration: float,
        engineering_judgement: float,
        total_score: float,
    ) -> Optional[SessionScore]:
        now = datetime.now(timezone.utc)
        await self.db.execute(
            update(SessionScore)
            .where(SessionScore.session_id == session_id)
            .values(
                status=ScoreStatus.completed,
                engineering_skill=engineering_skill,
                ai_collaboration=ai_collaboration,
                ai_trust_calibration=ai_trust_calibration,
                engineering_judgement=engineering_judgement,
                total_score=total_score,
                computed_at=now,
            )
        )
        await self.db.flush()
        return await self.get_by_session(session_id)

    async def set_failed(self, session_id: uuid.UUID, failure_reason: str) -> None:
        await self.db.execute(
            update(SessionScore)
            .where(SessionScore.session_id == session_id)
            .values(status=ScoreStatus.failed, failure_reason=failure_reason)
        )
        await self.db.flush()

    async def get_by_session(self, session_id: uuid.UUID) -> Optional[SessionScore]:
        result = await self.db.execute(
            select(SessionScore).where(SessionScore.session_id == session_id)
        )
        return result.scalar_one_or_none()
