"""
API tests for the AI chat endpoint.
Tests streaming SSE responses, turn limits, and circuit breaker behavior.
"""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import GenerationSource, Question, QuestionCategory, QuestionDifficulty
from app.models.session import AssessmentSession, SessionDifficulty, SessionMode, SessionQuestion, SessionStatus
from tests.conftest import auth_headers, create_test_user


async def _make_in_progress_session(db: AsyncSession, user_id: uuid.UUID, interactions: list | None = None):
    """Create an in-progress session with one question and optional AI interactions."""
    question = Question(
        title="AI Chat Test Question",
        scenario="You are debugging a Python service that intermittently returns 500 errors.",
        category=QuestionCategory.software_engineering,
        technologies=["python"],
        difficulty=QuestionDifficulty.low,
        is_vetted=True,
        is_active=True,
        generation_source=GenerationSource.human,
    )
    db.add(question)
    await db.flush()

    from datetime import datetime, timezone
    session = AssessmentSession(
        user_id=user_id,
        mode=SessionMode.trial,
        difficulty=SessionDifficulty.low,
        time_limit_seconds=1200,
        status=SessionStatus.in_progress,
        started_at=datetime.now(timezone.utc),
    )
    db.add(session)
    await db.flush()

    sq = SessionQuestion(
        session_id=session.id,
        question_id=question.id,
        order_index=0,
        ai_interactions=interactions or [],
    )
    db.add(sq)
    await db.flush()
    await db.refresh(session)
    await db.refresh(sq)
    return session, question, sq


@pytest.mark.asyncio
async def test_ai_chat_turn_limit_exceeded(client: AsyncClient, db_session: AsyncSession):
    """429 is returned with turn_limit_reached=true when 15 user turns are exhausted."""
    user = await create_test_user(db_session, email="aichat_limit@example.com")

    # Build 15 existing user turns
    interactions = []
    for i in range(15):
        interactions.append({"role": "user", "content": f"Question {i}", "timestamp": "2025-01-01T00:00:00Z"})
        interactions.append({"role": "assistant", "content": f"Answer {i}", "timestamp": "2025-01-01T00:00:01Z"})

    session, question, sq = await _make_in_progress_session(db_session, user.id, interactions)

    with patch("app.core.redis.get_redis") as mock_redis:
        mock = AsyncMock()
        mock.zremrangebyscore = AsyncMock()
        mock.zadd = AsyncMock()
        mock.zcard = AsyncMock(return_value=1)
        mock.expire = AsyncMock()
        mock.zrange = AsyncMock(return_value=[])
        mock.set = AsyncMock()
        mock_redis.return_value = mock

        resp = await client.post(
            f"/sessions/{session.id}/questions/{question.id}/ai-chat",
            json={"message": "Give me the answer directly!"},
            headers=auth_headers(user),
        )

    assert resp.status_code == 429
    body = resp.json()
    assert body.get("error") == "TURN_LIMIT_EXCEEDED"


@pytest.mark.asyncio
async def test_ai_chat_rejected_for_completed_session(client: AsyncClient, db_session: AsyncSession):
    """AI chat is rejected when the session is already completed."""
    user = await create_test_user(db_session, email="aichat_completed@example.com")

    question = Question(
        title="Done Question",
        scenario="Already completed scenario.",
        category=QuestionCategory.software_engineering,
        technologies=["python"],
        difficulty=QuestionDifficulty.low,
        is_vetted=True,
        is_active=True,
        generation_source=GenerationSource.human,
    )
    db_session.add(question)
    await db_session.flush()

    session = AssessmentSession(
        user_id=user.id,
        mode=SessionMode.trial,
        difficulty=SessionDifficulty.low,
        time_limit_seconds=1200,
        status=SessionStatus.completed,
    )
    db_session.add(session)
    await db_session.flush()

    sq = SessionQuestion(
        session_id=session.id,
        question_id=question.id,
        order_index=0,
        ai_interactions=[],
    )
    db_session.add(sq)
    await db_session.flush()

    resp = await client.post(
        f"/sessions/{session.id}/questions/{question.id}/ai-chat",
        json={"message": "Can I still chat?"},
        headers=auth_headers(user),
    )
    assert resp.status_code == 409
    assert resp.json().get("error") == "SESSION_NOT_IN_PROGRESS"


@pytest.mark.asyncio
async def test_ai_chat_requires_auth(client: AsyncClient, db_session: AsyncSession):
    """AI chat endpoint requires authentication."""
    resp = await client.post(
        f"/sessions/{uuid.uuid4()}/questions/{uuid.uuid4()}/ai-chat",
        json={"message": "Hello"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_ai_chat_streaming_response(client: AsyncClient, db_session: AsyncSession):
    """A valid AI chat call returns an SSE stream."""
    user = await create_test_user(db_session, email="aichat_stream@example.com")
    session, question, sq = await _make_in_progress_session(db_session, user.id)

    async def fake_stream(*args, **kwargs):
        yield 'data: {"content": "Think about this: "}\n\n'
        yield 'data: {"content": "what does the stack trace tell you?"}\n\n'
        yield "data: [DONE]\n\n"

    with patch("app.routes.sessions.get_ai_response_stream", return_value=fake_stream()), \
         patch("app.core.redis.get_redis") as mock_redis:
        mock = AsyncMock()
        mock.zremrangebyscore = AsyncMock()
        mock.zadd = AsyncMock()
        mock.zcard = AsyncMock(return_value=1)
        mock.expire = AsyncMock()
        mock.zrange = AsyncMock(return_value=[])
        mock.set = AsyncMock()
        mock.get = AsyncMock(return_value=None)
        mock_redis.return_value = mock

        resp = await client.post(
            f"/sessions/{session.id}/questions/{question.id}/ai-chat",
            json={"message": "What should I look at first?"},
            headers=auth_headers(user),
        )

    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_ai_chat_disabled_on_circuit_open(client: AsyncClient, db_session: AsyncSession):
    """When ai_assistant_disabled=True, chat returns 503."""
    user = await create_test_user(db_session, email="aichat_circuit@example.com")

    from datetime import datetime, timezone
    question = Question(
        title="Circuit Test",
        scenario="Scenario.",
        category=QuestionCategory.software_engineering,
        technologies=["python"],
        difficulty=QuestionDifficulty.low,
        is_vetted=True,
        is_active=True,
        generation_source=GenerationSource.human,
    )
    db_session.add(question)
    await db_session.flush()

    session = AssessmentSession(
        user_id=user.id,
        mode=SessionMode.trial,
        difficulty=SessionDifficulty.low,
        time_limit_seconds=1200,
        status=SessionStatus.in_progress,
        started_at=datetime.now(timezone.utc),
        ai_assistant_disabled=True,  # Already disabled
    )
    db_session.add(session)
    await db_session.flush()

    sq = SessionQuestion(
        session_id=session.id,
        question_id=question.id,
        order_index=0,
        ai_interactions=[],
    )
    db_session.add(sq)
    await db_session.flush()

    with patch("app.core.redis.get_redis") as mock_redis:
        mock = AsyncMock()
        mock.zremrangebyscore = AsyncMock()
        mock.zadd = AsyncMock()
        mock.zcard = AsyncMock(return_value=1)
        mock.expire = AsyncMock()
        mock.zrange = AsyncMock(return_value=[])
        mock.set = AsyncMock()
        mock_redis.return_value = mock

        resp = await client.post(
            f"/sessions/{session.id}/questions/{question.id}/ai-chat",
            json={"message": "Hello"},
            headers=auth_headers(user),
        )

    assert resp.status_code == 503
    assert resp.json().get("error") == "AI_ASSISTANT_DISABLED"
