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

from sqlalchemy import delete, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.rpg import Character, GameMemory, Location, NPC, Quest, Relationship
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
    memory_types: list[str] | None = None,
    entity_types: list[str] | None = None,
    session_range: tuple[int, int] | None = None,
    k: int = 10,
) -> list[tuple[str, float]]:
    """FTS5 MATCH query returning (memory_id, score) pairs.

    Score is negated BM25 rank so higher = better match, consistent with
    RRF expectations.  Metadata filters are applied as SQL pre-filters via
    a JOIN with game_memories when any filter is active.
    """
    sanitized = _sanitize_fts_query(query)
    if not sanitized:
        return []

    try:
        where_parts = ["fts_memories MATCH :query"]
        params: dict = {"query": sanitized, "k": k}
        # When session_range is given, skip session_id filter (cross-session search)
        effective_session_id = session_id if not session_range else None
        needs_join = bool(effective_session_id or memory_types or entity_types or session_range)

        if effective_session_id:
            where_parts.append("g.session_id = :sid")
            params["sid"] = effective_session_id
        if memory_types:
            ph = ", ".join(f":mt{i}" for i in range(len(memory_types)))
            where_parts.append(f"g.memory_type IN ({ph})")
            for i, mt in enumerate(memory_types):
                params[f"mt{i}"] = mt
        if entity_types:
            ph = ", ".join(f":et{i}" for i in range(len(entity_types)))
            where_parts.append(f"g.entity_type IN ({ph})")
            for i, et in enumerate(entity_types):
                params[f"et{i}"] = et
        if session_range:
            where_parts.append("g.session_number >= :sn_min AND g.session_number <= :sn_max")
            params["sn_min"] = session_range[0]
            params["sn_max"] = session_range[1]

        where_clause = " AND ".join(where_parts)
        join_clause = "JOIN game_memories g ON g.id = f.memory_id " if needs_join else ""

        sql = (
            f"SELECT f.memory_id, -f.rank AS score "
            f"FROM fts_memories f {join_clause}"
            f"WHERE {where_clause} "
            f"ORDER BY f.rank LIMIT :k"
        )
        rows = (await session.execute(text(sql), params)).fetchall()
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
    memory_types: list[str] | None = None,
    entity_types: list[str] | None = None,
    session_range: tuple[int, int] | None = None,
    k: int = 20,
) -> list[tuple[str, int]]:
    """Vector similarity search returning (memory_id, rank_position) pairs.

    rank_position is 1-based (sorted by distance ascending = most similar first).
    When metadata filters are active, over-fetches from vec0 then filters during
    rowid resolution (sqlite-vec cannot pre-filter).
    """
    try:
        embedding = await embedding_service.generate_embedding(
            f"search_query: {query}"
        )
        vec_bytes = _serialize_float32(embedding)

        # Over-fetch when metadata filters are active
        # When session_range is given, skip session_id filter (cross-session search)
        has_filters = bool((session_id if not session_range else None) or memory_types or entity_types or session_range)
        vec_k = int(k * settings.memory_vec_overfetch_factor) if has_filters else k

        # sqlite-vec requires LIMIT directly on the vec0 query (no JOINs)
        vec_rows = (
            await session.execute(
                text(
                    "SELECT rowid, distance "
                    "FROM vec_memories "
                    "WHERE embedding MATCH :query "
                    "ORDER BY distance "
                    "LIMIT :k"
                ),
                {"query": vec_bytes, "k": vec_k},
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

        # Build unified filter query for metadata constraints
        mid_list = list(rowid_to_mid.values())
        if not mid_list:
            return []

        where_parts = ["id IN ({})".format(", ".join(f"'{m}'" for m in mid_list))]
        filter_params: dict = {}

        # When session_range is given, skip session_id filter (cross-session search)
        effective_session_id = session_id if not session_range else None
        if effective_session_id:
            where_parts.append("session_id = :sid")
            filter_params["sid"] = effective_session_id
        if memory_types:
            ph = ", ".join(f":mt{i}" for i in range(len(memory_types)))
            where_parts.append(f"memory_type IN ({ph})")
            for i, mt in enumerate(memory_types):
                filter_params[f"mt{i}"] = mt
        if entity_types:
            ph = ", ".join(f":et{i}" for i in range(len(entity_types)))
            where_parts.append(f"entity_type IN ({ph})")
            for i, et in enumerate(entity_types):
                filter_params[f"et{i}"] = et
        if session_range:
            where_parts.append("session_number >= :sn_min AND session_number <= :sn_max")
            filter_params["sn_min"] = session_range[0]
            filter_params["sn_max"] = session_range[1]

        where_clause = " AND ".join(where_parts)
        valid_mids = set(
            r[0] for r in (
                await session.execute(
                    text(f"SELECT id FROM game_memories WHERE {where_clause}"),
                    filter_params,
                )
            ).fetchall()
        )

        return [
            (rowid_to_mid[r[0]], rank + 1)
            for rank, r in enumerate(vec_rows)
            if r[0] in rowid_to_mid and rowid_to_mid[r[0]] in valid_mids
        ]
    except Exception:
        logger.warning("Vec search failed for query %r", query, exc_info=True)
        return []


async def search_hybrid(
    session: AsyncSession,
    query: str,
    *,
    embedding_service: BaseEmbeddingService | None = None,
    session_id: str | None = None,
    memory_types: list[str] | None = None,
    entity_types: list[str] | None = None,
    session_range: tuple[int, int] | None = None,
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

    filter_kw = dict(
        session_id=session_id,
        memory_types=memory_types,
        entity_types=entity_types,
        session_range=session_range,
    )

    # Run searches concurrently
    fts_task = search_fts(session, query, k=candidates_k, **filter_kw)

    if embedding_service is not None:
        vec_task = search_vec(
            session, query,
            embedding_service=embedding_service,
            k=candidates_k,
            **filter_kw,
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
    memory_types: list[str] | None = None,
    entity_types: list[str] | None = None,
    session_range: tuple[int, int] | None = None,
    top_k: int | None = None,
) -> list[tuple[str, float]]:
    """Stanford Generative Agents reranker on top of hybrid RRF candidates.

    Score = α_rel * relevance + α_rec * recency + α_imp * importance
    All components min-max normalized to [0,1].

    Falls back to plain search_hybrid() when stanford scoring is disabled.
    """
    filter_kw = dict(
        session_id=session_id,
        memory_types=memory_types,
        entity_types=entity_types,
        session_range=session_range,
    )

    if not settings.memory_stanford_scoring_enabled:
        return await search_hybrid(
            session, query,
            embedding_service=embedding_service,
            top_k=top_k,
            **filter_kw,
        )

    k = top_k or settings.memory_search_top_k

    # Step 1: Get RRF candidates (up to candidates_k)
    rrf_results = await search_hybrid(
        session, query,
        embedding_service=embedding_service,
        top_k=settings.memory_search_candidates_k,
        **filter_kw,
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


# ---------------------------------------------------------------------------
# GraphRAG integration (Phase 3.6)
# ---------------------------------------------------------------------------

async def _extract_entities_from_query(
    session: AsyncSession,
    game_session_id: str,
    query: str,
) -> list[tuple[str, str, str]]:
    """Find known entity names that appear in the query via word-boundary match.

    Returns list of (entity_type, entity_id, entity_name) tuples.
    """
    # Fetch all known entity names for the session in one pass
    entities: list[tuple[str, str, str]] = []

    char_rows = (await session.execute(
        select(Character.id, Character.name).where(Character.session_id == game_session_id)
    )).fetchall()
    for eid, name in char_rows:
        entities.append(("character", eid, name))

    npc_rows = (await session.execute(
        select(NPC.id, NPC.name).where(NPC.session_id == game_session_id)
    )).fetchall()
    for eid, name in npc_rows:
        entities.append(("npc", eid, name))

    loc_rows = (await session.execute(
        select(Location.id, Location.name).where(Location.session_id == game_session_id)
    )).fetchall()
    for eid, name in loc_rows:
        entities.append(("location", eid, name))

    quest_rows = (await session.execute(
        select(Quest.id, Quest.title).where(Quest.session_id == game_session_id)
    )).fetchall()
    for eid, title in quest_rows:
        entities.append(("quest", eid, title))

    # Word-boundary match against query
    matches = []
    for etype, eid, name in entities:
        if re.search(r"\b" + re.escape(name) + r"\b", query, re.IGNORECASE):
            matches.append((etype, eid, name))

    logger.info("GraphRAG: extracted %d entities from query: %s", len(matches), [m[2] for m in matches])
    return matches


async def _expand_entities_via_graph(
    session: AsyncSession,
    game_session_id: str,
    seeds: list[tuple[str, str, str]],
) -> list[str]:
    """Expand seed entities to their direct graph neighbors.

    Returns a list of neighbor display names (deduplicated against seeds),
    capped at graphrag_max_expansion_entities, sorted by strength descending.
    """
    min_strength = settings.graphrag_min_strength
    seed_keys = {(etype, eid) for etype, eid, _ in seeds}

    # Build OR conditions for both outgoing and incoming edges
    source_conds = [
        (Relationship.source_type == etype) & (Relationship.source_id == eid)
        for etype, eid, _ in seeds
    ]
    target_conds = [
        (Relationship.target_type == etype) & (Relationship.target_id == eid)
        for etype, eid, _ in seeds
    ]

    q = (
        select(Relationship)
        .where(
            Relationship.session_id == game_session_id,
            Relationship.strength >= min_strength,
            or_(*source_conds, *target_conds),
        )
        .order_by(Relationship.strength.desc())
    )
    result = await session.execute(q)
    rels = result.scalars().all()

    # Collect neighbor (type, id) pairs that are NOT in seed set
    neighbors: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str]] = set()
    for r in rels:
        # For each relationship, the "other" side is the neighbor
        for ntype, nid in [
            (r.source_type, r.source_id),
            (r.target_type, r.target_id),
        ]:
            key = (ntype, nid)
            if key not in seed_keys and key not in seen:
                seen.add(key)
                neighbors.append((ntype, nid, r.strength))

    # Cap at max expansion entities
    neighbors = neighbors[: settings.graphrag_max_expansion_entities]

    # Resolve IDs to display names
    from app.services.rpg_service import resolve_entity_name

    names = []
    for ntype, nid, _strength in neighbors:
        name = await resolve_entity_name(session, ntype, nid)
        names.append(name)

    logger.info("GraphRAG: expanded to %d neighbors: %s", len(names), names)
    return names


async def search_graphrag(
    session: AsyncSession,
    query: str,
    *,
    embedding_service: BaseEmbeddingService | None = None,
    session_id: str | None = None,
    game_session_id: str | None = None,
    memory_types: list[str] | None = None,
    entity_types: list[str] | None = None,
    session_range: tuple[int, int] | None = None,
    top_k: int | None = None,
) -> list[tuple[str, float]]:
    """GraphRAG-augmented memory search.

    Runs primary Stanford scoring search, then optionally expands via
    graph neighbors for structurally related memories.
    Falls back to plain search_with_stanford_scoring on any graph error.
    """
    filter_kw = dict(
        embedding_service=embedding_service,
        session_id=session_id,
        memory_types=memory_types,
        entity_types=entity_types,
        session_range=session_range,
        top_k=top_k,
    )

    # Step 1: Primary search — always runs
    primary = await search_with_stanford_scoring(session, query, **filter_kw)

    # Step 2: Graph expansion (optional)
    if not settings.graphrag_enabled or not game_session_id:
        return primary

    try:
        seeds = await _extract_entities_from_query(session, game_session_id, query)
        if not seeds:
            return primary

        expansion_names = await _expand_entities_via_graph(session, game_session_id, seeds)
        if not expansion_names:
            return primary

        # Build augmented query from expansion names
        augmented_query = " ".join(expansion_names)
        graph_results = await search_with_stanford_scoring(
            session, augmented_query, **filter_kw,
        )

        # Merge: primary keeps full scores, graph results weighted down
        weight = settings.graphrag_weight
        primary_ids = {mid for mid, _ in primary}
        merged: dict[str, float] = {mid: score for mid, score in primary}

        for mid, score in graph_results:
            if mid not in primary_ids:
                merged[mid] = score * weight

        k = top_k or settings.memory_search_top_k
        final = sorted(merged.items(), key=lambda x: x[1], reverse=True)[:k]

        logger.info(
            "GraphRAG: %d primary + %d graph -> %d merged",
            len(primary), len(graph_results), len(final),
        )
        return final

    except Exception:
        logger.warning("GraphRAG expansion failed, returning primary results", exc_info=True)
        return primary


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
