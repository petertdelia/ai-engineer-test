import uuid
from datetime import datetime

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.errors import (
    InsufficientScoreForCertificate,
    SessionNotFound,
)
from app.models.session import SessionMode, SessionStatus
from app.models.user import User
from app.repository.certificates import CertificateRepository
from app.repository.scores import ScoreRepository
from app.repository.sessions import SessionRepository
from app.repository.users import UserRepository
from app.schemas.scores import QuestionScoreDetail, ResultsResponse

router = APIRouter(prefix="/sessions", tags=["results"])
logger = structlog.get_logger()


@router.get("/{session_id}/results", response_model=ResultsResponse)
async def get_results(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session_repo = SessionRepository(db)
    session = await session_repo.get_by_id(session_id)
    if not session or session.user_id != current_user.id:
        raise SessionNotFound()

    if session.status not in (SessionStatus.completed, SessionStatus.flagged):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "SESSION_NOT_COMPLETED",
                "message": "Session has not been completed yet",
                "detail": {},
            }
        )

    # Trial/Practice sessions are never scored
    if session.mode in (SessionMode.trial, SessionMode.practice):
        # Still return submitted responses
        sq_rows = await session_repo.get_session_questions_with_details(session_id)
        question_details = []
        for sq, q in sq_rows:
            question_details.append(QuestionScoreDetail(
                question_id=q.id,
                order_index=sq.order_index,
                title=q.title,
                response_text=sq.response_text,
                score_engineering_skill=None,
                score_ai_collaboration=None,
                score_ai_trust_calibration=None,
                score_engineering_judgement=None,
                scoring_notes=None,
                ai_interactions=sq.ai_interactions or [],
            ))
        return ResultsResponse(
            status="not_scored",
            mode=session.mode.value,
            session_id=session_id,
            question_details=question_details,
        )

    # Exam mode: check scoring status
    score_repo = ScoreRepository(db)
    score = await score_repo.get_by_session(session_id)
    if not score:
        return ResultsResponse(status="pending", session_id=session_id)

    if score.status.value == "pending":
        return ResultsResponse(status="pending", session_id=session_id)

    if score.status.value == "failed":
        return ResultsResponse(
            status="failed",
            session_id=session_id,
            failure_reason=score.failure_reason,
        )

    # Completed — return full details
    sq_rows = await session_repo.get_session_questions_with_details(session_id)
    question_details = []
    for sq, q in sq_rows:
        question_details.append(QuestionScoreDetail(
            question_id=q.id,
            order_index=sq.order_index,
            title=q.title,
            response_text=sq.response_text,
            score_engineering_skill=sq.score_engineering_skill,
            score_ai_collaboration=sq.score_ai_collaboration,
            score_ai_trust_calibration=sq.score_ai_trust_calibration,
            score_engineering_judgement=sq.score_engineering_judgement,
            scoring_notes=sq.scoring_notes,
            ai_interactions=sq.ai_interactions or [],
        ))

    return ResultsResponse(
        status="completed",
        session_id=session_id,
        engineering_skill=score.engineering_skill,
        ai_collaboration=score.ai_collaboration,
        ai_trust_calibration=score.ai_trust_calibration,
        engineering_judgement=score.engineering_judgement,
        total_score=score.total_score,
        percentile_rank=score.percentile_rank,
        computed_at=score.computed_at,
        question_details=question_details,
    )


@router.get("/{session_id}/certificate")
async def get_or_create_certificate(
    session_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session_repo = SessionRepository(db)
    session = await session_repo.get_by_id(session_id)
    if not session or session.user_id != current_user.id:
        raise SessionNotFound()

    # Only Exam sessions can earn certificates
    if session.mode != SessionMode.exam:
        raise InsufficientScoreForCertificate("Certificates are only available for Exam sessions")

    score_repo = ScoreRepository(db)
    score = await score_repo.get_by_session(session_id)

    if not score or score.status.value != "completed":
        raise HTTPException(status_code=409, detail={
            "error": "SCORE_NOT_READY",
            "message": "Score is not yet available",
            "detail": {},
        })

    if (score.total_score or 0) < settings.CERTIFICATE_MIN_SCORE:
        raise InsufficientScoreForCertificate(
            f"Score {score.total_score:.1f} is below the minimum {settings.CERTIFICATE_MIN_SCORE}"
        )

    # Check if certificate already exists
    cert_repo = CertificateRepository(db)
    existing = await cert_repo.get_by_session(session_id)
    if existing:
        return {
            "id": str(existing.id),
            "image_url": existing.image_url,
            "share_token": str(existing.share_token),
            "linkedin_url": existing.linkedin_url,
            "created_at": existing.created_at.isoformat(),
        }

    # Generate certificate in background
    background_tasks.add_task(
        _generate_and_store_certificate,
        session_id=session_id,
        user_id=current_user.id,
        user_name=current_user.name,
        score_data={
            "total_score": score.total_score,
            "engineering_skill": score.engineering_skill,
            "ai_collaboration": score.ai_collaboration,
            "ai_trust_calibration": score.ai_trust_calibration,
            "engineering_judgement": score.engineering_judgement,
        },
    )

    return {"message": "Certificate generation in progress", "status": "generating"}


async def _generate_and_store_certificate(
    session_id: uuid.UUID,
    user_id: uuid.UUID,
    user_name: str,
    score_data: dict,
) -> None:
    from app.core.certificates import generate_certificate_image
    from app.core.database import async_session_factory
    import uuid as uuid_module

    share_token = uuid_module.uuid4()

    try:
        image_url, linkedin_url = await generate_certificate_image(
            user_name=user_name,
            score_data=score_data,
            session_id=session_id,
            share_token=share_token,
        )

        async with async_session_factory() as db:
            cert_repo = CertificateRepository(db)
            # Check again to avoid duplicates
            existing = await cert_repo.get_by_session(session_id)
            if not existing:
                await cert_repo.create(
                    user_id=user_id,
                    session_id=session_id,
                    image_url=image_url,
                    linkedin_url=linkedin_url,
                    share_token=share_token,
                )
            await db.commit()
    except Exception as e:
        logger.error("certificate_generation_failed", session_id=str(session_id), error=str(e))


@router.get("/{session_id}/certificate/share")
async def share_certificate(
    session_id: uuid.UUID,
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint — no auth required, token-based access."""
    import uuid as uuid_module
    try:
        share_token = uuid_module.UUID(token)
    except ValueError:
        raise HTTPException(status_code=404, detail="Invalid token")

    cert_repo = CertificateRepository(db)
    cert = await cert_repo.get_by_token(share_token)
    if not cert or cert.session_id != session_id:
        raise HTTPException(status_code=404, detail="Certificate not found")

    score_repo = ScoreRepository(db)
    score = await score_repo.get_by_session(session_id)

    return {
        "image_url": cert.image_url,
        "linkedin_url": cert.linkedin_url,
        "share_token": str(cert.share_token),
        "created_at": cert.created_at.isoformat(),
        "total_score": score.total_score if score else None,
    }
