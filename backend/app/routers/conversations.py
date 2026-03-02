from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_session
from app.exceptions import NotFoundError
from app.models.conversation import Conversation
from app.schemas.conversation import (
    ConversationCreate,
    ConversationRead,
    ConversationUpdate,
    ConversationWithMessages,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationRead])
async def list_conversations(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Conversation).order_by(Conversation.updated_at.desc()))
    return result.scalars().all()


@router.post("", response_model=ConversationRead, status_code=201)
async def create_conversation(
    data: ConversationCreate, session: AsyncSession = Depends(get_session)
):
    conv = Conversation(title=data.title, model=data.model)
    session.add(conv)
    await session.commit()
    await session.refresh(conv)
    return conv


@router.get("/{conversation_id}", response_model=ConversationWithMessages)
async def get_conversation(conversation_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise NotFoundError("Conversation", conversation_id)
    return conv


@router.patch("/{conversation_id}", response_model=ConversationRead)
async def update_conversation(
    conversation_id: str,
    data: ConversationUpdate,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise NotFoundError("Conversation", conversation_id)

    if data.title is not None:
        conv.title = data.title
    if data.model is not None:
        conv.model = data.model

    await session.commit()
    await session.refresh(conv)
    return conv


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise NotFoundError("Conversation", conversation_id)

    await session.delete(conv)
    await session.commit()
