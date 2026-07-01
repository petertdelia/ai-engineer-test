import uuid
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.topic import SavedTopic


class TopicRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_user(self, user_id: uuid.UUID) -> list[SavedTopic]:
        result = await self.db.execute(
            select(SavedTopic)
            .where(SavedTopic.user_id == user_id)
            .order_by(SavedTopic.created_at.desc())
        )
        return result.scalars().all()

    async def create(
        self,
        user_id: uuid.UUID,
        topic_name: str,
        study_url: str,
    ) -> SavedTopic:
        topic = SavedTopic(
            user_id=user_id,
            topic_name=topic_name,
            study_url=study_url,
        )
        self.db.add(topic)
        await self.db.flush()
        await self.db.refresh(topic)
        return topic

    async def get_by_id(self, topic_id: uuid.UUID) -> Optional[SavedTopic]:
        result = await self.db.execute(
            select(SavedTopic).where(SavedTopic.id == topic_id)
        )
        return result.scalar_one_or_none()

    async def delete(self, topic_id: uuid.UUID) -> None:
        await self.db.execute(
            delete(SavedTopic).where(SavedTopic.id == topic_id)
        )
        await self.db.flush()
