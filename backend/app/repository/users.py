import json
import uuid
from typing import Optional

from sqlalchemy import select, text, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        email: str,
        name: str,
        hashed_password: Optional[str] = None,
        auth_provider: str = "email",
        avatar_url: Optional[str] = None,
        is_email_verified: bool = False,
    ) -> User:
        user = User(
            email=email.lower(),
            name=name,
            hashed_password=hashed_password,
            auth_provider=auth_provider,
            avatar_url=avatar_url,
            is_email_verified=is_email_verified,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def update(self, user_id: uuid.UUID, **kwargs) -> Optional[User]:
        await self.db.execute(
            update(User).where(User.id == user_id).values(**kwargs)
        )
        await self.db.flush()
        return await self.get_by_id(user_id)

    async def delete(self, user_id: uuid.UUID) -> None:
        """Hard-delete the user and anonymize their session records."""
        from app.models.session import AssessmentSession

        # Anonymize sessions
        await self.db.execute(
            update(AssessmentSession)
            .where(AssessmentSession.user_id == user_id)
            .values(user_id=None)
        )
        await self.db.execute(delete(User).where(User.id == user_id))
        await self.db.flush()

    async def get_stats(self, user_id: uuid.UUID) -> dict:
        """Complex stats query with per-technology breakdowns and score trends."""
        # Per-technology strength: unnest technologies JSONB, join through SessionQuestion
        tech_query = text("""
            SELECT
                tech.value AS technology,
                ROUND(AVG(
                    (sq.score_engineering_skill + sq.score_ai_collaboration +
                     sq.score_ai_trust_calibration + sq.score_engineering_judgement) / 4.0
                ), 2) AS average_score,
                COUNT(DISTINCT s.id) AS session_count
            FROM assessment_sessions s
            JOIN session_questions sq ON sq.session_id = s.id
            JOIN questions q ON q.id = sq.question_id,
            jsonb_array_elements_text(q.technologies) AS tech(value)
            WHERE s.user_id = :user_id
              AND s.status = 'completed'
              AND sq.score_engineering_skill IS NOT NULL
            GROUP BY tech.value
            ORDER BY average_score DESC
        """)

        # Score trend across sessions
        trend_query = text("""
            SELECT
                s.id AS session_id,
                s.ended_at AS completed_at,
                ss.total_score,
                s.mode
            FROM assessment_sessions s
            JOIN session_scores ss ON ss.session_id = s.id
            WHERE s.user_id = :user_id
              AND s.status = 'completed'
              AND ss.status = 'completed'
            ORDER BY s.ended_at DESC
            LIMIT 20
        """)

        # Summary counts
        summary_query = text("""
            SELECT
                COUNT(*) AS total_sessions,
                COUNT(*) FILTER (WHERE mode = 'exam' AND status = 'completed') AS completed_exams,
                MAX(ss.total_score) AS best_score
            FROM assessment_sessions s
            LEFT JOIN session_scores ss ON ss.session_id = s.id AND ss.status = 'completed'
            WHERE s.user_id = :user_id
        """)

        tech_result = await self.db.execute(tech_query, {"user_id": str(user_id)})
        trend_result = await self.db.execute(trend_query, {"user_id": str(user_id)})
        summary_result = await self.db.execute(summary_query, {"user_id": str(user_id)})

        tech_rows = tech_result.fetchall()
        trend_rows = trend_result.fetchall()
        summary_row = summary_result.fetchone()

        return {
            "tech_strengths": [
                {
                    "technology": row.technology,
                    "average_score": float(row.average_score or 0),
                    "session_count": row.session_count,
                }
                for row in tech_rows
            ],
            "score_trends": [
                {
                    "session_id": row.session_id,
                    "completed_at": row.completed_at,
                    "total_score": float(row.total_score or 0),
                    "mode": row.mode,
                }
                for row in trend_rows
            ],
            "total_sessions": summary_row.total_sessions if summary_row else 0,
            "completed_exams": summary_row.completed_exams if summary_row else 0,
            "best_score": float(summary_row.best_score) if summary_row and summary_row.best_score else None,
        }
