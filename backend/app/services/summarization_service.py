"""Session summarization service — LLM-based narrative summaries (Phase 2.6)."""

from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.rpg import Character, GameMemory, GameSession, Quest

logger = logging.getLogger(__name__)


async def generate_session_summary(
    db: AsyncSession,
    game_session: GameSession,
    llm_service,
    model: str,
) -> str:
    """Generate an LLM narrative summary from game memories + state.

    Gathers all GameMemory records for the session plus current characters
    and quests, builds a prompt, and calls llm_service.chat().
    """
    # Gather memories
    result = await db.execute(
        select(GameMemory)
        .where(GameMemory.session_id == game_session.id)
        .order_by(GameMemory.created_at.asc())
    )
    memories = result.scalars().all()

    # Gather characters
    result = await db.execute(
        select(Character)
        .where(Character.session_id == game_session.id)
        .order_by(Character.created_at)
        .limit(6)
    )
    characters = result.scalars().all()

    # Gather active quests
    result = await db.execute(
        select(Quest)
        .where(Quest.session_id == game_session.id, Quest.status == "active")
        .limit(5)
    )
    quests = result.scalars().all()

    # Build context
    parts: list[str] = []

    parts.append(f"World: {game_session.world_name}")

    if characters:
        char_lines = []
        for c in characters:
            char_lines.append(f"- {c.name}, Level {c.level} {c.race} {c.char_class} (HP: {c.current_hp}/{c.max_hp})")
        parts.append("Characters:\n" + "\n".join(char_lines))

    if quests:
        quest_lines = [f"- {q.title}: {q.description[:80]}" for q in quests]
        parts.append("Active Quests:\n" + "\n".join(quest_lines))

    if memories:
        mem_lines = []
        for m in memories:
            entities = json.loads(m.entity_names) if m.entity_names else []
            entity_str = f" (involving {', '.join(entities)})" if entities else ""
            mem_lines.append(f"- [{m.memory_type}] {m.content}{entity_str}")
        parts.append("Session Events:\n" + "\n".join(mem_lines))
    else:
        parts.append("Session Events: No events recorded.")

    context_text = "\n\n".join(parts)

    max_tokens = settings.session_summary_max_tokens
    prompt = (
        "Write a 2-4 sentence narrative summary in past tense, third person. "
        "Focus on key story beats, character actions, discoveries, combat outcomes, and quest progress. "
        f"Keep it under {max_tokens * 4} characters.\n\n"
        f"{context_text}"
    )

    response = await llm_service.chat(
        model,
        [
            {"role": "system", "content": "/nothink\nYou are summarizing a D&D game session. Write a narrative summary of what happened. Be concise."},
            {"role": "user", "content": prompt},
        ],
        think=False,
        options={"num_predict": max_tokens + 100},
    )
    narrative = (response.get("content") or "").strip()
    if not narrative:
        logger.warning("LLM returned empty narrative (response keys: %s, content=%r)", list(response.keys()), response.get("content"))
    return narrative
