from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_session
from app.dependencies import get_ollama_service
from app.exceptions import NotFoundError
from app.models.conversation import Conversation
from app.models.rpg import Campaign, Character, GameSession, InventoryItem, Item, Location, NPC, Quest
from app.services.ollama_service import OllamaService
from app.schemas.conversation import (
    ConversationCreate,
    ConversationRead,
    ConversationUpdate,
    ConversationWithMessages,
)
from app.services.rpg_service import character_to_dict

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationRead])
async def list_conversations(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Conversation).order_by(Conversation.updated_at.desc()))
    convs = result.scalars().all()

    # Join campaign data for all conversations
    conv_ids = [c.id for c in convs]
    gs_result = await session.execute(
        select(GameSession).where(GameSession.conversation_id.in_(conv_ids))
    )
    gs_map: dict[str, GameSession] = {gs.conversation_id: gs for gs in gs_result.scalars().all()}

    # Fetch campaign names for sessions that have campaign_id
    campaign_ids = {gs.campaign_id for gs in gs_map.values() if gs.campaign_id}
    camp_map: dict[str, str] = {}
    if campaign_ids:
        camp_result = await session.execute(
            select(Campaign).where(Campaign.id.in_(campaign_ids))
        )
        camp_map = {c.id: c.name for c in camp_result.scalars().all()}

    out = []
    for c in convs:
        data = ConversationRead.model_validate(c).model_dump()
        gs = gs_map.get(c.id)
        if gs and gs.campaign_id:
            data["campaign_id"] = gs.campaign_id
            data["campaign_name"] = camp_map.get(gs.campaign_id)
            data["session_number"] = gs.session_number
            data["session_status"] = gs.status
        out.append(data)
    return out


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


@router.get("/{conversation_id}/recap")
async def get_session_recap(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
    llm_service: OllamaService = Depends(get_ollama_service),
):
    """Return a 'Previously on...' recap for a continued campaign session."""
    if not settings.session_recap_enabled:
        return None

    result = await session.execute(
        select(GameSession).where(GameSession.conversation_id == conversation_id)
    )
    gs = result.scalars().first()
    if not gs or not gs.campaign_id or gs.session_number <= 1:
        return None

    # Get campaign name
    camp_result = await session.execute(
        select(Campaign).where(Campaign.id == gs.campaign_id)
    )
    camp = camp_result.scalars().first()
    campaign_name = camp.name if camp else gs.world_name

    # Return cached recap if available
    if gs.session_recap:
        return {
            "type": "session_recap",
            "campaign_name": campaign_name,
            "session_number": gs.session_number,
            "recap": gs.session_recap,
            "narrative": True,
        }

    # Generate recap
    from app.services import recap_service

    # Get model from conversation
    conv_result = await session.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = conv_result.scalars().first()
    model = conv.model if conv and conv.model else settings.default_model

    try:
        recap_text = await recap_service.generate_session_recap(
            db=session,
            game_session=gs,
            llm_service=llm_service,
            model=model,
        )
    except Exception:
        recap_text = ""

    if recap_text:
        gs.session_recap = recap_text
        await session.commit()

    return {
        "type": "session_recap",
        "campaign_name": campaign_name,
        "session_number": gs.session_number,
        "recap": recap_text or None,
        "narrative": bool(recap_text),
    }


@router.get("/{conversation_id}/rpg/state")
async def get_rpg_state(conversation_id: str, session: AsyncSession = Depends(get_session)):
    """Return the current RPG game state for a conversation, or null if no session exists."""
    result = await session.execute(
        select(GameSession).where(GameSession.conversation_id == conversation_id)
    )
    gs = result.scalars().first()
    if gs is None:
        return None

    # Characters with inventory
    result = await session.execute(select(Character).where(Character.session_id == gs.id))
    chars = []
    for c in result.scalars().all():
        cd = character_to_dict(c)
        # Fetch inventory for this character
        inv_result = await session.execute(
            select(InventoryItem, Item)
            .join(Item, InventoryItem.item_id == Item.id)
            .where(InventoryItem.character_id == c.id)
        )
        cd["inventory"] = [
            {
                "name": item.name,
                "item_type": item.item_type,
                "quantity": inv.quantity,
                "is_equipped": inv.is_equipped,
                "rarity": item.rarity,
                "weight": item.weight,
                "value_gp": item.value_gp,
            }
            for inv, item in inv_result.all()
        ]
        chars.append(cd)

    # Current location
    current_loc = None
    if gs.current_location_id:
        result = await session.execute(select(Location).where(Location.id == gs.current_location_id))
        loc = result.scalars().first()
        if loc:
            current_loc = {"name": loc.name, "description": loc.description, "biome": loc.biome}

    # Active quests
    result = await session.execute(
        select(Quest).where(Quest.session_id == gs.id, Quest.status == "active")
    )
    active_quests = [
        {
            "title": q.title,
            "objectives": json.loads(q.objectives),
            "description": q.description or "",
            "rewards": json.loads(q.rewards) if q.rewards else {},
        }
        for q in result.scalars().all()
    ]

    # NPCs
    result = await session.execute(select(NPC).where(NPC.session_id == gs.id))
    npcs = [
        {
            "name": n.name,
            "disposition": n.disposition,
            "familiarity": n.familiarity,
            "description": n.description or "",
        }
        for n in result.scalars().all()
    ]

    # Combat & environment
    combat = json.loads(gs.combat_state) if gs.combat_state else None
    env = json.loads(gs.environment)

    # Campaign info
    campaign_info = None
    if gs.campaign_id:
        camp_result = await session.execute(
            select(Campaign).where(Campaign.id == gs.campaign_id)
        )
        camp = camp_result.scalars().first()
        if camp:
            campaign_info = {
                "id": camp.id,
                "name": camp.name,
                "session_number": gs.session_number,
                "status": camp.status,
            }

    return {
        "type": "game_state",
        "world_name": gs.world_name,
        "characters": chars,
        "current_location": current_loc,
        "active_quests": active_quests,
        "npcs": npcs,
        "in_combat": combat is not None,
        "combat": combat,
        "environment": env,
        "campaign": campaign_info,
        "session_status": gs.status,
    }
