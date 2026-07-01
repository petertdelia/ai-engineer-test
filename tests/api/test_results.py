"""
API tests for GET /sessions/{session_id}/results endpoint.
Tests pending, completed, failed, and pre-completion 409 states.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import GenerationSource, Question, QuestionCategory, QuestionDifficulty
from app.models.score import ScoreStatus, SessionScore
from app.models.session import AssessmentSession, SessionDifficulty, SessionMode, SessionQuestion, SessionStatus
from tests.conftest import auth_headers, create_test_user


async def _make_completed_session(db: AsyncSession, user_id: uuid.UUID):
    """Create a completed exam session with a question."""
    question = Question(
        title="Results Test Question",
        scenario="A complex distributed systems scenario.",
        category=QuestionCategory.software_engineering,
        technologies=["python", "kubernetes"],
        difficulty=QuestionDifficulty.high,
        is_vetted=True,
        is_active=True,
        generation_source=GenerationSource.human,
    )
    db.add(question)
    await db.flush()

    session = AssessmentSession(
        user_id=user_id,
        mode=SessionMode.exam,
        difficulty=SessionDifficulty.high,
        time_limit_seconds=3600,
        status=SessionStatus.completed,
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
    )
    db.add(session)
    await db.flush()

    sq = SessionQuestion(
        session_id=session.id,
        question_id=question.id,
        order_index=0,
        ai_interactions=[],
    )
    db.add(sq)
    await db.flush()

    await db.refresh(session)
    return session, question


@pytest.mark.asyncio
async def test_results_returns_404_for_nonexistent_session(client: AsyncClient, db_session: AsyncSession):
    """GET /sessions/{id}/results returns 404 for a random UUID."""
    user = await create_test_user(db_session, email="results_404@example.com")
    resp = await client.get(f"/sessions/{uuid.uuid4()}/results", headers=auth_headers(user))
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_results_409_when_session_not_complete(client: AsyncClient, db_session: AsyncSession):
    """GET /sessions/{id}/results returns 409 before session is complete."""
    user = await create_test_user(db_session, email="results_inprog@example.com")

    session = AssessmentSession(
        user_id=user.id,
        mode=SessionMode.exam,
        difficulty=SessionDifficulty.medium,
        time_limit_seconds=3600,
        status=SessionStatus.in_progress,
        started_at=datetime.now(timezone.utc),
    )
    db_session.add(session)
    await db_session.flush()

    resp = await client.get(f"/sessions/{session.id}/results", headers=auth_headers(user))
    assert resp.status_code == 409
    detail = resp.json().get("detail", {})
    assert detail.get("error") == "SESSION_NOT_COMPLETED"


@pytest.mark.asyncio
async def test_results_pending_scoring(client: AsyncClient, db_session: AsyncSession):
    """While scoring is pending, results returns 202 Accepted with status=pending."""
    user = await create_test_user(db_session, email="results_pending@example.com")
    session, _ = await _make_completed_session(db_session, user.id)

    score = SessionScore(
        session_id=session.id,
        status=ScoreStatus.pending,
    )
    db_session.add(score)
    await db_session.flush()

    resp = await client.get(f"/sessions/{session.id}/results", headers=auth_headers(user))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "pending"


@pytest.mark.asyncio
async def test_results_completed_scoring(client: AsyncClient, db_session: AsyncSession):
    """Once scoring completes, results returns 200 with score data."""
    user = await create_test_user(db_session, email="results_completed@example.com")
    session, _ = await _make_completed_session(db_session, user.id)

    score = SessionScore(
        session_id=session.id,
        status=ScoreStatus.completed,
        total_score=82.5,
        engineering_skill=80.0,
        ai_collaboration=85.0,
        ai_trust_calibration=85.0,
        engineering_judgement=80.0,
    )
    db_session.add(score)
    await db_session.flush()

    resp = await client.get(f"/sessions/{session.id}/results", headers=auth_headers(user))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "completed"
    assert body["total_score"] == 82.5


@pytest.mark.asyncio
async def test_results_failed_scoring(client: AsyncClient, db_session: AsyncSession):
    """When scoring fails, results returns the failed status and failure_reason."""
    user = await create_test_user(db_session, email="results_failed@example.com")
    session, _ = await _make_completed_session(db_session, user.id)

    score = SessionScore(
        session_id=session.id,
        status=ScoreStatus.failed,
        failure_reason="Claude API rate limit exceeded after 3 retries",
    )
    db_session.add(score)
    await db_session.flush()

    resp = await client.get(f"/sessions/{session.id}/results", headers=auth_headers(user))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert "failure_reason" in body
    assert body["failure_reason"] is not None


@pytest.mark.asyncio
async def test_results_requires_auth(client: AsyncClient):
    """GET /sessions/{id}/results requires authentication."""
    resp = await client.get(f"/sessions/{uuid.uuid4()}/results")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_results_cannot_access_other_users_session(client: AsyncClient, db_session: AsyncSession):
    """Users can only view their own session results."""
    owner = await create_test_user(db_session, email="results_owner@example.com")
    other = await create_test_user(db_session, email="results_other@example.com")

    session, _ = await _make_completed_session(db_session, owner.id)

    score = SessionScore(
        session_id=session.id,
        status=ScoreStatus.completed,
        total_score=75.0,
    )
    db_session.add(score)
    await db_session.flush()

    resp = await client.get(f"/sessions/{session.id}/results", headers=auth_headers(other))
    assert resp.status_code == 404
