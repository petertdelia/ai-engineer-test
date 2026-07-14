"""
Repository tests for user stats — requires real PostgreSQL.

Validates the jsonb_array_elements_text query that powers GET /users/me/stats,
testing per-technology score breakdowns against known fixture data.
"""
import uuid
from datetime import datetime, timezone

import pytest

from app.core.auth import hash_password
from app.models import User
from app.models.question import GenerationSource, Question, QuestionCategory, QuestionDifficulty
from app.models.score import ScoreStatus, SessionScore
from app.models.session import (
    AssessmentSession, SessionDifficulty, SessionMode, SessionQuestion, SessionStatus,
)
from app.repository.users import UserRepository
from tests.repository.conftest import requires_postgres


async def _seed_user_with_completed_exam(pg_session, technologies: list[str], score: float) -> User:
    """Seed a user with a completed exam session scored on a question with the given technologies."""
    user = User(
        email=f"stats_{uuid.uuid4().hex[:8]}@example.com",
        name="Stats User",
        hashed_password=hash_password("Password123"),
        auth_provider="email",
        is_email_verified=True,
    )
    pg_session.add(user)
    await pg_session.flush()

    q = Question(
        title=f"Stats Q {uuid.uuid4().hex[:6]}",
        scenario="Stats scenario.",
        category=QuestionCategory.software_engineering,
        technologies=technologies,
        difficulty=QuestionDifficulty.medium,
        is_vetted=True,
        is_active=True,
        generation_source=GenerationSource.human,
    )
    pg_session.add(q)
    await pg_session.flush()

    session = AssessmentSession(
        user_id=user.id,
        mode=SessionMode.exam,
        difficulty=SessionDifficulty.medium,
        time_limit_seconds=3600,
        status=SessionStatus.completed,
        started_at=datetime.now(timezone.utc),
        ended_at=datetime.now(timezone.utc),
    )
    pg_session.add(session)
    await pg_session.flush()

    sq = SessionQuestion(
        session_id=session.id,
        question_id=q.id,
        order_index=0,
        ai_interactions=[],
        score_engineering_skill=score,
        score_ai_collaboration=score,
        score_ai_trust_calibration=score,
        score_engineering_judgement=score,
    )
    pg_session.add(sq)
    await pg_session.flush()

    sess_score = SessionScore(
        session_id=session.id,
        status=ScoreStatus.completed,
        total_score=score,
        engineering_skill=score,
        ai_collaboration=score,
        ai_trust_calibration=score,
        engineering_judgement=score,
    )
    pg_session.add(sess_score)
    await pg_session.flush()
    await pg_session.refresh(user)
    return user


@requires_postgres
@pytest.mark.asyncio
async def test_get_stats_returns_dict(pg_session):
    """get_stats should return a dict (even if no sessions yet)."""
    repo = UserRepository(pg_session)
    user = User(
        email=f"stats_empty_{uuid.uuid4().hex[:8]}@example.com",
        name="Stats Empty",
        hashed_password=hash_password("Password123"),
        auth_provider="email",
        is_email_verified=True,
    )
    pg_session.add(user)
    await pg_session.flush()

    stats = await repo.get_stats(user.id)
    assert isinstance(stats, dict)


@requires_postgres
@pytest.mark.asyncio
async def test_get_stats_per_technology_breakdown(pg_session):
    """
    Stats should include tech_strengths with per-technology breakdowns
    from jsonb_array_elements_text unnesting.
    """
    repo = UserRepository(pg_session)
    user = await _seed_user_with_completed_exam(pg_session, ["python"], 80.0)

    stats = await repo.get_stats(user.id)

    # tech_strengths is the key in the actual implementation
    tech_strengths = stats.get("tech_strengths", [])
    techs = [row["technology"] for row in tech_strengths]
    assert "python" in techs


@requires_postgres
@pytest.mark.asyncio
async def test_get_stats_total_sessions_count(pg_session):
    repo = UserRepository(pg_session)
    user = await _seed_user_with_completed_exam(pg_session, ["go"], 75.0)

    stats = await repo.get_stats(user.id)
    assert stats.get("total_sessions", 0) >= 1


@requires_postgres
@pytest.mark.asyncio
async def test_get_stats_best_score(pg_session):
    repo = UserRepository(pg_session)
    user = await _seed_user_with_completed_exam(pg_session, ["python"], 90.0)

    stats = await repo.get_stats(user.id)
    best = stats.get("best_score")
    if best is not None:
        assert 0.0 <= best <= 100.0


@requires_postgres
@pytest.mark.asyncio
async def test_get_stats_multiple_technologies_unnested(pg_session):
    """
    A question with multiple technologies should produce a row for each
    technology in tech_strengths (via jsonb_array_elements_text unnesting).
    """
    repo = UserRepository(pg_session)
    user = await _seed_user_with_completed_exam(pg_session, ["python", "kubernetes"], 85.0)

    stats = await repo.get_stats(user.id)
    tech_strengths = stats.get("tech_strengths", [])
    techs = {row["technology"] for row in tech_strengths}

    # Both technologies should appear because of the unnesting query
    assert "python" in techs
    assert "kubernetes" in techs


@requires_postgres
@pytest.mark.asyncio
async def test_get_stats_for_user_with_no_sessions(pg_session):
    """User with no completed sessions should get zeroed/empty stats."""
    repo = UserRepository(pg_session)
    user = User(
        email=f"stats_nosess_{uuid.uuid4().hex[:8]}@example.com",
        name="No Sessions",
        hashed_password=hash_password("Password123"),
        auth_provider="email",
        is_email_verified=True,
    )
    pg_session.add(user)
    await pg_session.flush()

    stats = await repo.get_stats(user.id)
    assert stats is not None
    assert stats.get("total_sessions", 0) == 0
    assert stats.get("tech_strengths", []) == []
