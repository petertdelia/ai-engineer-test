import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import (
    AssessmentSession,
    EventType,
    SessionEvent,
    SessionMode,
    SessionQuestion,
    SessionStatus,
)
from app.models.question import Question

MODE_TIME_LIMITS = {
    SessionMode.trial: 20 * 60,
    SessionMode.practice: 60 * 60,
    SessionMode.exam: 90 * 60,
}


class SessionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: uuid.UUID,
        mode: str,
        difficulty: str,
    ) -> AssessmentSession:
        mode_enum = SessionMode(mode)
        time_limit = MODE_TIME_LIMITS[mode_enum]
        session = AssessmentSession(
            user_id=user_id,
            mode=mode_enum,
            difficulty=difficulty,
            time_limit_seconds=time_limit,
            status=SessionStatus.pending,
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def get_by_id(self, session_id: uuid.UUID) -> Optional[AssessmentSession]:
        result = await self.db.execute(
            select(AssessmentSession).where(AssessmentSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user(self, user_id: uuid.UUID, limit: int = 50, offset: int = 0) -> list[AssessmentSession]:
        result = await self.db.execute(
            select(AssessmentSession)
            .where(AssessmentSession.user_id == user_id)
            .order_by(AssessmentSession.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def start(
        self,
        session_id: uuid.UUID,
        questions: list[Question],
    ) -> AssessmentSession:
        now = datetime.now(timezone.utc)
        await self.db.execute(
            update(AssessmentSession)
            .where(AssessmentSession.id == session_id)
            .values(status=SessionStatus.in_progress, started_at=now)
        )

        for idx, question in enumerate(questions):
            sq = SessionQuestion(
                session_id=session_id,
                question_id=question.id,
                order_index=idx,
                ai_interactions=[],
            )
            self.db.add(sq)

        await self.db.flush()
        return await self.get_by_id(session_id)

    async def get_question(
        self, session_id: uuid.UUID, question_id: uuid.UUID
    ) -> Optional[SessionQuestion]:
        result = await self.db.execute(
            select(SessionQuestion).where(
                SessionQuestion.session_id == session_id,
                SessionQuestion.question_id == question_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_session_questions_with_details(
        self, session_id: uuid.UUID
    ) -> list[tuple[SessionQuestion, Question]]:
        result = await self.db.execute(
            select(SessionQuestion, Question)
            .join(Question, SessionQuestion.question_id == Question.id)
            .where(SessionQuestion.session_id == session_id)
            .order_by(SessionQuestion.order_index)
        )
        return result.all()

    async def save_response(
        self,
        session_id: uuid.UUID,
        question_id: uuid.UUID,
        response_text: str,
        code_response: Optional[str] = None,
    ) -> Optional[SessionQuestion]:
        now = datetime.now(timezone.utc)
        sq = await self.get_question(session_id, question_id)
        if not sq:
            return None

        sq.response_text = response_text
        sq.code_response = code_response
        sq.submitted_at = now
        await self.db.flush()
        return sq

    async def autosave_response(
        self,
        session_id: uuid.UUID,
        question_id: uuid.UUID,
        response_text: str,
        code_response: Optional[str] = None,
    ) -> Optional[SessionQuestion]:
        sq = await self.get_question(session_id, question_id)
        if not sq:
            return None

        sq.response_text = response_text
        sq.code_response = code_response
        await self.db.flush()
        return sq

    async def append_ai_interaction(
        self,
        session_id: uuid.UUID,
        question_id: uuid.UUID,
        role: str,
        content: str,
    ) -> Optional[SessionQuestion]:
        from datetime import timezone
        sq = await self.get_question(session_id, question_id)
        if not sq:
            return None

        interactions = list(sq.ai_interactions or [])
        interactions.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        sq.ai_interactions = interactions
        await self.db.flush()
        return sq

    async def complete(self, session_id: uuid.UUID) -> AssessmentSession:
        now = datetime.now(timezone.utc)
        await self.db.execute(
            update(AssessmentSession)
            .where(AssessmentSession.id == session_id)
            .values(status=SessionStatus.completed, ended_at=now)
        )
        await self.db.flush()
        return await self.get_by_id(session_id)

    async def abandon(self, session_id: uuid.UUID) -> AssessmentSession:
        now = datetime.now(timezone.utc)
        await self.db.execute(
            update(AssessmentSession)
            .where(AssessmentSession.id == session_id)
            .values(status=SessionStatus.abandoned, ended_at=now)
        )
        await self.db.flush()
        return await self.get_by_id(session_id)

    async def add_event(
        self,
        session_id: uuid.UUID,
        event_type: str,
        metadata: Optional[dict] = None,
    ) -> SessionEvent:
        event = SessionEvent(
            session_id=session_id,
            event_type=EventType(event_type),
            metadata_=metadata,
        )
        self.db.add(event)
        await self.db.flush()
        return event

    async def get_events(self, session_id: uuid.UUID) -> list[SessionEvent]:
        result = await self.db.execute(
            select(SessionEvent)
            .where(SessionEvent.session_id == session_id)
            .order_by(SessionEvent.occurred_at)
        )
        return list(result.scalars().all())

    async def flag_session(
        self,
        session_id: uuid.UUID,
        is_flagged: bool,
        flag_reason: Optional[str] = None,
    ) -> Optional[AssessmentSession]:
        values = {"is_flagged_for_review": is_flagged}
        if flag_reason is not None:
            values["flag_reason"] = flag_reason
        if not is_flagged:
            values["status"] = SessionStatus.completed  # Unflagging restores to completed
        else:
            values["status"] = SessionStatus.flagged
        await self.db.execute(
            update(AssessmentSession)
            .where(AssessmentSession.id == session_id)
            .values(**values)
        )
        await self.db.flush()
        return await self.get_by_id(session_id)

    async def disable_ai_assistant(self, session_id: uuid.UUID) -> None:
        await self.db.execute(
            update(AssessmentSession)
            .where(AssessmentSession.id == session_id)
            .values(ai_assistant_disabled=True)
        )
        await self.db.flush()

    async def list_all(
        self,
        is_flagged: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AssessmentSession]:
        query = select(AssessmentSession).order_by(AssessmentSession.created_at.desc())
        if is_flagged is not None:
            query = query.where(AssessmentSession.is_flagged_for_review == is_flagged)
        result = await self.db.execute(query.limit(limit).offset(offset))
        return list(result.scalars().all())
