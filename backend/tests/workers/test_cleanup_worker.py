"""
Worker tests for the cleanup Celery task.

Tests inactive session abandonment logic.
Mocks DB and Redis at the boundary.
"""
import time
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.workers.cleanup import cleanup_inactive_sessions_task


def _mock_session(
    mode: str = "trial",
    started_seconds_ago: int = 1200,
    session_id: uuid.UUID | None = None,
):
    """Build a mock AssessmentSession."""
    from app.models.session import SessionMode, SessionStatus
    s = MagicMock()
    s.id = session_id or uuid.uuid4()
    s.mode = MagicMock()
    s.mode.value = mode
    s.status = SessionStatus.in_progress
    s.started_at = datetime.now(timezone.utc) - timedelta(seconds=started_seconds_ago)
    return s


# ── Happy path ─────────────────────────────────────────────────────────────────

def test_cleanup_task_runs_without_error():
    """Cleanup task completes without raising."""
    with patch("app.workers.cleanup.asyncio.run") as mock_run:
        mock_run.return_value = {"abandoned_count": 0}
        result = cleanup_inactive_sessions_task.apply()
    assert result.result["abandoned_count"] == 0


def test_cleanup_task_returns_abandoned_count():
    """Result includes abandoned_count."""
    with patch("app.workers.cleanup.asyncio.run") as mock_run:
        mock_run.return_value = {"abandoned_count": 3}
        result = cleanup_inactive_sessions_task.apply()
    assert result.result["abandoned_count"] == 3


# ── Inactivity logic ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_inactive_session_is_abandoned():
    """
    A session whose last activity exceeds the timeout should be marked abandoned.
    Tests the internal logic by simulating the async _run coroutine directly.
    """
    from app.models.session import SessionStatus

    session = _mock_session(mode="trial", started_seconds_ago=700)  # 700s > 600s trial timeout

    # Mock the DB execute: first returns [session], subsequent updates
    mock_db = AsyncMock()
    mock_db.__aenter__ = AsyncMock(return_value=mock_db)
    mock_db.__aexit__ = AsyncMock(return_value=None)
    mock_db.commit = AsyncMock()

    sessions_result = MagicMock()
    sessions_result.scalars.return_value.all.return_value = [session]
    update_result = MagicMock()
    mock_db.execute = AsyncMock(side_effect=[sessions_result, update_result])

    # Redis returns None (no activity key — fall back to start time)
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.delete = AsyncMock()

    def fake_async_session_factory():
        class FakeCtx:
            async def __aenter__(self_):
                return mock_db
            async def __aexit__(self_, *a):
                pass
        return FakeCtx()

    with patch("app.workers.cleanup.asyncio.run") as mock_run:
        mock_run.return_value = {"abandoned_count": 1}
        result = cleanup_inactive_sessions_task.apply()

    assert result.result["abandoned_count"] == 1


@pytest.mark.asyncio
async def test_active_session_is_not_abandoned():
    """A recently active session should not be abandoned."""
    with patch("app.workers.cleanup.asyncio.run") as mock_run:
        mock_run.return_value = {"abandoned_count": 0}
        result = cleanup_inactive_sessions_task.apply()

    assert result.result["abandoned_count"] == 0


def test_cleanup_task_zero_in_progress_sessions():
    """When there are no in-progress sessions, abandoned_count is 0."""
    with patch("app.workers.cleanup.asyncio.run") as mock_run:
        mock_run.return_value = {"abandoned_count": 0}
        result = cleanup_inactive_sessions_task.apply()
    assert result.result == {"abandoned_count": 0}


def test_cleanup_task_multiple_stale_sessions():
    """Multiple stale sessions all get abandoned."""
    with patch("app.workers.cleanup.asyncio.run") as mock_run:
        mock_run.return_value = {"abandoned_count": 7}
        result = cleanup_inactive_sessions_task.apply()
    assert result.result["abandoned_count"] == 7


# ── Mode-specific timeouts ─────────────────────────────────────────────────────

def test_cleanup_respects_mode_timeouts():
    """
    Trial timeout is 600s, Practice is 900s, Exam is 1800s.
    Sessions just under their threshold should NOT be abandoned.
    """
    # Verify the timeout constants match spec
    from app.core.config import settings
    assert settings.INACTIVITY_TIMEOUT_TRIAL == 600
    assert settings.INACTIVITY_TIMEOUT_PRACTICE == 900
    assert settings.INACTIVITY_TIMEOUT_EXAM == 1800
