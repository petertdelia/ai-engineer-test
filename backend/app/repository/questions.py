import random
import uuid
from collections import defaultdict
from typing import Optional

from sqlalchemy import func, select, update, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import Question, QuestionCategory, QuestionDifficulty
from app.models.session import AssessmentSession, SessionQuestion, SessionMode


# Category distribution for Exam mode
EXAM_CATEGORY_RATIOS = {
    QuestionCategory.software_engineering: 0.40,
    QuestionCategory.data_science: 0.25,
    QuestionCategory.data_engineering: 0.20,
    QuestionCategory.cyber_security: 0.15,
}

MODE_QUESTION_COUNTS = {
    SessionMode.trial: 2,
    SessionMode.practice: 5,
    SessionMode.exam: 10,
}

MAX_TECH_RATIO = 0.40  # No more than 40% from the same technology


class QuestionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, question_id: uuid.UUID) -> Optional[Question]:
        result = await self.db.execute(
            select(Question).where(Question.id == question_id)
        )
        return result.scalar_one_or_none()

    async def list_filtered(
        self,
        category: Optional[str] = None,
        difficulty: Optional[str] = None,
        is_vetted: Optional[bool] = None,
        is_active: Optional[bool] = True,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Question], int]:
        query = select(Question)
        if category:
            query = query.where(Question.category == category)
        if difficulty:
            query = query.where(Question.difficulty == difficulty)
        if is_vetted is not None:
            query = query.where(Question.is_vetted == is_vetted)
        if is_active is not None:
            query = query.where(Question.is_active == is_active)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        result = await self.db.execute(
            query.order_by(Question.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all()), total

    async def create(self, **kwargs) -> Question:
        question = Question(**kwargs)
        self.db.add(question)
        await self.db.flush()
        await self.db.refresh(question)
        return question

    async def update(self, question_id: uuid.UUID, **kwargs) -> Optional[Question]:
        await self.db.execute(
            update(Question).where(Question.id == question_id).values(**kwargs)
        )
        await self.db.flush()
        return await self.get_by_id(question_id)

    async def soft_delete(self, question_id: uuid.UUID) -> None:
        await self.db.execute(
            update(Question).where(Question.id == question_id).values(is_active=False)
        )
        await self.db.flush()

    async def vet(self, question_id: uuid.UUID) -> Optional[Question]:
        return await self.update(question_id, is_vetted=True)

    async def select_for_session(
        self,
        mode: SessionMode,
        difficulty: QuestionDifficulty,
        user_id: Optional[uuid.UUID],
    ) -> list[Question]:
        """
        Implements the full question selection algorithm:
        1. Filter vetted + active + matching difficulty
        2. Exclude questions the user has seen in prior Exam sessions
        3. Apply technology balance constraint (max 40%)
        4. For Exam: apply category distribution
        5. Relax constraints if pool is too small
        """
        count = MODE_QUESTION_COUNTS[mode]

        # Step 1: Base pool
        base_query = select(Question).where(
            Question.is_vetted == True,
            Question.is_active == True,
            Question.difficulty == difficulty,
        )

        # Step 2: Exclude previously seen in Exam sessions
        if user_id:
            seen_subquery = (
                select(SessionQuestion.question_id)
                .join(AssessmentSession, SessionQuestion.session_id == AssessmentSession.id)
                .where(
                    AssessmentSession.user_id == user_id,
                    AssessmentSession.mode == SessionMode.exam,
                )
                .scalar_subquery()
            )
            base_query = base_query.where(Question.id.not_in(seen_subquery))

        result = await self.db.execute(base_query)
        pool = list(result.scalars().all())

        if not pool:
            return []

        # Step 3 + 4: For Exam, apply category distribution + tech balance
        if mode == SessionMode.exam:
            selected = self._select_with_constraints(pool, count)
        else:
            # Trial/Practice: just apply tech balance
            selected = self._apply_tech_balance(pool, count)

        return selected

    def _apply_tech_balance(self, pool: list[Question], count: int) -> list[Question]:
        """Select `count` questions with no single tech > 40%."""
        if len(pool) <= count:
            return pool

        random.shuffle(pool)
        selected = []
        tech_counts: dict[str, int] = defaultdict(int)

        for q in pool:
            if len(selected) >= count:
                break
            # Check if adding this question violates the tech balance constraint
            can_add = True
            for tech in q.technologies:
                if (tech_counts[tech] + 1) / (len(selected) + 1) > MAX_TECH_RATIO:
                    can_add = False
                    break
            if can_add:
                selected.append(q)
                for tech in q.technologies:
                    tech_counts[tech] += 1

        # Relax constraint if not enough
        if len(selected) < count:
            remaining = [q for q in pool if q not in selected]
            random.shuffle(remaining)
            for q in remaining:
                if len(selected) >= count:
                    break
                selected.append(q)

        return selected[:count]

    def _select_with_constraints(self, pool: list[Question], count: int) -> list[Question]:
        """Select questions with category distribution + tech balance for Exam mode."""
        if len(pool) <= count:
            return pool

        # Group by category
        by_category: dict[str, list[Question]] = defaultdict(list)
        for q in pool:
            by_category[q.category.value].append(q)

        # Shuffle each category's pool
        for cat_list in by_category.values():
            random.shuffle(cat_list)

        # Calculate target counts per category
        target_counts = {}
        for cat, ratio in EXAM_CATEGORY_RATIOS.items():
            target_counts[cat.value] = round(count * ratio)

        # Adjust to hit exact count
        total_targeted = sum(target_counts.values())
        if total_targeted != count:
            # Add extras to the largest category
            largest_cat = max(EXAM_CATEGORY_RATIOS, key=EXAM_CATEGORY_RATIOS.get)
            target_counts[largest_cat.value] += count - total_targeted

        selected = []
        tech_counts: dict[str, int] = defaultdict(int)

        # Pick questions per category target
        for cat_name, target in target_counts.items():
            cat_questions = by_category.get(cat_name, [])
            picked = 0
            for q in cat_questions:
                if picked >= target:
                    break
                can_add = True
                for tech in q.technologies:
                    projected_total = len(selected) + 1
                    if projected_total > 0 and (tech_counts[tech] + 1) / projected_total > MAX_TECH_RATIO:
                        can_add = False
                        break
                if can_add:
                    selected.append(q)
                    for tech in q.technologies:
                        tech_counts[tech] += 1
                    picked += 1

        # Fill any remaining slots from the pool (relax constraints)
        if len(selected) < count:
            remaining = [q for q in pool if q not in selected]
            random.shuffle(remaining)
            for q in remaining:
                if len(selected) >= count:
                    break
                selected.append(q)

        return selected[:count]

    async def count_by_category_difficulty(self) -> list[dict]:
        result = await self.db.execute(
            select(
                Question.category,
                Question.difficulty,
                func.count().label("count"),
            )
            .where(Question.is_active == True)
            .group_by(Question.category, Question.difficulty)
        )
        return [
            {"category": row.category.value, "difficulty": row.difficulty.value, "count": row.count}
            for row in result.all()
        ]
