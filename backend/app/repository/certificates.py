import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.certificate import Certificate


class CertificateRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
        image_url: str,
        linkedin_url: str,
        share_token: Optional[uuid.UUID] = None,
    ) -> Certificate:
        cert = Certificate(
            user_id=user_id,
            session_id=session_id,
            image_url=image_url,
            linkedin_url=linkedin_url,
            share_token=share_token or uuid.uuid4(),
        )
        self.db.add(cert)
        await self.db.flush()
        await self.db.refresh(cert)
        return cert

    async def get_by_session(self, session_id: uuid.UUID) -> Optional[Certificate]:
        result = await self.db.execute(
            select(Certificate).where(Certificate.session_id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_by_token(self, share_token: uuid.UUID) -> Optional[Certificate]:
        result = await self.db.execute(
            select(Certificate).where(Certificate.share_token == share_token)
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: uuid.UUID) -> list[Certificate]:
        result = await self.db.execute(
            select(Certificate)
            .where(Certificate.user_id == user_id)
            .order_by(Certificate.created_at.desc())
        )
        return list(result.scalars().all())
