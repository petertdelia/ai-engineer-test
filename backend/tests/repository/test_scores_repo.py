"""
Repository tests for ScoreRepository — requires real PostgreSQL.

Tests pending/completed/failed transitions and failure_reason writes.
"""
import uuid
from datetime import datetime, timezone

import pytest

from app.core.auth import hash_password
from app.models import User
from app.models.question import GenerationSource, Question, QuestionCategory, QuestionDifficulty
from app.models.score import ScoreStatus, SessionScore
from app.models.session import AssessmentSession, SessionDifficulty, SessionMode, SessionStatus
from app.repository.scores import ScoreRepository
from tests.repository.conftest import requires_postgres


async def _seed_completed_session(pg_session) -> AssessmentSession:
    user = User(
        email=f"score_repo_{uuid.uuid4().hex[:8]}@example.com",
        name="Score Test",
        hashed_password=hash_password("Password123"),
        auth_provider="email",
        is_email_verified=True,
    )
    pg_session.add(user)
    await pg_session.flush()

    session = AssessmentSession(
        user_id=user.id,
        mode=SessionMode.exam,
        difficulty=SessionDifficulty.medium,
        time_limit_seconds=3600,
        status=SessionStatus.completed,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    pg_session.add(session)
    await pg_session.flush()
    await pg_session.refresh(session)
    return session


@requires_postgres
@pytest.mark.asyncio
async def test_create_pending_score(pg_session):
    repo = ScoreRepository(pg_session)
    session = await _seed_completed_session(pg_session)

    score = await repo.create_pending(session.id)
    assert score.id is not None
    assert score.status == ScoreStatus.pending
    assert score.total_score is None


@requires_postgres
@pytest.mark.asyncio
async def test_update_score_to_completed(pg_session):
    repo = ScoreRepository(pg_session)
    session = await _seed_completed_session(pg_session)

    score = await repo.create_pending(session.id)
    updated = await repo.update_score(
        session_id=session.id,
        engineering_skill=80.0,
        ai_collaboration=75.0,
        ai_trust_calibration=70.0,
        engineering_judgement=85.0,
        total_score=77.5,
    )
    assert updated.status == ScoreStatus.completed
    assert updated.total_score == 77.5
    assert updated.engineering_skill == 80.0


@requires_postgres
@pytest.mark.asyncio
async def test_set_failed_score(pg_session):
    repo = ScoreRepository(pg_session)
    session = await _seed_completed_session(pg_session)

    await repo.create_pending(session.id)
    await repo.set_failed(session.id, "Claude API timed out after 3 retries")
    failed = await repo.get_by_session(session.id)
    assert failed.status == ScoreStatus.failed
    assert "Claude API" in failed.failure_reason


@requires_postgres
@pytest.mark.asyncio
async def test_get_score_by_session(pg_session):
    repo = ScoreRepository(pg_session)
    session = await _seed_completed_session(pg_session)

    await repo.create_pending(session.id)
    found = await repo.get_by_session(session.id)
    assert found is not None
    assert found.session_id == session.id


@requires_postgres
@pytest.mark.asyncio
async def test_get_score_returns_none_for_unknown_session(pg_session):
    repo = ScoreRepository(pg_session)
    result = await repo.get_by_session(uuid.uuid4())
    assert result is None


@requires_postgres
@pytest.mark.asyncio
async def test_score_transitions_pending_to_completed(pg_session):
    """Full lifecycle: pending → completed."""
    repo = ScoreRepository(pg_session)
    session = await _seed_completed_session(pg_session)

    score = await repo.create_pending(session.id)
    assert score.status == ScoreStatus.pending

    completed = await repo.update_score(
        session_id=session.id,
        engineering_skill=90.0,
        ai_collaboration=85.0,
        ai_trust_calibration=80.0,
        engineering_judgement=88.0,
        total_score=85.75,
    )
    assert completed.status == ScoreStatus.completed
    assert completed.total_score == 85.75


@requires_postgres
@pytest.mark.asyncio
async def test_failure_reason_is_persisted(pg_session):
    repo = ScoreRepository(pg_session)
    session = await _seed_completed_session(pg_session)

    await repo.create_pending(session.id)
    failure_msg = "All 3 retries exhausted: rate limit exceeded"
    await repo.set_failed(session.id, failure_msg)

    # Re-fetch to verify persistence
    found = await repo.get_by_session(session.id)
    assert found.failure_reason == failure_msg
