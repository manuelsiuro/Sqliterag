"""Game memory management tools (Phase 10 + Phase 2.6 session summarization)."""

from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.rpg_service import get_or_create_session

logger = logging.getLogger(__name__)


def _memory_to_event(m) -> dict:
    """Convert a GameMemory row to a serializable event dict."""
    return {
        "content": m.content,
        "memory_type": m.memory_type,
        "importance": round((m.importance_score or 0.5) * 9 + 1),
        "entities": json.loads(m.entity_names) if m.entity_names else [],
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


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
    entity_type: str = "",
    session_range: str = "",
    *,
    session: AsyncSession,
    conversation_id: str,
    embedding_service=None,
) -> str:
    """Search long-term game memory using hybrid retrieval with metadata pre-filters."""
    from app.services import memory_service

    gs = await get_or_create_session(session, conversation_id)

    # Parse comma-separated strings into lists
    memory_types = [t.strip() for t in memory_type.split(",") if t.strip()] or None
    entity_types = [t.strip() for t in entity_type.split(",") if t.strip()] or None

    # Parse session range: "N" -> (N, N), "N-M" -> (N, M)
    parsed_range = None
    if session_range and session_range.strip():
        sr = session_range.strip()
        if "-" in sr:
            parts = sr.split("-", 1)
            try:
                parsed_range = (int(parts[0].strip()), int(parts[1].strip()))
            except ValueError:
                pass
        else:
            try:
                parsed_range = (int(sr), int(sr))
            except ValueError:
                pass

    results = await memory_service.search_with_stanford_scoring(
        session,
        query,
        embedding_service=embedding_service,
        session_id=gs.id,
        memory_types=memory_types,
        entity_types=entity_types,
        session_range=parsed_range,
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

    memory_list = [_memory_to_event(m) for m in memories]

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
    llm_service=None,
    embedding_service=None,
) -> str:
    """Get a narrative summary of the current game session."""
    from app.models.rpg import GameMemory

    gs = await get_or_create_session(session, conversation_id)

    # If cached narrative exists, return it directly
    if gs.session_summary:
        return json.dumps({
            "type": "session_summary",
            "session_number": gs.session_number,
            "events": [],
            "count": 0,
            "summary": gs.session_summary,
            "narrative": True,
        })

    result = await session.execute(
        select(GameMemory)
        .where(GameMemory.session_id == gs.id)
        .order_by(GameMemory.created_at.asc())
    )
    memories = result.scalars().all()

    events = [_memory_to_event(m) for m in memories]

    # Try LLM narrative generation on-demand
    if memories and llm_service is not None and settings.session_summary_enabled:
        try:
            from app.services.summarization_service import generate_session_summary

            logger.info("Generating LLM narrative for session %s (%d memories)", gs.id, len(memories))
            narrative = await generate_session_summary(
                session, gs, llm_service, settings.default_model,
            )
            if narrative:
                # Cache on the game session
                gs.session_summary = narrative
                await session.flush()
                logger.info("Narrative generated and cached (%d chars)", len(narrative))
                return json.dumps({
                    "type": "session_summary",
                    "session_number": gs.session_number,
                    "events": events,
                    "count": len(events),
                    "summary": narrative,
                    "narrative": True,
                })
            else:
                logger.warning("LLM narrative returned empty, falling back to programmatic summary")
        except Exception:
            logger.warning("LLM narrative generation failed", exc_info=True)
    elif not memories:
        logger.info("get_session_summary: no memories to summarize")
    elif llm_service is None:
        logger.info("get_session_summary: llm_service is None, using programmatic fallback")

    # Programmatic fallback
    type_counts: dict[str, int] = {}
    for m in memories:
        type_counts[m.memory_type] = type_counts.get(m.memory_type, 0) + 1

    if events:
        first = events[0].get("created_at", "?")
        last = events[-1].get("created_at", "?")
        type_parts = ", ".join(f"{count} {t}" for t, count in type_counts.items())
        summary = f"{len(events)} memories ({type_parts}) from {first} to {last}"
    else:
        summary = "No memories recorded yet."

    return json.dumps({
        "type": "session_summary",
        "session_number": gs.session_number,
        "events": events,
        "count": len(events),
        "summary": summary,
        "narrative": False,
    })


async def recall_context(
    query: str,
    *,
    session: AsyncSession,
    conversation_id: str,
    embedding_service=None,
) -> str:
    """Search recall storage for evicted conversation messages."""
    from app.services import memory_service

    gs = await get_or_create_session(session, conversation_id)

    results = await memory_service.search_with_stanford_scoring(
        session,
        query,
        embedding_service=embedding_service,
        session_id=gs.id,
        memory_types=["recall"],
    )

    if not results:
        return json.dumps({
            "type": "recall_results",
            "query": query,
            "memories": [],
            "count": 0,
            "message": "No recalled context found for that query.",
        })

    memory_ids = [mid for mid, _score in results]
    memories = await memory_service.get_memories_by_ids(session, memory_ids)

    memory_list = [_memory_to_event(m) for m in memories]

    return json.dumps({
        "type": "recall_results",
        "query": query,
        "memories": memory_list,
        "count": len(memory_list),
    })


async def end_session(
    summary_override: str = "",
    *,
    session: AsyncSession,
    conversation_id: str,
    llm_service=None,
    embedding_service=None,
) -> str:
    """End the current game session with a narrative summary."""
    from app.services import memory_service

    gs = await get_or_create_session(session, conversation_id)

    if gs.status == "ended":
        return json.dumps({
            "type": "session_ended",
            "error": "Session has already been ended.",
        })

    # Generate summary
    summary_text = ""
    if summary_override:
        summary_text = summary_override
    elif llm_service is not None and settings.session_summary_enabled:
        try:
            from app.services.summarization_service import generate_session_summary

            logger.info("end_session: generating LLM narrative for session %s", gs.id)
            summary_text = await generate_session_summary(
                session, gs, llm_service, settings.default_model,
            )
            logger.info("end_session: narrative generated (%d chars)", len(summary_text))
        except Exception:
            logger.warning("end_session: LLM narrative generation failed", exc_info=True)
    elif llm_service is None:
        logger.info("end_session: llm_service is None, using programmatic fallback")

    if not summary_text:
        # Programmatic fallback
        from app.models.rpg import GameMemory
        result = await session.execute(
            select(GameMemory)
            .where(GameMemory.session_id == gs.id)
            .order_by(GameMemory.created_at.asc())
        )
        memories = result.scalars().all()
        if memories:
            summary_text = f"Session ended with {len(memories)} recorded events in {gs.world_name}."
        else:
            summary_text = f"Session ended in {gs.world_name}. No events were recorded."

    # Update session state
    gs.status = "ended"
    gs.session_summary = summary_text
    await session.flush()

    # Archive summary as a searchable GameMemory
    await memory_service.create_memory(
        session,
        session_id=gs.id,
        memory_type="summary",
        entity_type="session_summary",
        content=summary_text,
        entity_names=[gs.world_name],
        importance_score=0.9,
        embedding_service=embedding_service,
    )

    return json.dumps({
        "type": "session_ended",
        "session_number": gs.session_number,
        "world_name": gs.world_name,
        "summary": summary_text,
        "status": "ended",
    })
