import uuid
from typing import Optional

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.core.auth import get_current_user, require_admin
from app.core.database import get_db
from app.core.errors import SessionNotFound
from app.core.redis import sliding_window_rate_limit
from app.models.score import ScoreStatus, SessionScore
from app.models.session import AssessmentSession, SessionMode, SessionStatus
from app.models.user import User
from app.repository.questions import QuestionRepository
from app.repository.scores import ScoreRepository
from app.repository.sessions import SessionRepository
from app.repository.users import UserRepository
from app.schemas.questions import CreateQuestionRequest, QuestionResponse, UpdateQuestionRequest
from app.workers.pipeline import generate_questions_task
from app.workers.scoring import score_session_task

router = APIRouter(prefix="/admin", tags=["admin"])
logger = structlog.get_logger()


# ─── Questions ───────────────────────────────────────────────────────────────

@router.get("/questions", response_model=list[QuestionResponse])
async def list_questions(
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    is_vetted: Optional[bool] = None,
    is_active: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    repo = QuestionRepository(db)
    questions, total = await repo.list_filtered(
        category=category,
        difficulty=difficulty,
        is_vetted=is_vetted,
        is_active=is_active,
        limit=limit,
        offset=offset,
    )
    return questions


@router.get("/questions/{question_id}", response_model=QuestionResponse)
async def get_question(
    question_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    repo = QuestionRepository(db)
    q = await repo.get_by_id(question_id)
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    return q


@router.post("/questions", response_model=QuestionResponse, status_code=201)
async def create_question(
    request: CreateQuestionRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    repo = QuestionRepository(db)
    return await repo.create(**request.model_dump())


@router.patch("/questions/{question_id}", response_model=QuestionResponse)
async def update_question(
    question_id: uuid.UUID,
    request: UpdateQuestionRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    repo = QuestionRepository(db)
    q = await repo.get_by_id(question_id)
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    updates = request.model_dump(exclude_unset=True)
    return await repo.update(question_id, **updates)


@router.delete("/questions/{question_id}", status_code=204)
async def delete_question(
    question_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    repo = QuestionRepository(db)
    q = await repo.get_by_id(question_id)
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    await repo.soft_delete(question_id)
    return None


@router.post("/questions/{question_id}/vet", response_model=QuestionResponse)
async def vet_question(
    question_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    repo = QuestionRepository(db)
    q = await repo.vet(question_id)
    if not q:
        raise HTTPException(status_code=404, detail="Question not found")
    return q


# ─── Pipeline ─────────────────────────────────────────────────────────────────

class PipelineGenerateRequest(BaseModel):
    category: str = Field(pattern="^(software_engineering|data_science|data_engineering|cyber_security)$")
    difficulty: str = Field(pattern="^(low|medium|high)$")
    count: int = Field(default=5, ge=1, le=20)


@router.post("/pipeline/generate")
async def trigger_pipeline(
    request: PipelineGenerateRequest,
    http_request: __import__("fastapi").Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    # Rate limit: 5 req / hour per admin
    allowed, retry_after = await sliding_window_rate_limit(
        f"rl:pipeline:{admin.id}", 5, 3600
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={"error": "RATE_LIMIT_EXCEEDED", "message": "Pipeline trigger rate limit exceeded", "retry_after": retry_after},
            headers={"Retry-After": str(retry_after)},
        )

    from app.models.pipeline import PipelineRun, PipelineStatus
    run = PipelineRun(
        triggered_by=str(admin.id),
        category=request.category,
        difficulty=request.difficulty,
        status=PipelineStatus.running,
    )
    db.add(run)
    await db.flush()
    await db.commit()

    generate_questions_task.delay(str(run.id), request.category, request.difficulty, request.count)

    return {"message": "Pipeline triggered", "run_id": str(run.id)}


@router.get("/pipeline/runs")
async def list_pipeline_runs(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    from app.models.pipeline import PipelineRun
    from sqlalchemy import select
    result = await db.execute(
        select(PipelineRun).order_by(PipelineRun.started_at.desc()).limit(limit).offset(offset)
    )
    runs = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "triggered_by": r.triggered_by,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "ended_at": r.ended_at.isoformat() if r.ended_at else None,
            "status": r.status.value,
            "category": r.category,
            "difficulty": r.difficulty,
            "generated_count": r.generated_count,
            "passed_count": r.passed_count,
            "held_count": r.held_count,
            "failed_count": r.failed_count,
            "error_message": r.error_message,
        }
        for r in runs
    ]


# ─── Sessions ─────────────────────────────────────────────────────────────────

class FlagSessionRequest(BaseModel):
    is_flagged: bool
    flag_reason: Optional[str] = None


@router.get("/sessions")
async def list_admin_sessions(
    is_flagged: Optional[bool] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    repo = SessionRepository(db)
    sessions = await repo.list_all(is_flagged=is_flagged, limit=limit, offset=offset)
    return [
        {
            "id": str(s.id),
            "user_id": str(s.user_id) if s.user_id else None,
            "mode": s.mode.value,
            "difficulty": s.difficulty.value,
            "status": s.status.value,
            "is_flagged_for_review": s.is_flagged_for_review,
            "flag_reason": s.flag_reason,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "ended_at": s.ended_at.isoformat() if s.ended_at else None,
        }
        for s in sessions
    ]


@router.patch("/sessions/{session_id}/flag")
async def flag_session(
    session_id: uuid.UUID,
    request: FlagSessionRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    repo = SessionRepository(db)
    session = await repo.get_by_id(session_id)
    if not session:
        raise SessionNotFound()
    updated = await repo.flag_session(session_id, request.is_flagged, request.flag_reason)
    return {"message": "Session flag updated", "session_id": str(session_id)}


@router.get("/sessions/{session_id}/events")
async def get_session_events(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    repo = SessionRepository(db)
    session = await repo.get_by_id(session_id)
    if not session:
        raise SessionNotFound()
    events = await repo.get_events(session_id)
    return [
        {
            "id": str(e.id),
            "event_type": e.event_type.value,
            "occurred_at": e.occurred_at.isoformat(),
            "metadata": e.metadata_,
        }
        for e in events
    ]


@router.post("/sessions/{session_id}/rescore")
async def rescore_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Re-queue scoring for a session that failed."""
    repo = SessionRepository(db)
    session = await repo.get_by_id(session_id)
    if not session:
        raise SessionNotFound()

    score_repo = ScoreRepository(db)
    score = await score_repo.get_by_session(session_id)
    if not score:
        # Create a new pending score record
        await score_repo.create_pending(session_id)
    else:
        # Reset to pending
        from sqlalchemy import update
        from app.models.score import SessionScore
        await db.execute(
            update(SessionScore)
            .where(SessionScore.session_id == session_id)
            .values(status=ScoreStatus.pending, failure_reason=None)
        )
        await db.flush()

    score_session_task.delay(str(session_id))

    return {"message": "Scoring re-queued", "session_id": str(session_id)}


# ─── Stats ────────────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_platform_stats(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    from app.models.user import User as UserModel

    user_count_result = await db.execute(select(func.count(UserModel.id)))
    total_users = user_count_result.scalar_one()

    session_mode_result = await db.execute(
        select(AssessmentSession.mode, func.count().label("count"))
        .where(AssessmentSession.status == SessionStatus.completed)
        .group_by(AssessmentSession.mode)
    )
    sessions_by_mode = {row.mode.value: row.count for row in session_mode_result.all()}

    from app.models.question import Question
    question_counts_result = await db.execute(
        select(Question.category, Question.difficulty, func.count().label("count"))
        .where(Question.is_active == True)
        .group_by(Question.category, Question.difficulty)
    )
    question_counts = [
        {"category": row.category.value, "difficulty": row.difficulty.value, "count": row.count}
        for row in question_counts_result.all()
    ]

    return {
        "total_users": total_users,
        "sessions_by_mode": sessions_by_mode,
        "question_bank": question_counts,
    }


# ─── Users ────────────────────────────────────────────────────────────────────

class UpdateUserAdminRequest(BaseModel):
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None


@router.get("/users")
async def search_users(
    query: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    from sqlalchemy import or_
    from app.models.user import User as UserModel

    stmt = select(UserModel)
    if query:
        stmt = stmt.where(
            or_(
                UserModel.email.ilike(f"%{query}%"),
                UserModel.name.ilike(f"%{query}%"),
            )
        )
    result = await db.execute(stmt.order_by(UserModel.created_at.desc()).limit(limit).offset(offset))
    users = result.scalars().all()
    return [
        {
            "id": str(u.id),
            "email": u.email,
            "name": u.name,
            "is_active": u.is_active,
            "is_admin": u.is_admin,
            "is_email_verified": u.is_email_verified,
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]


@router.get("/users/{user_id}")
async def get_admin_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    from app.models.user import User as UserModel
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    session_repo = SessionRepository(db)
    sessions = await session_repo.get_by_user(user_id, limit=20)

    return {
        "id": str(user.id),
        "email": user.email,
        "name": user.name,
        "is_active": user.is_active,
        "is_admin": user.is_admin,
        "is_email_verified": user.is_email_verified,
        "created_at": user.created_at.isoformat(),
        "sessions": [
            {
                "id": str(s.id),
                "mode": s.mode.value,
                "status": s.status.value,
                "created_at": s.created_at.isoformat(),
            }
            for s in sessions
        ],
    }


@router.patch("/users/{user_id}")
async def update_admin_user(
    user_id: uuid.UUID,
    request: UpdateUserAdminRequest,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    updates = request.model_dump(exclude_unset=True)
    updated = await user_repo.update(user_id, **updates)
    return {"message": "User updated", "user_id": str(user_id)}


@router.post("/users/{user_id}/delete", status_code=204)
async def admin_delete_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await user_repo.delete(user_id)
    return None
