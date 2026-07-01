import asyncio
import time
from datetime import datetime, timezone

import structlog

from app.workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(name="app.workers.cleanup.cleanup_inactive_sessions_task")
def cleanup_inactive_sessions_task() -> dict:
    """Mark sessions as abandoned if they've been inactive past their timeout."""

    async def _run():
        from app.core.config import settings
        from app.core.database import async_session_factory
        from app.core.redis import get_redis
        from app.models.session import AssessmentSession, SessionMode, SessionStatus
        from sqlalchemy import select, update

        redis = get_redis()
        now = time.time()

        # Inactivity timeouts per mode
        inactivity_timeouts = {
            "trial": settings.INACTIVITY_TIMEOUT_TRIAL,
            "practice": settings.INACTIVITY_TIMEOUT_PRACTICE,
            "exam": settings.INACTIVITY_TIMEOUT_EXAM,
        }

        abandoned_count = 0

        async with async_session_factory() as db:
            # Fetch all in-progress sessions
            result = await db.execute(
                select(AssessmentSession).where(
                    AssessmentSession.status == SessionStatus.in_progress
                )
            )
            sessions = result.scalars().all()

            for session in sessions:
                mode_key = session.mode.value
                timeout = inactivity_timeouts.get(mode_key, 1800)

                activity_key = f"session_activity:{session.id}"
                last_activity_str = await redis.get(activity_key)

                if last_activity_str is None:
                    # No activity record — use session start time as fallback
                    if session.started_at:
                        started = session.started_at.timestamp() if hasattr(session.started_at, 'timestamp') else now
                        if (now - started) > timeout:
                            await db.execute(
                                update(AssessmentSession)
                                .where(AssessmentSession.id == session.id)
                                .values(
                                    status=SessionStatus.abandoned,
                                    ended_at=datetime.now(timezone.utc),
                                )
                            )
                            abandoned_count += 1
                else:
                    last_activity = float(last_activity_str)
                    if (now - last_activity) > timeout:
                        await db.execute(
                            update(AssessmentSession)
                            .where(AssessmentSession.id == session.id)
                            .values(
                                status=SessionStatus.abandoned,
                                ended_at=datetime.now(timezone.utc),
                            )
                        )
                        await redis.delete(activity_key)
                        abandoned_count += 1

            if abandoned_count > 0:
                await db.commit()
                logger.info("sessions_abandoned_for_inactivity", count=abandoned_count)

        return {"abandoned_count": abandoned_count}

    return asyncio.run(_run())


@celery_app.task(name="app.workers.cleanup.recompute_percentile_ranks_task")
def recompute_percentile_ranks_task() -> dict:
    """Nightly job to recompute percentile ranks across all completed exam scores."""

    async def _run():
        from app.core.config import settings
        from app.core.database import async_session_factory
        from app.models.score import ScoreStatus, SessionScore
        from app.models.session import AssessmentSession, SessionMode
        from sqlalchemy import select, func, update

        async with async_session_factory() as db:
            # Count qualified scores
            count_result = await db.execute(
                select(func.count(SessionScore.id))
                .join(AssessmentSession, SessionScore.session_id == AssessmentSession.id)
                .where(
                    SessionScore.status == ScoreStatus.completed,
                    AssessmentSession.mode == SessionMode.exam,
                )
            )
            total = count_result.scalar_one()

            if total < settings.LEADERBOARD_MIN_POPULATION:
                logger.info("percentile_recompute_skipped", reason="insufficient_population", count=total)
                return {"skipped": True, "count": total}

            # Fetch all scores ordered by total_score
            result = await db.execute(
                select(SessionScore.id, SessionScore.total_score)
                .join(AssessmentSession, SessionScore.session_id == AssessmentSession.id)
                .where(
                    SessionScore.status == ScoreStatus.completed,
                    AssessmentSession.mode == SessionMode.exam,
                    SessionScore.total_score.isnot(None),
                )
                .order_by(SessionScore.total_score)
            )
            scores = result.all()
            n = len(scores)

            for rank, (score_id, total_score) in enumerate(scores):
                percentile = round((rank / n) * 100, 1)
                await db.execute(
                    update(SessionScore)
                    .where(SessionScore.id == score_id)
                    .values(percentile_rank=percentile)
                )

            await db.commit()
            logger.info("percentile_ranks_recomputed", count=n)
            return {"recomputed": n}

    return asyncio.run(_run())
