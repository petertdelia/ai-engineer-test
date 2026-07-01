"""
Repository tests for QuestionRepository — requires real PostgreSQL.

Tests JSONB array queries, category/difficulty filtering, and the full
question selection algorithm.
"""
import uuid

import pytest

from app.models.question import GenerationSource, Question, QuestionCategory, QuestionDifficulty
from app.models.session import SessionMode
from app.repository.questions import QuestionRepository
from tests.repository.conftest import requires_postgres


async def _seed_question(pg_session, **overrides) -> Question:
    defaults = dict(
        title=f"Seed Q {uuid.uuid4().hex[:8]}",
        scenario="Test scenario for repository testing.",
        category=QuestionCategory.software_engineering,
        technologies=["python"],
        difficulty=QuestionDifficulty.medium,
        is_vetted=True,
        is_active=True,
        generation_source=GenerationSource.human,
    )
    defaults.update(overrides)
    q = Question(**defaults)
    pg_session.add(q)
    await pg_session.flush()
    await pg_session.refresh(q)
    return q


@requires_postgres
@pytest.mark.asyncio
async def test_create_and_get_by_id(pg_session):
    repo = QuestionRepository(pg_session)
    q = await repo.create(
        title="Unique Question Title",
        scenario="Complex scenario.",
        category=QuestionCategory.software_engineering,
        technologies=["python", "fastapi"],
        difficulty=QuestionDifficulty.medium,
        is_vetted=True,
        is_active=True,
        generation_source=GenerationSource.human,
    )
    found = await repo.get_by_id(q.id)
    assert found is not None
    assert found.title == "Unique Question Title"
    assert "python" in found.technologies


@requires_postgres
@pytest.mark.asyncio
async def test_filter_by_category(pg_session):
    repo = QuestionRepository(pg_session)
    await _seed_question(pg_session, category=QuestionCategory.data_science, is_vetted=True, is_active=True)
    await _seed_question(pg_session, category=QuestionCategory.cyber_security, is_vetted=True, is_active=True)

    results, total = await repo.list_filtered(category="data_science")
    assert all(q.category == QuestionCategory.data_science for q in results)


@requires_postgres
@pytest.mark.asyncio
async def test_filter_by_difficulty(pg_session):
    repo = QuestionRepository(pg_session)
    await _seed_question(pg_session, difficulty=QuestionDifficulty.high, is_vetted=True, is_active=True)
    await _seed_question(pg_session, difficulty=QuestionDifficulty.low, is_vetted=True, is_active=True)

    results, total = await repo.list_filtered(difficulty="high")
    assert all(q.difficulty == QuestionDifficulty.high for q in results)


@requires_postgres
@pytest.mark.asyncio
async def test_filter_unvetted(pg_session):
    repo = QuestionRepository(pg_session)
    await _seed_question(pg_session, is_vetted=False, is_active=True)
    await _seed_question(pg_session, is_vetted=True, is_active=True)

    unvetted, _ = await repo.list_filtered(is_vetted=False)
    assert all(q.is_vetted is False for q in unvetted)


@requires_postgres
@pytest.mark.asyncio
async def test_vet_question(pg_session):
    repo = QuestionRepository(pg_session)
    q = await _seed_question(pg_session, is_vetted=False)
    assert q.is_vetted is False

    vetted = await repo.vet(q.id)
    assert vetted.is_vetted is True


@requires_postgres
@pytest.mark.asyncio
async def test_soft_delete_question(pg_session):
    repo = QuestionRepository(pg_session)
    q = await _seed_question(pg_session, is_active=True)

    await repo.soft_delete(q.id)
    found = await repo.get_by_id(q.id)
    assert found.is_active is False


@requires_postgres
@pytest.mark.asyncio
async def test_select_for_trial_session(pg_session):
    repo = QuestionRepository(pg_session)

    # Seed enough vetted medium questions
    for _ in range(5):
        await _seed_question(
            pg_session,
            category=QuestionCategory.software_engineering,
            difficulty=QuestionDifficulty.medium,
            is_vetted=True,
            is_active=True,
        )

    result = await repo.select_for_session(
        mode=SessionMode.trial,
        difficulty=QuestionDifficulty.medium,
        user_id=None,
    )
    assert len(result) == 2  # trial gets 2


@requires_postgres
@pytest.mark.asyncio
async def test_select_for_exam_session(pg_session):
    repo = QuestionRepository(pg_session)

    # Seed 10+ questions across categories
    for _ in range(6):
        await _seed_question(pg_session, category=QuestionCategory.software_engineering, difficulty=QuestionDifficulty.medium, is_vetted=True, is_active=True)
    for _ in range(4):
        await _seed_question(pg_session, category=QuestionCategory.data_science, difficulty=QuestionDifficulty.medium, is_vetted=True, is_active=True)
    for _ in range(3):
        await _seed_question(pg_session, category=QuestionCategory.data_engineering, difficulty=QuestionDifficulty.medium, is_vetted=True, is_active=True, technologies=["airflow"])
    for _ in range(2):
        await _seed_question(pg_session, category=QuestionCategory.cyber_security, difficulty=QuestionDifficulty.medium, is_vetted=True, is_active=True, technologies=["nmap"])

    result = await repo.select_for_session(
        mode=SessionMode.exam,
        difficulty=QuestionDifficulty.medium,
        user_id=None,
    )
    assert len(result) == 10  # exam gets 10


@requires_postgres
@pytest.mark.asyncio
async def test_technologies_jsonb_query(pg_session):
    """Verify JSONB technologies column stores and retrieves arrays correctly."""
    q = await _seed_question(pg_session, technologies=["python", "fastapi", "postgres"])
    found_q = await QuestionRepository(pg_session).get_by_id(q.id)
    assert "fastapi" in found_q.technologies
    assert len(found_q.technologies) == 3
