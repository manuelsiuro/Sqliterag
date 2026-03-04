"""Game memory CRUD with FTS5 sync.

All writes to game_memories are mirrored to the fts_memories FTS5 virtual
table so that exact-keyword search (Phase 2.2) and hybrid RRF retrieval
(Phase 2.3) work correctly.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rpg import GameMemory

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal FTS helpers
# ---------------------------------------------------------------------------

async def _fts_insert(session: AsyncSession, memory: GameMemory) -> None:
    """Insert a row into fts_memories mirroring the given GameMemory."""
    try:
        entity_names_str = _entity_names_to_text(memory.entity_names)
        await session.execute(
            text(
                "INSERT INTO fts_memories(content, entity_names, memory_id) "
                "VALUES (:content, :entity_names, :memory_id)"
            ),
            {
                "content": memory.content,
                "entity_names": entity_names_str,
                "memory_id": memory.id,
            },
        )
    except Exception:
        logger.warning("FTS insert failed for memory %s", memory.id, exc_info=True)


async def _fts_delete(session: AsyncSession, memory_id: str) -> None:
    """Delete a row from fts_memories by memory_id."""
    try:
        await session.execute(
            text("DELETE FROM fts_memories WHERE memory_id = :mid"),
            {"mid": memory_id},
        )
    except Exception:
        logger.warning("FTS delete failed for memory %s", memory_id, exc_info=True)


def _entity_names_to_text(entity_names_json: str) -> str:
    """Convert a JSON array of entity names to a space-separated string for FTS5."""
    try:
        names = json.loads(entity_names_json) if entity_names_json else []
    except (json.JSONDecodeError, TypeError):
        names = []
    return " ".join(str(n) for n in names) if names else ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def create_memory(
    session: AsyncSession,
    *,
    session_id: str,
    memory_type: str,
    content: str,
    entity_names: list[str] | None = None,
    entity_type: str | None = None,
    importance_score: float = 0.5,
    session_number: int | None = None,
) -> GameMemory:
    """Create a GameMemory row and sync to FTS5."""
    memory = GameMemory(
        id=str(uuid.uuid4()),
        session_id=session_id,
        memory_type=memory_type,
        content=content,
        entity_names=json.dumps(entity_names or []),
        entity_type=entity_type,
        importance_score=importance_score,
        session_number=session_number,
    )
    session.add(memory)
    await session.flush()  # ensure id is assigned before FTS insert
    await _fts_insert(session, memory)
    return memory


async def update_memory(
    session: AsyncSession,
    memory: GameMemory,
    *,
    content: str | None = None,
    entity_names: list[str] | None = None,
    importance_score: float | None = None,
) -> GameMemory:
    """Update ORM fields and re-sync FTS (delete old + insert new)."""
    if content is not None:
        memory.content = content
    if entity_names is not None:
        memory.entity_names = json.dumps(entity_names)
    if importance_score is not None:
        memory.importance_score = importance_score

    await _fts_delete(session, memory.id)
    await _fts_insert(session, memory)
    return memory


async def delete_memory(session: AsyncSession, memory: GameMemory) -> None:
    """Delete a single memory from both ORM and FTS."""
    await _fts_delete(session, memory.id)
    await session.delete(memory)


async def delete_session_memories(session: AsyncSession, game_session_id: str) -> int:
    """Bulk delete all memories for a game session. Returns count deleted."""
    # Gather ids first for FTS cleanup
    rows = (
        await session.execute(
            text("SELECT id FROM game_memories WHERE session_id = :sid"),
            {"sid": game_session_id},
        )
    ).fetchall()

    if not rows:
        return 0

    for (mid,) in rows:
        await _fts_delete(session, mid)

    result = await session.execute(
        delete(GameMemory).where(GameMemory.session_id == game_session_id)
    )
    return result.rowcount  # type: ignore[return-value]


async def search_fts(
    session: AsyncSession,
    query: str,
    *,
    session_id: str | None = None,
    k: int = 10,
) -> list[tuple[str, float]]:
    """FTS5 MATCH query returning (memory_id, score) pairs.

    Score is negated BM25 rank so higher = better match, consistent with
    Phase 2.3 RRF expectations.
    """
    if not query or not query.strip():
        return []

    try:
        if session_id:
            rows = (
                await session.execute(
                    text(
                        "SELECT f.memory_id, -f.rank AS score "
                        "FROM fts_memories f "
                        "JOIN game_memories g ON g.id = f.memory_id "
                        "WHERE fts_memories MATCH :query AND g.session_id = :sid "
                        "ORDER BY f.rank "
                        "LIMIT :k"
                    ),
                    {"query": query, "sid": session_id, "k": k},
                )
            ).fetchall()
        else:
            rows = (
                await session.execute(
                    text(
                        "SELECT f.memory_id, -f.rank AS score "
                        "FROM fts_memories f "
                        "WHERE fts_memories MATCH :query "
                        "ORDER BY f.rank "
                        "LIMIT :k"
                    ),
                    {"query": query, "k": k},
                )
            ).fetchall()
        return [(row[0], float(row[1])) for row in rows]
    except Exception:
        logger.warning("FTS search failed for query %r", query, exc_info=True)
        return []


async def touch_memory(session: AsyncSession, memory: GameMemory) -> None:
    """Update last_accessed timestamp (for Phase 2.4 recency scoring)."""
    memory.last_accessed = datetime.now(timezone.utc)


async def rebuild_fts_index(session: AsyncSession) -> int:
    """Full reindex from game_memories → fts_memories. Returns row count."""
    try:
        await session.execute(text("DELETE FROM fts_memories"))
        await session.execute(
            text(
                "INSERT INTO fts_memories(content, entity_names, memory_id) "
                "SELECT content, entity_names, id FROM game_memories"
            )
        )
        count = (
            await session.execute(text("SELECT COUNT(*) FROM fts_memories"))
        ).scalar() or 0
        logger.info("Rebuilt fts_memories index: %d rows", count)
        return count
    except Exception:
        logger.warning("FTS rebuild failed", exc_info=True)
        return 0
