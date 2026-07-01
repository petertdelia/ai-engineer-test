import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import Question, QuestionCategory, QuestionDifficulty, GenerationSource
from tests.conftest import auth_headers, create_test_user


async def create_test_question(db: AsyncSession, title: str = "Test Question", difficulty: str = "low") -> Question:
    q = Question(
        title=title,
        scenario="A realistic scenario about engineering problems requiring thought and analysis.",
        category=QuestionCategory.software_engineering,
        technologies=["python"],
        difficulty=QuestionDifficulty(difficulty),
        is_vetted=True,
        is_active=True,
        generation_source=GenerationSource.human,
    )
    db.add(q)
    await db.flush()
    await db.refresh(q)
    return q


async def create_enough_questions(db: AsyncSession, count: int = 3, difficulty: str = "low") -> list[Question]:
    questions = []
    for i in range(count):
        q = await create_test_question(db, title=f"Question {i}", difficulty=difficulty)
        questions.append(q)
    return questions


@pytest.mark.asyncio
async def test_create_session(client: AsyncClient, db_session: AsyncSession):
    user = await create_test_user(db_session, email="sess1@example.com")
    resp = await client.post("/sessions", json={"mode": "trial", "difficulty": "low"}, headers=auth_headers(user))
    assert resp.status_code == 201
    data = resp.json()
    assert data["mode"] == "trial"
    assert data["difficulty"] == "low"
    assert data["status"] == "pending"
    assert data["time_limit_seconds"] == 20 * 60


@pytest.mark.asyncio
async def test_list_sessions(client: AsyncClient, db_session: AsyncSession):
    user = await create_test_user(db_session, email="sess2@example.com")
    await client.post("/sessions", json={"mode": "trial", "difficulty": "low"}, headers=auth_headers(user))
    resp = await client.get("/sessions", headers=auth_headers(user))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_start_session(client: AsyncClient, db_session: AsyncSession):
    user = await create_test_user(db_session, email="sess3@example.com")
    await create_enough_questions(db_session, count=5, difficulty="low")

    create_resp = await client.post("/sessions", json={"mode": "trial", "difficulty": "low"}, headers=auth_headers(user))
    assert create_resp.status_code == 201
    session_id = create_resp.json()["id"]

    with patch("app.core.redis.get_redis") as mock_redis:
        mock = AsyncMock()
        mock.set = AsyncMock()
        mock_redis.return_value = mock

        start_resp = await client.post(f"/sessions/{session_id}/start", headers=auth_headers(user))
    assert start_resp.status_code == 200
    data = start_resp.json()
    assert data["status"] == "in_progress"
    assert len(data["questions"]) == 2  # Trial mode = 2 questions
    assert "scenario" in data["questions"][0]


@pytest.mark.asyncio
async def test_start_exam_requires_verified_email(client: AsyncClient, db_session: AsyncSession):
    user = await create_test_user(db_session, email="unverified@example.com", is_email_verified=False)
    await create_enough_questions(db_session, count=15, difficulty="medium")

    create_resp = await client.post("/sessions", json={"mode": "exam", "difficulty": "medium"}, headers=auth_headers(user))
    session_id = create_resp.json()["id"]

    resp = await client.post(f"/sessions/{session_id}/start", headers=auth_headers(user))
    assert resp.status_code == 403
    assert resp.json()["error"] == "UNVERIFIED_EMAIL_REQUIRED"


@pytest.mark.asyncio
async def test_respond_to_question(client: AsyncClient, db_session: AsyncSession):
    user = await create_test_user(db_session, email="respond@example.com")
    await create_enough_questions(db_session, count=5)

    create_resp = await client.post("/sessions", json={"mode": "trial", "difficulty": "low"}, headers=auth_headers(user))
    session_id = create_resp.json()["id"]

    with patch("app.core.redis.get_redis") as mock_redis:
        mock = AsyncMock()
        mock.set = AsyncMock()
        mock.get = AsyncMock(return_value=None)
        mock_redis.return_value = mock

        await client.post(f"/sessions/{session_id}/start", headers=auth_headers(user))

    # Get the question IDs
    detail_resp = await client.get(f"/sessions/{session_id}", headers=auth_headers(user))
    questions = detail_resp.json()["questions"]
    assert len(questions) > 0
    question_id = questions[0]["question_id"]

    with patch("app.core.redis.get_redis") as mock_redis:
        mock = AsyncMock()
        mock.set = AsyncMock()
        mock.get = AsyncMock(return_value=None)
        mock_redis.return_value = mock

        resp = await client.post(
            f"/sessions/{session_id}/questions/{question_id}/respond",
            json={"response_text": "My detailed answer to this question about engineering."},
            headers=auth_headers(user),
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_autosave(client: AsyncClient, db_session: AsyncSession):
    user = await create_test_user(db_session, email="autosave@example.com")
    await create_enough_questions(db_session, count=5)

    create_resp = await client.post("/sessions", json={"mode": "trial", "difficulty": "low"}, headers=auth_headers(user))
    session_id = create_resp.json()["id"]

    with patch("app.core.redis.get_redis") as mock_redis:
        mock = AsyncMock()
        mock.set = AsyncMock()
        mock.get = AsyncMock(return_value=None)
        mock_redis.return_value = mock

        await client.post(f"/sessions/{session_id}/start", headers=auth_headers(user))

    detail_resp = await client.get(f"/sessions/{session_id}", headers=auth_headers(user))
    question_id = detail_resp.json()["questions"][0]["question_id"]

    with patch("app.core.redis.get_redis") as mock_redis:
        mock = AsyncMock()
        mock.set = AsyncMock()
        mock_redis.return_value = mock

        resp = await client.patch(
            f"/sessions/{session_id}/questions/{question_id}/autosave",
            json={"response_text": "Draft answer..."},
            headers=auth_headers(user),
        )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_complete_session(client: AsyncClient, db_session: AsyncSession):
    user = await create_test_user(db_session, email="complete@example.com")
    await create_enough_questions(db_session, count=5)

    create_resp = await client.post("/sessions", json={"mode": "trial", "difficulty": "low"}, headers=auth_headers(user))
    session_id = create_resp.json()["id"]

    with patch("app.core.redis.get_redis") as mock_redis:
        mock = AsyncMock()
        mock.set = AsyncMock()
        mock_redis.return_value = mock

        await client.post(f"/sessions/{session_id}/start", headers=auth_headers(user))

    resp = await client.post(f"/sessions/{session_id}/complete", headers=auth_headers(user))
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_results_not_scored_for_trial(client: AsyncClient, db_session: AsyncSession):
    user = await create_test_user(db_session, email="results1@example.com")
    await create_enough_questions(db_session, count=5)

    create_resp = await client.post("/sessions", json={"mode": "trial", "difficulty": "low"}, headers=auth_headers(user))
    session_id = create_resp.json()["id"]

    with patch("app.core.redis.get_redis") as mock_redis:
        mock = AsyncMock()
        mock.set = AsyncMock()
        mock_redis.return_value = mock

        await client.post(f"/sessions/{session_id}/start", headers=auth_headers(user))
    await client.post(f"/sessions/{session_id}/complete", headers=auth_headers(user))

    resp = await client.get(f"/sessions/{session_id}/results", headers=auth_headers(user))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "not_scored"
    assert data["mode"] == "trial"


@pytest.mark.asyncio
async def test_results_409_for_pending_session(client: AsyncClient, db_session: AsyncSession):
    user = await create_test_user(db_session, email="results2@example.com")

    create_resp = await client.post("/sessions", json={"mode": "trial", "difficulty": "low"}, headers=auth_headers(user))
    session_id = create_resp.json()["id"]

    resp = await client.get(f"/sessions/{session_id}/results", headers=auth_headers(user))
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_abandon_session(client: AsyncClient, db_session: AsyncSession):
    user = await create_test_user(db_session, email="abandon@example.com")

    create_resp = await client.post("/sessions", json={"mode": "trial", "difficulty": "low"}, headers=auth_headers(user))
    session_id = create_resp.json()["id"]

    resp = await client.post(f"/sessions/{session_id}/abandon", headers=auth_headers(user))
    assert resp.status_code == 200

    detail_resp = await client.get(f"/sessions/{session_id}", headers=auth_headers(user))
    assert detail_resp.json()["status"] == "abandoned"
