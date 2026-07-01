import asyncio
import uuid

import sentry_sdk
import structlog

from app.workers.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # Base delay; exponential via countdown
    name="app.workers.scoring.score_session_task",
)
def score_session_task(self, session_id_str: str, request_id: str | None = None) -> dict:
    """Score a completed exam session. Retries up to 3 times with exponential backoff."""
    session_id = uuid.UUID(session_id_str)

    if request_id:
        try:
            import structlog.contextvars
            structlog.contextvars.bind_contextvars(request_id=request_id, session_id=session_id_str)
        except Exception:
            pass

    sentry_sdk.set_context("task", {"session_id": session_id_str, "task_id": self.request.id})

    async def _run():
        from app.core.database import async_session_factory
        from app.core.scoring import score_session
        from app.repository.scores import ScoreRepository

        async with async_session_factory() as db:
            try:
                scores = await score_session(session_id, db)
                score_repo = ScoreRepository(db)
                await score_repo.update_score(
                    session_id=session_id,
                    engineering_skill=scores["engineering_skill"],
                    ai_collaboration=scores["ai_collaboration"],
                    ai_trust_calibration=scores["ai_trust_calibration"],
                    engineering_judgement=scores["engineering_judgement"],
                    total_score=scores["total_score"],
                )
                await db.commit()
                logger.info("session_scored", session_id=session_id_str, total_score=scores["total_score"])
                return {"status": "completed", "session_id": session_id_str}
            except Exception as e:
                await db.rollback()
                raise e

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("scoring_task_failed", session_id=session_id_str, error=str(exc), retry_count=self.request.retries)
        sentry_sdk.capture_exception(exc)

        # Exponential backoff: 60s, 120s, 240s
        retry_countdown = 60 * (2 ** self.request.retries)

        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=retry_countdown)
        else:
            # Final failure — mark score as failed
            async def _mark_failed():
                from app.core.database import async_session_factory
                from app.repository.scores import ScoreRepository
                async with async_session_factory() as db:
                    score_repo = ScoreRepository(db)
                    await score_repo.set_failed(session_id, str(exc))
                    await db.commit()

            asyncio.run(_mark_failed())
            return {"status": "failed", "session_id": session_id_str, "error": str(exc)}
