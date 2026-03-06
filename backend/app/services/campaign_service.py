"""Campaign persistence service (Phase 5.1).

Manages campaign lifecycle: create, continue (re-parent entities), summaries.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.rpg import (
    Campaign,
    Character,
    GameSession,
    Location,
    NPC,
    Quest,
    Relationship,
)

logger = logging.getLogger(__name__)


async def create_campaign(
    db: AsyncSession,
    name: str,
    description: str = "",
    world_name: str = "",
) -> Campaign:
    campaign = Campaign(
        name=name,
        description=description,
        world_name=world_name or "Unnamed World",
    )
    db.add(campaign)
    await db.flush()
    return campaign


async def get_campaign(db: AsyncSession, campaign_id: str) -> Campaign | None:
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    return result.scalars().first()


async def list_campaigns(
    db: AsyncSession,
    status: str | None = None,
) -> list[dict]:
    q = select(Campaign).order_by(Campaign.updated_at.desc())
    if status:
        q = q.where(Campaign.status == status)
    result = await db.execute(q)
    campaigns = result.scalars().all()

    out = []
    for c in campaigns:
        count_result = await db.execute(
            select(GameSession).where(GameSession.campaign_id == c.id)
        )
        session_count = len(count_result.scalars().all())
        out.append({
            "id": c.id,
            "name": c.name,
            "world_name": c.world_name,
            "description": c.description,
            "status": c.status,
            "session_count": session_count,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        })
    return out


async def get_campaign_detail(db: AsyncSession, campaign_id: str) -> dict | None:
    campaign = await get_campaign(db, campaign_id)
    if not campaign:
        return None

    result = await db.execute(
        select(GameSession)
        .where(GameSession.campaign_id == campaign_id)
        .order_by(GameSession.session_number)
    )
    sessions = result.scalars().all()

    return {
        "id": campaign.id,
        "name": campaign.name,
        "world_name": campaign.world_name,
        "description": campaign.description,
        "status": campaign.status,
        "session_count": len(sessions),
        "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
        "updated_at": campaign.updated_at.isoformat() if campaign.updated_at else None,
        "sessions": [
            {
                "conversation_id": s.conversation_id,
                "session_number": s.session_number,
                "status": s.status,
                "world_name": s.world_name,
                "summary": s.session_summary,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in sessions
        ],
    }


async def continue_campaign(db: AsyncSession, campaign_id: str) -> dict:
    """Continue a campaign: create new conversation + session, re-parent entities."""
    campaign = await get_campaign(db, campaign_id)
    if not campaign:
        raise ValueError("Campaign not found")
    if campaign.status != "active":
        raise ValueError("Campaign is not active")

    # Check no active session exists
    result = await db.execute(
        select(GameSession).where(
            GameSession.campaign_id == campaign_id,
            GameSession.status == "active",
        )
    )
    active = result.scalars().first()
    if active:
        raise ValueError(
            f"Campaign already has an active session (conversation {active.conversation_id})"
        )

    # Find the last ended session
    result = await db.execute(
        select(GameSession)
        .where(
            GameSession.campaign_id == campaign_id,
            GameSession.status == "ended",
        )
        .order_by(GameSession.session_number.desc())
        .limit(1)
    )
    last_session = result.scalars().first()
    if not last_session:
        raise ValueError("No ended session found to continue from")

    new_session_number = last_session.session_number + 1

    # Create new conversation
    conv = Conversation(
        title=f"{campaign.name} - Session {new_session_number}",
        model="qwen3.5:9b",
    )
    db.add(conv)
    await db.flush()

    # Create new game session
    new_gs = GameSession(
        id=str(uuid.uuid4()),
        conversation_id=conv.id,
        campaign_id=campaign_id,
        world_name=last_session.world_name,
        current_location_id=last_session.current_location_id,
        environment=last_session.environment,
        session_number=new_session_number,
        status="active",
    )
    db.add(new_gs)
    await db.flush()

    # Re-parent entities from old session to new session
    old_sid = last_session.id
    new_sid = new_gs.id

    await db.execute(
        update(Character)
        .where(Character.session_id == old_sid)
        .values(session_id=new_sid)
    )
    await db.execute(
        update(Location)
        .where(Location.session_id == old_sid)
        .values(session_id=new_sid)
    )
    await db.execute(
        update(NPC)
        .where(NPC.session_id == old_sid)
        .values(session_id=new_sid)
    )
    # Re-parent active + completed quests (failed quests stay with old session)
    await db.execute(
        update(Quest)
        .where(Quest.session_id == old_sid, Quest.status.in_(["active", "completed"]))
        .values(session_id=new_sid)
    )
    await db.execute(
        update(Relationship)
        .where(Relationship.session_id == old_sid)
        .values(session_id=new_sid)
    )
    # InventoryItems follow characters via character_id FK — no update needed
    # GameMemories stay with original session for historical search

    logger.info(
        "Continued campaign %s: session %d -> %d (conv %s)",
        campaign_id, last_session.session_number, new_session_number, conv.id,
    )

    return {
        "conversation_id": conv.id,
        "session_number": new_session_number,
        "world_name": new_gs.world_name,
        "campaign_id": campaign_id,
        "campaign_name": campaign.name,
    }


async def get_previous_summaries(
    db: AsyncSession,
    campaign_id: str,
    limit: int = 3,
) -> list[dict]:
    """Get summaries from previous sessions in a campaign (most recent first)."""
    result = await db.execute(
        select(GameSession)
        .where(
            GameSession.campaign_id == campaign_id,
            GameSession.status == "ended",
            GameSession.session_summary.isnot(None),
        )
        .order_by(GameSession.session_number.desc())
        .limit(limit)
    )
    sessions = result.scalars().all()
    return [
        {
            "session_number": s.session_number,
            "summary": s.session_summary,
        }
        for s in reversed(sessions)  # chronological order
    ]


async def get_campaign_session_numbers(
    db: AsyncSession,
    campaign_id: str,
) -> tuple[int, int] | None:
    """Get the (min, max) session numbers for a campaign. For cross-session memory search."""
    result = await db.execute(
        select(GameSession.session_number)
        .where(GameSession.campaign_id == campaign_id)
        .order_by(GameSession.session_number)
    )
    numbers = [r[0] for r in result.all()]
    if not numbers:
        return None
    return (numbers[0], numbers[-1])
