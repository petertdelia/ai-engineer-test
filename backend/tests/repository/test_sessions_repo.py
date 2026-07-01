"""
Repository tests for sessions — requires real PostgreSQL.

Tests session state transitions, question selection query, and autosave upsert.
"""
import uuid
from datetime import datetime, timezone

import pytest

from app.core.auth import hash_password
from app.models import User
from app.models.question import GenerationSource, Question, QuestionCategory, QuestionDifficulty
from app.models.session import AssessmentSession, SessionMode, SessionQuestion, SessionStatus
from app.repository.sessions import SessionRepository
from tests.repository.conftest import requires_postgres


async def _seed_user(pg_session) -> User:
    user = User(
        email=f"sess_repo_{uuid.uuid4().hex[:8]}@example.com",
        name="Session Test User",
        hashed_password=hash_password("Password123"),
        auth_provider="email",
        is_email_verified=True,
    )
    pg_session.add(user)
    await pg_session.flush()
    await pg_session.refresh(user)
    return user


async def _seed_question(pg_session) -> Question:
    q = Question(
        title=f"Repo Session Q {uuid.uuid4().hex[:8]}",
        scenario="Complex debugging scenario.",
        category=QuestionCategory.software_engineering,
        technologies=["python"],
        difficulty=QuestionDifficulty.medium,
        is_vetted=True,
        is_active=True,
        generation_source=GenerationSource.human,
    )
    pg_session.add(q)
    await pg_session.flush()
    await pg_session.refresh(q)
    return q


@requires_postgres
@pytest.mark.asyncio
async def test_create_session(pg_session):
    repo = SessionRepository(pg_session)
    user = await _seed_user(pg_session)

    session = await repo.create(
        user_id=user.id,
        mode="trial",
        difficulty="medium",
    )
    assert session.id is not None
    assert session.status == SessionStatus.pending
    assert session.mode == SessionMode.trial


@requires_postgres
@pytest.mark.asyncio
async def test_get_session_by_id(pg_session):
    repo = SessionRepository(pg_session)
    user = await _seed_user(pg_session)

    session = await repo.create(
        user_id=user.id,
        mode="practice",
        difficulty="low",
    )
    found = await repo.get_by_id(session.id)
    assert found is not None
    assert found.id == session.id


@requires_postgres
@pytest.mark.asyncio
async def test_session_transition_to_in_progress(pg_session):
    repo = SessionRepository(pg_session)
    user = await _seed_user(pg_session)
    question = await _seed_question(pg_session)

    session = await repo.create(
        user_id=user.id,
        mode="trial",
        difficulty="medium",
    )
    assert session.status == SessionStatus.pending

    started = await repo.start(session.id, [question])
    assert started.status == SessionStatus.in_progress


@requires_postgres
@pytest.mark.asyncio
async def test_session_transition_to_completed(pg_session):
    repo = SessionRepository(pg_session)
    user = await _seed_user(pg_session)
    question = await _seed_question(pg_session)

    session = await repo.create(
        user_id=user.id,
        mode="exam",
        difficulty="high",
    )
    await repo.start(session.id, [question])
    completed = await repo.complete(session.id)
    assert completed.status == SessionStatus.completed
    assert completed.ended_at is not None


@requires_postgres
@pytest.mark.asyncio
async def test_session_transition_to_abandoned(pg_session):
    repo = SessionRepository(pg_session)
    user = await _seed_user(pg_session)
    question = await _seed_question(pg_session)

    session = await repo.create(
        user_id=user.id,
        mode="practice",
        difficulty="medium",
    )
    await repo.start(session.id, [question])
    abandoned = await repo.abandon(session.id)
    assert abandoned.status == SessionStatus.abandoned


@requires_postgres
@pytest.mark.asyncio
async def test_add_session_questions(pg_session):
    repo = SessionRepository(pg_session)
    user = await _seed_user(pg_session)
    question = await _seed_question(pg_session)

    session = await repo.create(
        user_id=user.id,
        mode="trial",
        difficulty="medium",
    )

    started = await repo.start(session.id, [question])

    # Verify it was persisted
    from sqlalchemy import select
    result = await pg_session.execute(
        select(SessionQuestion).where(SessionQuestion.session_id == session.id)
    )
    sqs = result.scalars().all()
    assert len(sqs) == 1
    assert sqs[0].question_id == question.id


@requires_postgres
@pytest.mark.asyncio
async def test_get_user_sessions(pg_session):
    repo = SessionRepository(pg_session)
    user = await _seed_user(pg_session)

    for _ in range(3):
        await repo.create(
            user_id=user.id,
            mode="trial",
            difficulty="medium",
        )

    sessions = await repo.get_by_user(user.id)
    assert len(sessions) >= 3
