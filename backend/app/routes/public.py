import structlog
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis import get_redis

router = APIRouter(tags=["public"])
logger = structlog.get_logger()


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Verify DB and Redis connections."""
    status = {"status": "ok", "database": "ok", "redis": "ok"}

    # Check database
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        status["database"] = f"error: {str(e)}"
        status["status"] = "degraded"

    # Check Redis
    try:
        redis = get_redis()
        await redis.ping()
    except Exception as e:
        status["redis"] = f"error: {str(e)}"
        status["status"] = "degraded"

    return status


@router.get("/leaderboard")
async def get_leaderboard(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(__import__("app.core.auth", fromlist=["get_current_user"]).get_current_user),
):
    from app.core.config import settings
    from app.models.score import SessionScore, ScoreStatus
    from app.models.session import AssessmentSession, SessionMode, SessionStatus
    from app.models.user import User
    from sqlalchemy import select, func

    # Check minimum population
    count_result = await db.execute(
        select(func.count(SessionScore.id))
        .join(AssessmentSession, SessionScore.session_id == AssessmentSession.id)
        .where(
            SessionScore.status == ScoreStatus.completed,
            AssessmentSession.mode == SessionMode.exam,
        )
    )
    total_qualified = count_result.scalar_one()

    if total_qualified < settings.LEADERBOARD_MIN_POPULATION:
        return {
            "available": False,
            "message": f"Leaderboard available once {settings.LEADERBOARD_MIN_POPULATION} candidates complete exams",
            "current_count": total_qualified,
        }

    # Return top 50 with is_public_rank=True
    result = await db.execute(
        select(User.name, User.avatar_url, SessionScore.total_score, SessionScore.percentile_rank)
        .join(AssessmentSession, SessionScore.session_id == AssessmentSession.id)
        .join(User, AssessmentSession.user_id == User.id)
        .where(
            User.is_public_rank == True,
            SessionScore.status == ScoreStatus.completed,
            AssessmentSession.mode == SessionMode.exam,
        )
        .order_by(SessionScore.total_score.desc())
        .limit(50)
    )

    entries = result.all()
    return {
        "available": True,
        "total_qualified": total_qualified,
        "entries": [
            {
                "name": row.name,
                "avatar_url": row.avatar_url,
                "total_score": row.total_score,
                "percentile_rank": row.percentile_rank,
            }
            for row in entries
        ],
    }
