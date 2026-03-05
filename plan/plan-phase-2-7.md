# Phase 2.7: Metadata-Enhanced Retrieval

## Context

Phases 2.1-2.6 built the full game memory pipeline: `GameMemory` model with `memory_type`, `entity_type`, `session_number`, `entity_names`, and `importance_score`; FTS5 full-text search; sqlite-vec vector similarity; hybrid RRF fusion; Stanford Generative Agents reranking; and session summarization with LLM narratives.

However, all metadata filtering is currently **post-retrieval**. The `search_memory` tool (`builtin_tools/memory.py` lines 101-103) fetches top-k results from `search_with_stanford_scoring()` and then filters by `memory_type` in Python. This means if 20 candidates are retrieved and only 3 match a desired `memory_type`, the effective result set is diluted — the user gets fewer than `top_k` results, and high-quality matches pushed out of the candidate pool are permanently lost.

Phase 2.7 pushes metadata constraints into the SQL queries themselves (**pre-filtering**) so all `candidates_k` results already satisfy the criteria, and the full `top_k` is drawn from a properly filtered pool.

Additionally, the automatic RAG injection in `chat_service.py` (lines 211-240) uses no metadata filters at all. Phase-aware filtering (e.g., preferring `episodic` memories for narrative, `procedural` for combat rules) will improve injection quality.

## Design Decisions

- **Pre-filter, not post-filter**: Metadata constraints applied at the SQL level in both `search_fts()` and `search_vec()`. When no filters are provided, behavior is identical to Phase 2.6 (backward compatible).
- **Over-fetch for vec search**: sqlite-vec `vec0` cannot pre-filter (no WHERE/JOIN support). We over-fetch from `vec_memories` (`candidates_k * overfetch_factor`) when metadata filters are active, then apply filters during the rowid-to-memory resolution step. This is the same pattern already used for `session_id` filtering (lines 359-378).
- **List-based filter params**: `memory_types` and `entity_types` are `list[str] | None` internally to support multi-value filtering (e.g., `["episodic", "semantic"]`). The LLM-facing tool accepts comma-separated strings.
- **Session range as tuple**: `(min, max)` internally. LLM sends `"N"` (single session) or `"N-M"` (range). Parsing in the tool function.
- **Phase-to-memory-type mapping for auto-injection**: Small dict mapping `GamePhase` to preferred `memory_types`. Toggled via `memory_prefilter_enabled` config.
- **No frontend changes**: The `memory_results` JSON shape is unchanged. Improvements are purely backend retrieval quality.

## Changes Overview

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/config.py` | Modify | Add `memory_prefilter_enabled`, `memory_vec_overfetch_factor` |
| `backend/app/database.py` | Modify | Add 3 indexes on `game_memories`; update `search_memory` tool definition |
| `backend/app/services/memory_service.py` | Modify | Add `memory_types`, `entity_types`, `session_range` to all 4 search functions |
| `backend/app/services/builtin_tools/memory.py` | Modify | Add `entity_type`, `session_range` params; remove post-filter hack |
| `backend/app/services/chat_service.py` | Modify | Phase-aware `memory_types` in auto-injection |

## Step 1: Add config settings

**File**: `backend/app/config.py` (after line 75, after the Stanford scoring block)

```python
# Metadata-enhanced retrieval (Phase 2.7)
memory_prefilter_enabled: bool = True
memory_vec_overfetch_factor: float = 2.0  # Over-fetch multiplier for vec when filters active
```

## Step 2: Add database indexes + update tool definition

**File**: `backend/app/database.py`

### 2a: Indexes (after FTS5 creation at line 117, before line 119)

```python
# Indexes for metadata-enhanced retrieval (Phase 2.7)
for idx_name, idx_col in [
    ("idx_game_memories_memory_type", "memory_type"),
    ("idx_game_memories_entity_type", "entity_type"),
    ("idx_game_memories_session_number", "session_number"),
]:
    try:
        await conn.execute(text(
            f"CREATE INDEX IF NOT EXISTS {idx_name} ON game_memories({idx_col})"
        ))
    except Exception:
        pass
```

### 2b: Update `search_memory` tool def (lines 656-664)

Replace `parameters_schema` to include new params:

```python
"search_memory": {
    "description": "Search long-term game memory for past events, facts, or knowledge. Supports filtering by memory type, entity type, and session range.",
    "parameters_schema": _schema(["query"], {
        "query": {"type": "string", "description": "Search query describing what to recall."},
        "memory_type": {"type": "string", "description": "Filter by memory type: episodic, semantic, procedural, summary. Comma-separated for multiple. Empty for all."},
        "entity_type": {"type": "string", "description": "Filter by entity type: character, location, npc, quest, item, event. Comma-separated for multiple. Empty for all."},
        "session_range": {"type": "string", "description": "Filter by session number: 'N' for single session, 'N-M' for range. Empty for all."},
    }),
    "execution_type": "builtin",
    "execution_config": _config("search_memory"),
},
```

## Step 3: Extend `search_fts()` with metadata pre-filters

**File**: `backend/app/services/memory_service.py` (lines 260-307)

New signature:
```python
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
```

Replace the current two-branch if/else with a single dynamic query builder:

```python
sanitized = _sanitize_fts_query(query)
if not sanitized:
    return []

try:
    where_parts = ["fts_memories MATCH :query"]
    params: dict = {"query": sanitized, "k": k}
    needs_join = bool(session_id or memory_types or entity_types or session_range)

    if session_id:
        where_parts.append("g.session_id = :sid")
        params["sid"] = session_id
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
```

## Step 4: Extend `search_vec()` with metadata pre-filters

**File**: `backend/app/services/memory_service.py` (lines 310-389)

New signature:
```python
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
```

Key changes:
1. **Over-fetch when filters active** — replace `k` with `vec_k`:
   ```python
   has_filters = bool(session_id or memory_types or entity_types or session_range)
   vec_k = int(k * settings.memory_vec_overfetch_factor) if has_filters else k
   ```
   Use `vec_k` in the sqlite-vec MATCH query (line 337).

2. **Unified filter query** — replace the current two-branch session_id logic (lines 359-384) with a single dynamic WHERE builder:
   ```python
   mid_list = list(rowid_to_mid.values())
   if not mid_list:
       return []

   where_parts = ["id IN ({})".format(", ".join(f"'{m}'" for m in mid_list))]
   params: dict = {}

   if session_id:
       where_parts.append("session_id = :sid")
       params["sid"] = session_id
   if memory_types:
       ph = ", ".join(f":mt{i}" for i in range(len(memory_types)))
       where_parts.append(f"memory_type IN ({ph})")
       for i, mt in enumerate(memory_types):
           params[f"mt{i}"] = mt
   if entity_types:
       ph = ", ".join(f":et{i}" for i in range(len(entity_types)))
       where_parts.append(f"entity_type IN ({ph})")
       for i, et in enumerate(entity_types):
           params[f"et{i}"] = et
   if session_range:
       where_parts.append("session_number >= :sn_min AND session_number <= :sn_max")
       params["sn_min"] = session_range[0]
       params["sn_max"] = session_range[1]

   where_clause = " AND ".join(where_parts)
   valid_mids = set(
       r[0] for r in (
           await session.execute(
               text(f"SELECT id FROM game_memories WHERE {where_clause}"),
               params,
           )
       ).fetchall()
   )

   return [
       (rowid_to_mid[r[0]], rank + 1)
       for rank, r in enumerate(vec_rows)
       if r[0] in rowid_to_mid and rowid_to_mid[r[0]] in valid_mids
   ]
   ```

## Step 5: Thread filters through `search_hybrid()`

**File**: `backend/app/services/memory_service.py` (lines 392-455)

New signature adds `memory_types`, `entity_types`, `session_range`. Pass them to both `search_fts()` (line 416) and `search_vec()` (lines 419-424). No changes to the RRF fusion logic itself.

## Step 6: Thread filters through `search_with_stanford_scoring()`

**File**: `backend/app/services/memory_service.py` (lines 506-588)

New signature adds `memory_types`, `entity_types`, `session_range`. Pass them to both `search_hybrid()` calls (line 523 disabled fallback, line 532 main path). No changes to the Stanford scoring math.

## Step 7: Update `search_memory` tool

**File**: `backend/app/services/builtin_tools/memory.py` (lines 70-112)

New signature:
```python
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
```

Add parsing logic before the search call:
```python
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
```

Pass as pre-filters to `search_with_stanford_scoring()`:
```python
results = await memory_service.search_with_stanford_scoring(
    session, query,
    embedding_service=embedding_service,
    session_id=gs.id,
    memory_types=memory_types,
    entity_types=entity_types,
    session_range=parsed_range,
)
```

**Remove** the post-filter hack (old lines 101-103):
```python
# REMOVED: if memory_type:
# REMOVED:     memories = [m for m in memories if m.memory_type == memory_type]
```

## Step 8: Phase-aware auto-injection in `chat_service.py`

**File**: `backend/app/services/chat_service.py`

Add module-level mapping (after line 32, after the `prompt_builder` imports):

```python
from app.services.prompt_builder import GamePhase

# Phase-aware memory type preferences for auto-injection (Phase 2.7)
_PHASE_MEMORY_TYPES: dict[GamePhase, list[str]] = {
    GamePhase.COMBAT: ["episodic", "procedural"],
    GamePhase.SOCIAL: ["episodic", "semantic"],
    GamePhase.EXPLORATION: ["episodic", "semantic"],
}
```

Note: `GamePhase` is defined in `prompt_builder.py` — verify it's importable from the existing import block (line 27-32). Add `GamePhase` to the import list.

Modify the auto-injection call (lines 218-222):

```python
preferred_types = None
if settings.memory_prefilter_enabled and phase is not None:
    preferred_types = _PHASE_MEMORY_TYPES.get(phase)

memory_results = await search_with_stanford_scoring(
    session, user_message,
    embedding_service=self.embedding_service,
    session_id=game_session.id,
    memory_types=preferred_types,
)
```

When `memory_prefilter_enabled=False` or phase not in the mapping, `preferred_types=None` — no filter, fully backward compatible.

## Implementation Order

1. `backend/app/config.py` — Settings (unblocks everything)
2. `backend/app/database.py` — Indexes + tool def (unblocks startup)
3. `backend/app/services/memory_service.py` — Core: extend all 4 search functions (Steps 3-6)
4. `backend/app/services/builtin_tools/memory.py` — Tool params + remove post-filter (Step 7)
5. `backend/app/services/chat_service.py` — Phase-aware auto-injection (Step 8)

Steps 1-2 are independent. Step 3 is the critical core. Steps 4-5 depend on Step 3.

## Verification

### Startup
1. Restart backend — confirm no errors, indexes created silently
2. Confirm tool count remains 45 (no new tools, just updated `search_memory` schema)

### Backward Compatibility
3. Call `search_memory` with only `query` (no filters) — verify identical results to Phase 2.6
4. Verify automatic RAG injection works with `memory_prefilter_enabled=False`

### Pre-filter Functionality (Chrome MCP)
5. Start game session, `archive_event` with different `memory_type` values (`episodic`, `semantic`)
6. `search_memory` with `memory_type="episodic"` — only episodic returned
7. `search_memory` with `memory_type="episodic,semantic"` — both types returned
8. `search_memory` with `entity_type="character"` — only character-entity memories
9. `search_memory` with `session_range="1"` — only session 1 memories
10. `search_memory` with filters matching zero memories — clean empty result, no errors

### Phase-Aware Auto-Injection
11. Start combat, send message — backend logs show injected memories favor `episodic`+`procedural`
12. Social interaction (talk_to_npc) — logs show `episodic`+`semantic` preference

### Edge Cases
13. `session_range="abc"` (invalid) — graceful fallback, no filter applied
14. `entity_type="nonexistent"` — empty results, no crash
