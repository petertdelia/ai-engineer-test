import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import GenerationSource, Question, QuestionCategory, QuestionDifficulty
from tests.conftest import auth_headers, create_test_user


@pytest.mark.asyncio
async def test_admin_create_question(client: AsyncClient, db_session: AsyncSession):
    admin = await create_test_user(db_session, email="admin1@example.com", is_admin=True)
    resp = await client.post(
        "/admin/questions",
        json={
            "title": "Test Admin Question",
            "scenario": "A realistic engineering scenario for testing purposes with enough detail.",
            "category": "software_engineering",
            "technologies": ["python"],
            "difficulty": "medium",
        },
        headers=auth_headers(admin),
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Test Admin Question"
    assert data["is_vetted"] == False


@pytest.mark.asyncio
async def test_admin_list_questions(client: AsyncClient, db_session: AsyncSession):
    admin = await create_test_user(db_session, email="admin2@example.com", is_admin=True)
    q = Question(
        title="List Q",
        scenario="Scenario text.",
        category=QuestionCategory.software_engineering,
        technologies=["go"],
        difficulty=QuestionDifficulty.high,
        is_vetted=True,
        is_active=True,
        generation_source=GenerationSource.human,
    )
    db_session.add(q)
    await db_session.flush()

    resp = await client.get("/admin/questions", headers=auth_headers(admin))
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert any(item["title"] == "List Q" for item in resp.json())


@pytest.mark.asyncio
async def test_admin_vet_question(client: AsyncClient, db_session: AsyncSession):
    admin = await create_test_user(db_session, email="admin3@example.com", is_admin=True)
    q = Question(
        title="Vet Me",
        scenario="Scenario.",
        category=QuestionCategory.data_science,
        technologies=["python"],
        difficulty=QuestionDifficulty.low,
        is_vetted=False,
        is_active=True,
        generation_source=GenerationSource.ai_pipeline,
    )
    db_session.add(q)
    await db_session.flush()

    resp = await client.post(f"/admin/questions/{q.id}/vet", headers=auth_headers(admin))
    assert resp.status_code == 200
    assert resp.json()["is_vetted"] == True


@pytest.mark.asyncio
async def test_admin_soft_delete_question(client: AsyncClient, db_session: AsyncSession):
    admin = await create_test_user(db_session, email="admin4@example.com", is_admin=True)
    q = Question(
        title="Delete Me",
        scenario="Scenario.",
        category=QuestionCategory.cyber_security,
        technologies=["python"],
        difficulty=QuestionDifficulty.medium,
        is_vetted=True,
        is_active=True,
        generation_source=GenerationSource.human,
    )
    db_session.add(q)
    await db_session.flush()

    resp = await client.delete(f"/admin/questions/{q.id}", headers=auth_headers(admin))
    assert resp.status_code == 204

    # Verify soft-deleted
    get_resp = await client.get(f"/admin/questions/{q.id}", headers=auth_headers(admin))
    assert get_resp.json()["is_active"] == False


@pytest.mark.asyncio
async def test_admin_requires_admin_role(client: AsyncClient, db_session: AsyncSession):
    regular_user = await create_test_user(db_session, email="notadmin@example.com", is_admin=False)
    resp = await client.get("/admin/questions", headers=auth_headers(regular_user))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_admin_get_stats(client: AsyncClient, db_session: AsyncSession):
    admin = await create_test_user(db_session, email="admin5@example.com", is_admin=True)
    resp = await client.get("/admin/stats", headers=auth_headers(admin))
    assert resp.status_code == 200
    data = resp.json()
    assert "total_users" in data
    assert "sessions_by_mode" in data
    assert "question_bank" in data


@pytest.mark.asyncio
async def test_admin_flag_session(client: AsyncClient, db_session: AsyncSession):
    admin = await create_test_user(db_session, email="admin6@example.com", is_admin=True)
    user = await create_test_user(db_session, email="flagged_user@example.com")

    # Create a session to flag
    from app.repository.sessions import SessionRepository
    repo = SessionRepository(db_session)
    session = await repo.create(user_id=user.id, mode="practice", difficulty="low")

    resp = await client.patch(
        f"/admin/sessions/{session.id}/flag",
        json={"is_flagged": True, "flag_reason": "Suspected outside AI usage"},
        headers=auth_headers(admin),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_admin_pipeline_trigger(client: AsyncClient, db_session: AsyncSession):
    admin = await create_test_user(db_session, email="admin7@example.com", is_admin=True)

    with patch("app.routes.admin.generate_questions_task") as mock_task:
        mock_task.delay = MagicMock()
        with patch("app.core.redis.get_redis") as mock_redis:
            mock = AsyncMock()
            mock.zremrangebyscore = AsyncMock()
            mock.zadd = AsyncMock()
            mock.zcard = AsyncMock(return_value=1)
            mock.expire = AsyncMock()
            mock.zrange = AsyncMock(return_value=[])
            mock.execute = AsyncMock(return_value=[0, 1, 1, True])
            mock.pipeline.return_value = mock
            mock_redis.return_value = mock

            resp = await client.post(
                "/admin/pipeline/generate",
                json={"category": "software_engineering", "difficulty": "medium", "count": 3},
                headers=auth_headers(admin),
            )
    assert resp.status_code == 200
    assert "run_id" in resp.json()


@pytest.mark.asyncio
async def test_admin_user_search(client: AsyncClient, db_session: AsyncSession):
    admin = await create_test_user(db_session, email="admin8@example.com", is_admin=True)
    await create_test_user(db_session, email="searchable@example.com", name="Searchable Person")

    resp = await client.get("/admin/users?query=searchable", headers=auth_headers(admin))
    assert resp.status_code == 200
    results = resp.json()
    assert any("searchable" in u["email"] for u in results)


@pytest.mark.asyncio
async def test_admin_update_user(client: AsyncClient, db_session: AsyncSession):
    admin = await create_test_user(db_session, email="admin9@example.com", is_admin=True)
    user = await create_test_user(db_session, email="tobeupdated@example.com")

    resp = await client.patch(
        f"/admin/users/{user.id}",
        json={"is_active": False},
        headers=auth_headers(admin),
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_admin_rescore_session(client: AsyncClient, db_session: AsyncSession):
    admin = await create_test_user(db_session, email="admin10@example.com", is_admin=True)
    user = await create_test_user(db_session, email="rescore_user@example.com")

    from app.repository.sessions import SessionRepository
    from app.repository.scores import ScoreRepository
    session_repo = SessionRepository(db_session)
    score_repo = ScoreRepository(db_session)

    session = await session_repo.create(user_id=user.id, mode="exam", difficulty="medium")
    await session_repo.complete(session.id)
    score = await score_repo.create_pending(session.id)
    await score_repo.set_failed(session.id, "Original failure")

    with patch("app.routes.admin.score_session_task") as mock_task:
        mock_task.delay = MagicMock()

        resp = await client.post(
            f"/admin/sessions/{session.id}/rescore",
            headers=auth_headers(admin),
        )
    assert resp.status_code == 200
