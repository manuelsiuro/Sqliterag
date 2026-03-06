"""Session recap generation — "Previously on..." narrative (Phase 5.5)."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.rpg import Campaign, Character, GameSession, Location, Quest

logger = logging.getLogger(__name__)


async def generate_session_recap(
    db: AsyncSession,
    game_session: GameSession,
    llm_service,
    model: str,
) -> str:
    """Generate a dramatic 'Previously on...' recap from prior campaign sessions.

    Uses previous session summaries + current party/location/quests as context.
    Returns the narrative text (not JSON).
    """
    from app.services import campaign_service

    summaries = await campaign_service.get_previous_summaries(
        db, game_session.campaign_id, limit=settings.campaign_recap_max_sessions,
    )

    # Gather current party
    result = await db.execute(
        select(Character)
        .where(Character.session_id == game_session.id, Character.is_player.is_(True))
        .order_by(Character.created_at)
        .limit(6)
    )
    characters = result.scalars().all()

    # Current location
    location_name = None
    if game_session.current_location_id:
        result = await db.execute(
            select(Location).where(Location.id == game_session.current_location_id)
        )
        loc = result.scalars().first()
        if loc:
            location_name = loc.name

    # Active quests
    result = await db.execute(
        select(Quest)
        .where(Quest.session_id == game_session.id, Quest.status == "active")
        .limit(3)
    )
    quests = result.scalars().all()

    # Campaign name
    campaign_name = game_session.world_name
    if game_session.campaign_id:
        camp_result = await db.execute(
            select(Campaign).where(Campaign.id == game_session.campaign_id)
        )
        camp = camp_result.scalars().first()
        if camp:
            campaign_name = camp.name

    # Build context for LLM
    parts: list[str] = [f"Campaign: {campaign_name}"]

    if summaries:
        for s in summaries:
            parts.append(f"Session {s['session_number']}: {s['summary']}")
    else:
        parts.append("(No previous session summaries available.)")

    if characters:
        names = ", ".join(
            f"{c.name} (L{c.level} {c.char_class})" for c in characters[:4]
        )
        parts.append(f"Current party: {names}")

    if location_name:
        parts.append(f"Current location: {location_name}")

    if quests:
        quest_list = ", ".join(q.title for q in quests)
        parts.append(f"Active quests: {quest_list}")

    context_text = "\n".join(parts)

    max_tokens = settings.session_recap_max_tokens
    response = await llm_service.chat(
        model,
        [
            {
                "role": "system",
                "content": (
                    "/nothink\n"
                    "You are narrating a dramatic 'Previously on...' recap for a D&D campaign. "
                    "Write in 2nd person, 150-200 words. Be vivid and theatrical, like the opening "
                    "of a fantasy TV episode. Reference key events, characters, and unresolved tensions."
                ),
            },
            {"role": "user", "content": context_text},
        ],
        think=False,
        options={"num_predict": max_tokens + 100},
    )
    narrative = (response.get("content") or "").strip()

    if not narrative:
        logger.warning("Recap LLM returned empty, using programmatic fallback")
        narrative = _programmatic_recap(campaign_name, summaries, characters)

    return narrative


def _programmatic_recap(
    campaign_name: str,
    summaries: list[dict],
    characters: list,
) -> str:
    parts = [f"Previously on {campaign_name}..."]
    for s in summaries:
        parts.append(f"In Session {s['session_number']}: {s['summary']}")
    if characters:
        names = ", ".join(c.name for c in characters[:4])
        parts.append(f"Your party ({names}) continues the adventure.")
    return " ".join(parts)
