import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.repository.topics import TopicRepository

router = APIRouter(prefix="/users/me/topics", tags=["topics"])


class CreateTopicRequest(BaseModel):
    topic_name: str = Field(min_length=1, max_length=500)
    study_url: str = Field(min_length=1, max_length=2048)


class TopicResponse(BaseModel):
    id: uuid.UUID
    topic_name: str
    study_url: str

    model_config = {"from_attributes": True}


@router.get("", response_model=list[TopicResponse])
async def list_topics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = TopicRepository(db)
    return await repo.list_by_user(current_user.id)


@router.post("", response_model=TopicResponse, status_code=201)
async def create_topic(
    request: CreateTopicRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = TopicRepository(db)
    return await repo.create(
        user_id=current_user.id,
        topic_name=request.topic_name,
        study_url=request.study_url,
    )


@router.delete("/{topic_id}", status_code=204)
async def delete_topic(
    topic_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    repo = TopicRepository(db)
    topic = await repo.get_by_id(topic_id)
    if not topic or topic.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Topic not found")
    await repo.delete(topic_id)
    return None
