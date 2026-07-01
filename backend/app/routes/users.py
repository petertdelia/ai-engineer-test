import json

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.redis import cache_delete, cache_get, cache_set
from app.models.user import User
from app.repository.certificates import CertificateRepository
from app.repository.scores import ScoreRepository
from app.repository.sessions import SessionRepository
from app.repository.topics import TopicRepository
from app.repository.users import UserRepository
from app.schemas.users import CertificateListItem, StatsResponse, UpdateProfileRequest, UserResponse

router = APIRouter(prefix="/users", tags=["users"])
logger = structlog.get_logger()

STATS_CACHE_TTL = 300  # 5 minutes


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    request: UpdateProfileRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if request.model_fields_set and "email" in request.model_fields_set:
        raise HTTPException(status_code=422, detail="Email cannot be changed via this endpoint")

    updates = request.model_dump(exclude_unset=True)
    if not updates:
        return current_user

    repo = UserRepository(db)
    updated = await repo.update(current_user.id, **updates)
    # Invalidate stats cache
    await cache_delete(f"user_stats:{current_user.id}")
    return updated


@router.delete("/me", status_code=204)
async def delete_account(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = UserRepository(db)
    await repo.delete(current_user.id)
    return None


@router.get("/me/export")
async def export_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """GDPR data export."""
    session_repo = SessionRepository(db)
    score_repo = ScoreRepository(db)
    cert_repo = CertificateRepository(db)

    sessions = await session_repo.get_by_user(current_user.id, limit=1000)
    session_data = []
    for session in sessions:
        questions_with_detail = await session_repo.get_session_questions_with_details(session.id)
        score = await score_repo.get_by_session(session.id)
        session_data.append({
            "id": str(session.id),
            "mode": session.mode.value,
            "difficulty": session.difficulty.value,
            "status": session.status.value,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
            "questions": [
                {
                    "question_id": str(sq.question_id),
                    "order_index": sq.order_index,
                    "response_text": sq.response_text,
                    "code_response": sq.code_response,
                    "ai_interactions": sq.ai_interactions,
                    "submitted_at": sq.submitted_at.isoformat() if sq.submitted_at else None,
                }
                for sq, q in questions_with_detail
            ],
            "score": {
                "status": score.status.value,
                "total_score": score.total_score,
                "engineering_skill": score.engineering_skill,
                "ai_collaboration": score.ai_collaboration,
                "ai_trust_calibration": score.ai_trust_calibration,
                "engineering_judgement": score.engineering_judgement,
            } if score else None,
        })

    certificates = await cert_repo.list_by_user(current_user.id)

    return {
        "profile": {
            "id": str(current_user.id),
            "email": current_user.email,
            "name": current_user.name,
            "created_at": current_user.created_at.isoformat(),
        },
        "sessions": session_data,
        "certificates": [
            {"session_id": str(c.session_id), "image_url": c.image_url, "created_at": c.created_at.isoformat()}
            for c in certificates
        ],
    }


@router.get("/me/stats", response_model=StatsResponse)
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cache_key = f"user_stats:{current_user.id}"
    cached = await cache_get(cache_key)
    if cached:
        return json.loads(cached)

    repo = UserRepository(db)
    stats = await repo.get_stats(current_user.id)
    await cache_set(cache_key, json.dumps(stats, default=str), STATS_CACHE_TTL)
    return stats


@router.get("/me/certificates", response_model=list[CertificateListItem])
async def list_certificates(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cert_repo = CertificateRepository(db)
    score_repo = ScoreRepository(db)
    certs = await cert_repo.list_by_user(current_user.id)

    result = []
    for cert in certs:
        score = await score_repo.get_by_session(cert.session_id)
        result.append(CertificateListItem(
            id=cert.id,
            session_id=cert.session_id,
            total_score=score.total_score if score else None,
            image_url=cert.image_url,
            share_token=cert.share_token,
            linkedin_url=cert.linkedin_url,
            created_at=cert.created_at,
        ))
    return result


@router.patch("/me/rank-opt-in", response_model=UserResponse)
async def toggle_rank_opt_in(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = UserRepository(db)
    new_value = not current_user.is_public_rank
    updated = await repo.update(current_user.id, is_public_rank=new_value)
    return updated
