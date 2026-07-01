import json
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ai import MAX_TURNS_PER_QUESTION, get_ai_response_stream
from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.errors import (
    AIAssistantDisabled,
    InsufficientQuestions,
    SessionAlreadyCompleted,
    SessionExpired,
    SessionNotFound,
    SessionNotInProgress,
    TurnLimitExceeded,
    UnverifiedEmailRequired,
)
from app.core.redis import (
    sliding_window_rate_limit,
    update_session_activity,
)
from app.models.session import SessionMode, SessionStatus
from app.models.user import User
from app.repository.questions import QuestionRepository
from app.repository.sessions import SessionRepository
from app.schemas.sessions import (
    AIChatRequest,
    AutosaveRequest,
    CreateSessionRequest,
    RespondRequest,
    SessionDetailResponse,
    SessionEventRequest,
    SessionListItem,
    SessionResponse,
    StartSessionResponse,
    QuestionInSession,
)

router = APIRouter(prefix="/sessions", tags=["sessions"])
logger = structlog.get_logger()


def _build_question_in_session(sq, q) -> dict:
    return {
        "id": sq.id,
        "question_id": sq.question_id,
        "order_index": sq.order_index,
        "title": q.title,
        "scenario": q.scenario,
        "supporting_code": q.supporting_code,
        "supporting_logs": q.supporting_logs,
        "supporting_metrics": q.supporting_metrics,
        "category": q.category.value,
        "technologies": q.technologies,
        "difficulty": q.difficulty.value,
        "response_text": sq.response_text,
        "code_response": sq.code_response,
        "ai_interactions": sq.ai_interactions or [],
        "started_at": sq.started_at,
        "submitted_at": sq.submitted_at,
    }


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    request: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = SessionRepository(db)
    session = await repo.create(
        user_id=current_user.id,
        mode=request.mode,
        difficulty=request.difficulty,
    )
    return session


@router.get("", response_model=list[SessionListItem])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = SessionRepository(db)
    sessions = await repo.get_by_user(current_user.id)
    return sessions


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = SessionRepository(db)
    session = await repo.get_by_id(session_id)
    if not session or session.user_id != current_user.id:
        raise SessionNotFound()

    questions_with_detail = await repo.get_session_questions_with_details(session_id)

    include_content = session.status in (SessionStatus.in_progress, SessionStatus.completed, SessionStatus.flagged)
    questions = []
    if include_content:
        for sq, q in questions_with_detail:
            questions.append(_build_question_in_session(sq, q))

    return {
        "id": session.id,
        "mode": session.mode.value,
        "difficulty": session.difficulty.value,
        "status": session.status.value,
        "time_limit_seconds": session.time_limit_seconds,
        "started_at": session.started_at,
        "ended_at": session.ended_at,
        "ai_assistant_disabled": session.ai_assistant_disabled,
        "is_flagged_for_review": session.is_flagged_for_review,
        "questions": questions,
        "created_at": session.created_at,
    }


@router.post("/{session_id}/start", response_model=StartSessionResponse)
async def start_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session_repo = SessionRepository(db)
    question_repo = QuestionRepository(db)

    session = await session_repo.get_by_id(session_id)
    if not session or session.user_id != current_user.id:
        raise SessionNotFound()

    if session.status != SessionStatus.pending:
        raise SessionAlreadyCompleted(f"Session is already {session.status.value}")

    # Exam requires verified email
    if session.mode == SessionMode.exam and not current_user.is_email_verified:
        raise UnverifiedEmailRequired()

    questions = await question_repo.select_for_session(
        mode=session.mode,
        difficulty=session.difficulty,
        user_id=current_user.id,
    )

    from app.repository.questions import MODE_QUESTION_COUNTS
    required_count = MODE_QUESTION_COUNTS[session.mode]
    if len(questions) < required_count:
        raise InsufficientQuestions(
            f"Only {len(questions)} questions available, need {required_count}"
        )

    started_session = await session_repo.start(session_id, questions)

    # Initialize session activity in Redis
    await update_session_activity(str(session_id))

    questions_data = []
    for idx, q in enumerate(questions):
        questions_data.append({
            "id": uuid.uuid4(),  # placeholder sq id (will be refreshed below)
            "question_id": q.id,
            "order_index": idx,
            "title": q.title,
            "scenario": q.scenario,
            "supporting_code": q.supporting_code,
            "supporting_logs": q.supporting_logs,
            "supporting_metrics": q.supporting_metrics,
            "category": q.category.value,
            "technologies": q.technologies,
            "difficulty": q.difficulty.value,
            "response_text": None,
            "code_response": None,
            "ai_interactions": [],
            "started_at": None,
            "submitted_at": None,
        })

    # Fetch actual session questions with correct IDs
    sq_rows = await session_repo.get_session_questions_with_details(session_id)
    questions_data = [_build_question_in_session(sq, q) for sq, q in sq_rows]

    return {
        "id": started_session.id,
        "mode": started_session.mode.value,
        "difficulty": started_session.difficulty.value,
        "status": started_session.status.value,
        "time_limit_seconds": started_session.time_limit_seconds,
        "started_at": started_session.started_at,
        "questions": questions_data,
        "ai_assistant_disabled": started_session.ai_assistant_disabled,
    }


def _check_time_limit(session) -> None:
    if session.started_at is None:
        return
    now = datetime.now(timezone.utc)
    deadline = session.started_at.replace(tzinfo=timezone.utc) if session.started_at.tzinfo is None else session.started_at
    deadline = deadline.replace(tzinfo=timezone.utc) if deadline.tzinfo is None else deadline
    elapsed = (now - session.started_at.replace(tzinfo=timezone.utc) if session.started_at.tzinfo is None else (now - session.started_at)).total_seconds()
    if elapsed > session.time_limit_seconds:
        raise SessionExpired()


@router.post("/{session_id}/questions/{question_id}/respond")
async def respond_to_question(
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    request: RespondRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = SessionRepository(db)
    session = await repo.get_by_id(session_id)
    if not session or session.user_id != current_user.id:
        raise SessionNotFound()
    if session.status != SessionStatus.in_progress:
        raise SessionNotInProgress()

    _check_time_limit(session)
    await update_session_activity(str(session_id))

    sq = await repo.save_response(session_id, question_id, request.response_text, request.code_response)
    if not sq:
        raise HTTPException(status_code=404, detail="Question not found in this session")

    return {"message": "Response saved", "question_id": str(question_id)}


@router.patch("/{session_id}/questions/{question_id}/autosave")
async def autosave_response(
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    request: AutosaveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = SessionRepository(db)
    session = await repo.get_by_id(session_id)
    if not session or session.user_id != current_user.id:
        raise SessionNotFound()
    if session.status != SessionStatus.in_progress:
        raise SessionNotInProgress()

    await update_session_activity(str(session_id))
    sq = await repo.autosave_response(session_id, question_id, request.response_text, request.code_response)
    if not sq:
        raise HTTPException(status_code=404, detail="Question not found in this session")

    return {"message": "Draft saved"}


@router.post("/{session_id}/questions/{question_id}/ai-chat")
async def ai_chat(
    session_id: uuid.UUID,
    question_id: uuid.UUID,
    request: AIChatRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Rate limit: 60 req / hour per user
    allowed, retry_after = await sliding_window_rate_limit(
        f"rl:ai_chat:{current_user.id}", 60, 3600
    )
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={"error": "RATE_LIMIT_EXCEEDED", "message": "AI chat rate limit exceeded", "retry_after": retry_after},
            headers={"Retry-After": str(retry_after)},
        )

    repo = SessionRepository(db)
    session = await repo.get_by_id(session_id)
    if not session or session.user_id != current_user.id:
        raise SessionNotFound()
    if session.status != SessionStatus.in_progress:
        raise SessionNotInProgress()
    if session.ai_assistant_disabled:
        raise AIAssistantDisabled()

    _check_time_limit(session)
    await update_session_activity(str(session_id))

    sq = await repo.get_question(session_id, question_id)
    if not sq:
        raise HTTPException(status_code=404, detail="Question not found in this session")

    # Check turn limit
    user_turn_count = sum(1 for i in (sq.ai_interactions or []) if i.get("role") == "user")
    if user_turn_count >= MAX_TURNS_PER_QUESTION:
        raise TurnLimitExceeded()

    # Load the question scenario
    from app.repository.questions import QuestionRepository
    q_repo = QuestionRepository(db)
    question = await q_repo.get_by_id(question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    # Append user message
    await repo.append_ai_interaction(session_id, question_id, "user", request.message)
    # Refresh sq to get updated interactions
    sq = await repo.get_question(session_id, question_id)

    async def event_stream() -> AsyncGenerator[str, None]:
        full_response = ""
        suppressed = False
        try:
            async for chunk in get_ai_response_stream(
                question_scenario=question.scenario,
                ai_interactions=sq.ai_interactions[:-1],  # exclude the just-added user message
                new_user_message=request.message,
                difficulty=session.difficulty.value,
            ):
                if "[DONE]" in chunk:
                    break
                # Parse SSE chunk
                if chunk.startswith("data: "):
                    data = chunk[6:].strip()
                    try:
                        parsed = json.loads(data)
                        if parsed.get("circuit_open"):
                            # Disable AI assistant on this session
                            await repo.disable_ai_assistant(session_id)
                            yield f"data: {json.dumps({'error': 'AI assistant disabled due to service issues'})}\n\n"
                            return
                        if parsed.get("suppressed"):
                            suppressed = True
                            full_response = ""
                            continue
                        content = parsed.get("content", "")
                        full_response += content
                    except json.JSONDecodeError:
                        pass
                yield chunk

            # Store the assistant response
            if full_response:
                await repo.append_ai_interaction(session_id, question_id, "assistant", full_response)

        except Exception as e:
            logger.error("ai_chat_stream_error", error=str(e))
            yield f"data: {json.dumps({'error': 'AI assistant encountered an error'})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/{session_id}/complete")
async def complete_session(
    session_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = SessionRepository(db)
    session = await repo.get_by_id(session_id)
    if not session or session.user_id != current_user.id:
        raise SessionNotFound()
    if session.status != SessionStatus.in_progress:
        raise SessionNotInProgress()

    completed = await repo.complete(session_id)

    # Only trigger scoring for Exam mode
    if session.mode == SessionMode.exam:
        from app.repository.scores import ScoreRepository
        score_repo = ScoreRepository(db)
        await score_repo.create_pending(session_id)
        await db.commit()

        # Queue Celery scoring task
        from app.workers.scoring import score_session_task
        score_session_task.delay(str(session_id))

    return {"message": "Session completed", "session_id": str(session_id), "mode": session.mode.value}


@router.post("/{session_id}/abandon")
async def abandon_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = SessionRepository(db)
    session = await repo.get_by_id(session_id)
    if not session or session.user_id != current_user.id:
        raise SessionNotFound()
    if session.status not in (SessionStatus.pending, SessionStatus.in_progress):
        return {"message": "Session already ended"}

    await repo.abandon(session_id)
    return {"message": "Session abandoned"}


@router.post("/{session_id}/events", status_code=202)
async def record_event(
    session_id: uuid.UUID,
    request: SessionEventRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fire-and-forget integrity event recording."""
    repo = SessionRepository(db)
    session = await repo.get_by_id(session_id)
    if not session or session.user_id != current_user.id:
        return {"message": "ok"}  # Fire-and-forget: don't surface errors

    valid_types = {"leave_page", "return_to_page", "inactivity_warning", "tab_blur", "copy_paste"}
    if request.event_type not in valid_types:
        return {"message": "ok"}

    background_tasks.add_task(
        _record_event_bg,
        session_id,
        request.event_type,
        request.metadata,
    )
    return {"message": "ok"}


async def _record_event_bg(session_id: uuid.UUID, event_type: str, metadata: dict | None) -> None:
    from app.core.database import async_session_factory
    async with async_session_factory() as db:
        repo = SessionRepository(db)
        await repo.add_event(session_id, event_type, metadata)
        await db.commit()
