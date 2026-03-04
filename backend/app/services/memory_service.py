"""Game memory CRUD with FTS5 + sqlite-vec sync and hybrid RRF search.

All writes to game_memories are mirrored to the fts_memories FTS5 virtual
table and (when an embedding_service is provided) to vec_memories + vec_memory_map
so that exact-keyword search (Phase 2.2) and hybrid RRF retrieval (Phase 2.3)
work correctly.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import struct
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.rpg import GameMemory
from app.services.base import BaseEmbeddingService

logger = logging.getLogger(__name__)


def _serialize_float32(vec: list[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


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
# FTS query sanitization (Step 3)
# ---------------------------------------------------------------------------

_FTS_OPERATORS = re.compile(r"\b(AND|OR|NOT|NEAR)\b", re.IGNORECASE)
_FTS_SPECIAL = re.compile(r'[*"()+\-^]')


def _sanitize_fts_query(query: str) -> str:
    """Escape FTS5 special characters and operators for safe MATCH queries.

    Each token is wrapped in double quotes for literal matching.
    """
    # Remove FTS5 special chars
    cleaned = _FTS_SPECIAL.sub(" ", query)
    # Remove operator keywords
    cleaned = _FTS_OPERATORS.sub(" ", cleaned)
    # Split into tokens and quote each one
    tokens = cleaned.split()
    if not tokens:
        return ""
    return " ".join(f'"{t}"' for t in tokens)


# ---------------------------------------------------------------------------
# Internal vec helpers (Step 4)
# ---------------------------------------------------------------------------

async def _vec_insert(
    session: AsyncSession,
    memory: GameMemory,
    embedding_service: BaseEmbeddingService,
) -> None:
    """Generate embedding and insert into vec_memory_map + vec_memories."""
    try:
        embedding = await embedding_service.generate_embedding(
            f"search_document: {memory.content}"
        )
        vec_bytes = _serialize_float32(embedding)

        # Insert mapping row and get the rowid
        await session.execute(
            text("INSERT INTO vec_memory_map(memory_id) VALUES (:mid)"),
            {"mid": memory.id},
        )
        row = (
            await session.execute(
                text("SELECT rowid FROM vec_memory_map WHERE memory_id = :mid"),
                {"mid": memory.id},
            )
        ).fetchone()
        if row is None:
            logger.warning("vec_memory_map insert returned no rowid for %s", memory.id)
            return
        rowid = row[0]

        await session.execute(
            text("INSERT INTO vec_memories(rowid, embedding) VALUES (:rowid, :emb)"),
            {"rowid": rowid, "emb": vec_bytes},
        )
    except Exception:
        logger.warning("Vec insert failed for memory %s", memory.id, exc_info=True)


async def _vec_delete(session: AsyncSession, memory_id: str) -> None:
    """Remove a memory from vec_memories + vec_memory_map."""
    try:
        row = (
            await session.execute(
                text("SELECT rowid FROM vec_memory_map WHERE memory_id = :mid"),
                {"mid": memory_id},
            )
        ).fetchone()
        if row is None:
            return
        rowid = row[0]
        await session.execute(
            text("DELETE FROM vec_memories WHERE rowid = :rid"),
            {"rid": rowid},
        )
        await session.execute(
            text("DELETE FROM vec_memory_map WHERE rowid = :rid"),
            {"rid": rowid},
        )
    except Exception:
        logger.warning("Vec delete failed for memory %s", memory_id, exc_info=True)


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
    embedding_service: BaseEmbeddingService | None = None,
) -> GameMemory:
    """Create a GameMemory row and sync to FTS5 (+ vec if embedding_service provided)."""
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
    await session.flush()  # ensure id is assigned before FTS/vec insert
    await _fts_insert(session, memory)
    if embedding_service is not None:
        await _vec_insert(session, memory, embedding_service)
    return memory


async def update_memory(
    session: AsyncSession,
    memory: GameMemory,
    *,
    content: str | None = None,
    entity_names: list[str] | None = None,
    importance_score: float | None = None,
    embedding_service: BaseEmbeddingService | None = None,
) -> GameMemory:
    """Update ORM fields and re-sync FTS (+ vec if content changed and embedding_service provided)."""
    content_changed = content is not None and content != memory.content

    if content is not None:
        memory.content = content
    if entity_names is not None:
        memory.entity_names = json.dumps(entity_names)
    if importance_score is not None:
        memory.importance_score = importance_score

    await _fts_delete(session, memory.id)
    await _fts_insert(session, memory)

    if content_changed and embedding_service is not None:
        await _vec_delete(session, memory.id)
        await _vec_insert(session, memory, embedding_service)

    return memory


async def delete_memory(session: AsyncSession, memory: GameMemory) -> None:
    """Delete a single memory from ORM, FTS, and vec."""
    await _fts_delete(session, memory.id)
    await _vec_delete(session, memory.id)
    await session.delete(memory)


async def delete_session_memories(session: AsyncSession, game_session_id: str) -> int:
    """Bulk delete all memories for a game session. Returns count deleted."""
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
        await _vec_delete(session, mid)

    result = await session.execute(
        delete(GameMemory).where(GameMemory.session_id == game_session_id)
    )
    return result.rowcount  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

async def search_fts(
    session: AsyncSession,
    query: str,
    *,
    session_id: str | None = None,
    k: int = 10,
) -> list[tuple[str, float]]:
    """FTS5 MATCH query returning (memory_id, score) pairs.

    Score is negated BM25 rank so higher = better match, consistent with
    RRF expectations.
    """
    sanitized = _sanitize_fts_query(query)
    if not sanitized:
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
                    {"query": sanitized, "sid": session_id, "k": k},
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
                    {"query": sanitized, "k": k},
                )
            ).fetchall()
        return [(row[0], float(row[1])) for row in rows]
    except Exception:
        logger.warning("FTS search failed for query %r", query, exc_info=True)
        return []


async def search_vec(
    session: AsyncSession,
    query: str,
    *,
    embedding_service: BaseEmbeddingService,
    session_id: str | None = None,
    k: int = 20,
) -> list[tuple[str, int]]:
    """Vector similarity search returning (memory_id, rank_position) pairs.

    rank_position is 1-based (sorted by distance ascending = most similar first).
    """
    try:
        embedding = await embedding_service.generate_embedding(
            f"search_query: {query}"
        )
        vec_bytes = _serialize_float32(embedding)

        # sqlite-vec requires LIMIT directly on the vec0 query (no JOINs)
        # So we query vec_memories first, then resolve memory_ids via vec_memory_map
        vec_rows = (
            await session.execute(
                text(
                    "SELECT rowid, distance "
                    "FROM vec_memories "
                    "WHERE embedding MATCH :query "
                    "ORDER BY distance "
                    "LIMIT :k"
                ),
                {"query": vec_bytes, "k": k},
            )
        ).fetchall()

        if not vec_rows:
            return []

        # Resolve rowids to memory_ids via mapping table
        rowid_list = [r[0] for r in vec_rows]
        placeholders = ", ".join(str(rid) for rid in rowid_list)
        map_rows = (
            await session.execute(
                text(
                    f"SELECT rowid, memory_id FROM vec_memory_map "
                    f"WHERE rowid IN ({placeholders})"
                )
            )
        ).fetchall()
        rowid_to_mid = {r[0]: r[1] for r in map_rows}

        if session_id:
            # Filter by session_id
            mid_list = list(rowid_to_mid.values())
            mid_placeholders = ", ".join(f"'{m}'" for m in mid_list)
            session_mids = set(
                r[0] for r in (
                    await session.execute(
                        text(
                            f"SELECT id FROM game_memories "
                            f"WHERE id IN ({mid_placeholders}) AND session_id = :sid"
                        ),
                        {"sid": session_id},
                    )
                ).fetchall()
            )
            rows = [
                (rowid_to_mid[r[0]], rank + 1)
                for rank, r in enumerate(vec_rows)
                if r[0] in rowid_to_mid and rowid_to_mid[r[0]] in session_mids
            ]
        else:
            rows = [
                (rowid_to_mid[r[0]], rank + 1)
                for rank, r in enumerate(vec_rows)
                if r[0] in rowid_to_mid
            ]

        return rows
    except Exception:
        logger.warning("Vec search failed for query %r", query, exc_info=True)
        return []


async def search_hybrid(
    session: AsyncSession,
    query: str,
    *,
    embedding_service: BaseEmbeddingService | None = None,
    session_id: str | None = None,
    top_k: int | None = None,
) -> list[tuple[str, float]]:
    """Hybrid RRF search combining FTS5 and vector similarity.

    Returns (memory_id, rrf_score) pairs sorted by score descending.
    Degrades gracefully: FTS-only if no embedding_service or vec fails,
    vec-only if FTS fails, empty if both fail.
    """
    if not query or not query.strip():
        return []

    k = top_k or settings.memory_search_top_k
    candidates_k = settings.memory_search_candidates_k
    rrf_k = settings.memory_rrf_k
    w_fts = settings.memory_weight_fts
    w_vec = settings.memory_weight_vec

    # Run searches concurrently
    fts_task = search_fts(session, query, session_id=session_id, k=candidates_k)

    if embedding_service is not None:
        vec_task = search_vec(
            session, query,
            embedding_service=embedding_service,
            session_id=session_id,
            k=candidates_k,
        )
        fts_results, vec_results = await asyncio.gather(fts_task, vec_task)
    else:
        fts_results = await fts_task
        vec_results = []

    # Build rank maps (1-based ranks)
    fts_ranks: dict[str, int] = {}
    for rank, (mid, _score) in enumerate(fts_results, start=1):
        fts_ranks[mid] = rank

    vec_ranks: dict[str, int] = {}
    for mid, rank in vec_results:
        vec_ranks[mid] = rank

    # Collect all candidate memory_ids
    all_ids = set(fts_ranks.keys()) | set(vec_ranks.keys())
    if not all_ids:
        return []

    # Compute RRF scores
    scored: list[tuple[str, float]] = []
    for mid in all_ids:
        score = 0.0
        if mid in fts_ranks:
            score += w_fts / (rrf_k + fts_ranks[mid])
        if mid in vec_ranks:
            score += w_vec / (rrf_k + vec_ranks[mid])
        scored.append((mid, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:k]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def get_memories_by_ids(
    session: AsyncSession, memory_ids: list[str]
) -> list[GameMemory]:
    """Fetch full GameMemory objects by ID list, preserving input order."""
    if not memory_ids:
        return []

    result = await session.execute(
        select(GameMemory).where(GameMemory.id.in_(memory_ids))
    )
    memories_map = {m.id: m for m in result.scalars().all()}
    return [memories_map[mid] for mid in memory_ids if mid in memories_map]


async def touch_memory(session: AsyncSession, memory: GameMemory) -> None:
    """Update last_accessed timestamp (for Phase 2.4 recency scoring)."""
    memory.last_accessed = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Stanford Generative Agents scoring (Phase 2.4)
# ---------------------------------------------------------------------------

def _compute_recency(memory: GameMemory, decay: float) -> float:
    """Exponential decay based on hours since last_accessed."""
    now = datetime.now(timezone.utc)
    last = memory.last_accessed or memory.created_at
    if last.tzinfo is None:
        from datetime import timezone as _tz
        last = last.replace(tzinfo=_tz.utc)
    hours = (now - last).total_seconds() / 3600.0
    return decay ** hours


def _min_max_normalize(values: list[float]) -> list[float]:
    """Normalize values to [0, 1] range. Returns all 1.0 if no spread."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return [1.0] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


async def search_with_stanford_scoring(
    session: AsyncSession,
    query: str,
    *,
    embedding_service: BaseEmbeddingService | None = None,
    session_id: str | None = None,
    top_k: int | None = None,
) -> list[tuple[str, float]]:
    """Stanford Generative Agents reranker on top of hybrid RRF candidates.

    Score = α_rel * relevance + α_rec * recency + α_imp * importance
    All components min-max normalized to [0,1].

    Falls back to plain search_hybrid() when stanford scoring is disabled.
    """
    if not settings.memory_stanford_scoring_enabled:
        return await search_hybrid(
            session, query,
            embedding_service=embedding_service,
            session_id=session_id,
            top_k=top_k,
        )

    k = top_k or settings.memory_search_top_k

    # Step 1: Get RRF candidates (up to candidates_k)
    rrf_results = await search_hybrid(
        session, query,
        embedding_service=embedding_service,
        session_id=session_id,
        top_k=settings.memory_search_candidates_k,
    )
    if not rrf_results:
        return []

    # Step 2: Fetch full GameMemory objects for scoring
    memory_ids = [mid for mid, _score in rrf_results]
    memories = await get_memories_by_ids(session, memory_ids)
    if not memories:
        return []

    mem_map = {m.id: m for m in memories}
    # Filter to only IDs we actually got back
    rrf_results = [(mid, score) for mid, score in rrf_results if mid in mem_map]

    # Step 3: Compute raw component scores
    decay = settings.memory_recency_decay
    raw_relevance = [score for _mid, score in rrf_results]
    raw_recency = [_compute_recency(mem_map[mid], decay) for mid, _score in rrf_results]
    raw_importance = [mem_map[mid].importance_score or 0.5 for mid, _score in rrf_results]

    # Step 4: Min-max normalize each component
    norm_relevance = _min_max_normalize(raw_relevance)
    norm_recency = _min_max_normalize(raw_recency)
    norm_importance = _min_max_normalize(raw_importance)

    # Step 5: Weighted combination
    α_rel = settings.memory_alpha_relevance
    α_rec = settings.memory_alpha_recency
    α_imp = settings.memory_alpha_importance

    scored: list[tuple[str, float]] = []
    for i, (mid, _rrf_score) in enumerate(rrf_results):
        final = (
            α_rel * norm_relevance[i]
            + α_rec * norm_recency[i]
            + α_imp * norm_importance[i]
        )
        scored.append((mid, final))

    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:k]

    # Step 6: Touch accessed memories (update last_accessed)
    for mid, _score in top:
        if mid in mem_map:
            await touch_memory(session, mem_map[mid])

    logger.info(
        "Stanford scoring: %d candidates → %d results (top score=%.4f)",
        len(rrf_results), len(top), top[0][1] if top else 0.0,
    )
    return top


async def rebuild_fts_index(session: AsyncSession) -> int:
    """Full reindex from game_memories -> fts_memories. Returns row count."""
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


async def rebuild_vec_index(
    session: AsyncSession,
    embedding_service: BaseEmbeddingService,
) -> int:
    """Full reindex from game_memories -> vec_memory_map + vec_memories.

    Generates embeddings for all existing game memories. One-time migration
    utility for memories created before Phase 2.3.
    """
    try:
        # Clear existing vec data
        await session.execute(text("DELETE FROM vec_memories"))
        await session.execute(text("DELETE FROM vec_memory_map"))

        result = await session.execute(
            select(GameMemory)
        )
        memories = result.scalars().all()

        count = 0
        for memory in memories:
            await _vec_insert(session, memory, embedding_service)
            count += 1

        logger.info("Rebuilt vec_memories index: %d rows", count)
        return count
    except Exception:
        logger.warning("Vec rebuild failed", exc_info=True)
        return 0
