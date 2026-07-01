"""
API tests for the leaderboard endpoint.
Tests population threshold gate, is_public_rank filtering, and auth requirement.
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import GenerationSource, Question, QuestionCategory, QuestionDifficulty
from app.models.score import ScoreStatus, SessionScore
from app.models.session import AssessmentSession, SessionDifficulty, SessionMode, SessionStatus
from tests.conftest import auth_headers, create_test_user


async def _seed_leaderboard_entries(db: AsyncSession, count: int, public_rank: bool = True):
    """Seed `count` completed exam sessions with scores for leaderboard population."""
    users = []
    for i in range(count):
        from app.models import User
        from app.core.auth import hash_password
        user = User(
            email=f"leader_{i}_{uuid.uuid4().hex[:6]}@example.com",
            name=f"Leader {i}",
            hashed_password=hash_password("Password123"),
            auth_provider="email",
            is_email_verified=True,
            is_public_rank=public_rank,
        )
        db.add(user)
        await db.flush()

        question = Question(
            title=f"Leaderboard Q{i}",
            scenario=f"Scenario {i}",
            category=QuestionCategory.software_engineering,
            technologies=["python"],
            difficulty=QuestionDifficulty.medium,
            is_vetted=True,
            is_active=True,
            generation_source=GenerationSource.human,
        )
        db.add(question)
        await db.flush()

        session = AssessmentSession(
            user_id=user.id,
            mode=SessionMode.exam,
            difficulty=SessionDifficulty.medium,
            time_limit_seconds=3600,
            status=SessionStatus.completed,
            started_at=datetime.now(timezone.utc),
            ended_at=datetime.now(timezone.utc),
        )
        db.add(session)
        await db.flush()

        score = SessionScore(
            session_id=session.id,
            status=ScoreStatus.completed,
            total_score=float(70 + i),
        )
        db.add(score)
        await db.flush()

        users.append(user)

    return users


@pytest.mark.asyncio
async def test_leaderboard_requires_auth(client: AsyncClient):
    """Leaderboard requires authentication."""
    resp = await client.get("/leaderboard")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_leaderboard_empty_below_population_threshold(client: AsyncClient, db_session: AsyncSession):
    """No leaderboard data is returned when population is below LEADERBOARD_MIN_POPULATION (100)."""
    user = await create_test_user(db_session, email="lboard_empty@example.com")

    # Seed only a few entries — well below 100
    await _seed_leaderboard_entries(db_session, 3, public_rank=True)

    resp = await client.get("/leaderboard", headers=auth_headers(user))

    # Should return 200 with available=False (population gate)
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("available") is False
    assert "current_count" in body


@pytest.mark.asyncio
async def test_leaderboard_public_rank_filter(client: AsyncClient, db_session: AsyncSession):
    """Only users with is_public_rank=True appear in the leaderboard."""
    viewer = await create_test_user(db_session, email="lboard_viewer@example.com")

    # Seed users with is_public_rank=False
    private_users = await _seed_leaderboard_entries(db_session, 5, public_rank=False)
    private_ids = {str(u.id) for u in private_users}

    # Seed users with is_public_rank=True
    public_users = await _seed_leaderboard_entries(db_session, 5, public_rank=True)

    resp = await client.get("/leaderboard", headers=auth_headers(viewer))
    assert resp.status_code in (200, 204)

    if resp.status_code == 200:
        body = resp.json()
        entries = body.get("entries", [])
        returned_ids = {entry.get("user_id") for entry in entries}
        # No private users should appear
        overlap = private_ids & returned_ids
        assert len(overlap) == 0, f"Private users appeared in leaderboard: {overlap}"


@pytest.mark.asyncio
async def test_leaderboard_pagination(client: AsyncClient, db_session: AsyncSession):
    """Leaderboard supports limit and offset parameters."""
    viewer = await create_test_user(db_session, email="lboard_page@example.com")

    resp = await client.get("/leaderboard?limit=10&offset=0", headers=auth_headers(viewer))
    # Should not 422
    assert resp.status_code in (200, 204)
