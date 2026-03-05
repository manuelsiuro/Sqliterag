"""Game memory management tools (Phase 10)."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rpg_service import get_or_create_session


async def archive_event(
    description: str,
    importance: int = 5,
    entity_names: str = "",
    memory_type: str = "episodic",
    *,
    session: AsyncSession,
    conversation_id: str,
    embedding_service=None,
) -> str:
    """Record a significant story event into long-term game memory."""
    from app.services import memory_service

    gs = await get_or_create_session(session, conversation_id)

    # Normalize importance 1-10 int -> 0.0-1.0 float
    importance = max(1, min(10, int(importance)))
    score = max(0.0, min(1.0, (importance - 1) / 9.0))

    # Parse comma-separated entity names
    entities = [n.strip() for n in entity_names.split(",") if n.strip()] if entity_names else []

    await memory_service.create_memory(
        session,
        session_id=gs.id,
        memory_type=memory_type,
        entity_type="event",
        content=description,
        entity_names=entities,
        importance_score=score,
        embedding_service=embedding_service,
    )

    return json.dumps({
        "type": "memory_archived",
        "description": description,
        "importance": importance,
        "entities": entities,
        "memory_type": memory_type,
    })


async def search_memory(
    query: str,
    memory_type: str = "",
    *,
    session: AsyncSession,
    conversation_id: str,
    embedding_service=None,
) -> str:
    """Search long-term game memory using hybrid retrieval."""
    from app.services import memory_service

    gs = await get_or_create_session(session, conversation_id)

    results = await memory_service.search_with_stanford_scoring(
        session,
        query,
        embedding_service=embedding_service,
        session_id=gs.id,
    )

    if not results:
        return json.dumps({
            "type": "memory_results",
            "query": query,
            "memories": [],
            "count": 0,
        })

    memory_ids = [mid for mid, _score in results]
    memories = await memory_service.get_memories_by_ids(session, memory_ids)

    # Filter by memory_type if specified
    if memory_type:
        memories = [m for m in memories if m.memory_type == memory_type]

    memory_list = []
    for m in memories:
        memory_list.append({
            "content": m.content,
            "importance": round((m.importance_score or 0.5) * 9 + 1),
            "memory_type": m.memory_type,
            "entities": json.loads(m.entity_names) if m.entity_names else [],
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })

    return json.dumps({
        "type": "memory_results",
        "query": query,
        "memories": memory_list,
        "count": len(memory_list),
    })


async def get_session_summary(
    session_number: int = 0,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Get a summary of all archived memories for the current game session."""
    from app.models.rpg import GameMemory

    gs = await get_or_create_session(session, conversation_id)

    result = await session.execute(
        select(GameMemory)
        .where(GameMemory.session_id == gs.id)
        .order_by(GameMemory.created_at.asc())
    )
    memories = result.scalars().all()

    events = []
    type_counts: dict[str, int] = {}
    for m in memories:
        type_counts[m.memory_type] = type_counts.get(m.memory_type, 0) + 1
        events.append({
            "content": m.content,
            "memory_type": m.memory_type,
            "importance": round((m.importance_score or 0.5) * 9 + 1),
            "entities": json.loads(m.entity_names) if m.entity_names else [],
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })

    # Build programmatic summary
    if events:
        first = events[0].get("created_at", "?")
        last = events[-1].get("created_at", "?")
        type_parts = ", ".join(f"{count} {t}" for t, count in type_counts.items())
        summary = f"{len(events)} memories ({type_parts}) from {first} to {last}"
    else:
        summary = "No memories recorded yet."

    return json.dumps({
        "type": "session_summary",
        "session_number": session_number,
        "events": events,
        "count": len(events),
        "summary": summary,
    })
