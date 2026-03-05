# Phase 2.4: Stanford Retrieval Scoring — Implementation Plan

> **Status**: Phase 2.1-2.3 complete. This plan covers Phase 2.4 only.
> **Estimated changes**: ~90 new lines across 3 files. Zero DB migrations. Zero frontend changes.

---

## Context

The game memory system (Phase 2.1-2.3) stores episodic/semantic/procedural memories with hybrid RRF search (FTS5 + sqlite-vec). However, all memories are ranked purely by text relevance — a memory from 5 sessions ago scores the same as one from 2 minutes ago. The Stanford Generative Agents paper (Park et al., 2023) showed that combining **recency**, **importance**, and **relevance** produces dramatically better memory retrieval for interactive agents.

The `GameMemory` model already has `importance_score`, `last_accessed`, and `created_at` fields, plus a `touch_memory()` helper — all unused. This phase activates them.

---

## Architecture: POST-RRF Reranker

**Approach**: Add a reranking layer on top of existing RRF, not replace it.

```
User query
    │
    ▼
search_hybrid() → 20 candidates (RRF score = relevance proxy)
    │
    ▼
search_with_stanford_scoring() → rerank with recency + importance + relevance
    │
    ▼
Top 5 returned → injected into chat context
```

**Why rerank, not replace**: RRF already fuses keyword + semantic relevance well. Recency and importance are memory-level properties (not query-match properties). Keeping them separate preserves the working search pipeline and adds zero risk of regression.

---

## Implementation Steps

### Step 1: Add config settings — `backend/app/config.py`

Insert after line 64 (after existing `memory_search_candidates_k`):

```python
# Stanford retrieval scoring (Phase 2.4)
memory_stanford_scoring_enabled: bool = True
memory_alpha_recency: float = 1.0
memory_alpha_importance: float = 1.0
memory_alpha_relevance: float = 1.0
memory_recency_decay: float = 0.995  # per real-world hour
```

**Notes**:
- `0.995^24` (1 day) = 0.89, `0.995^168` (1 week) = 0.43, `0.995^720` (1 month) = 0.03
- Alpha weights all start at 1.0 — equal weighting, tunable later
- Feature flag allows disabling without code changes

---

### Step 2: Add Stanford scoring functions — `backend/app/services/memory_service.py`

Insert after `search_hybrid()` (line 455), before the Helpers section (line 458).

**Three new functions**:

1. `_compute_recency(memory, now, decay) -> float` — exponential decay from `last_accessed`
2. `_min_max_normalize(values) -> list[float]` — normalize to [0,1], handle uniform edge case
3. `search_with_stanford_scoring(session, query, ...) -> list[tuple[str, float]]` — main entry point

**`search_with_stanford_scoring` logic**:
1. If Stanford disabled → delegate to `search_hybrid()` directly
2. Get 20 RRF candidates via `search_hybrid(top_k=candidates_k)`
3. Fetch full `GameMemory` objects for those candidates
4. Compute raw recency (exponential decay), importance (from field), relevance (RRF score)
5. Min-max normalize each dimension to [0, 1]
6. Weighted sum: `α_rel * relevance + α_rec * recency + α_imp * importance`
7. Sort descending, return top_k
8. Call `touch_memory()` on returned memories (updates `last_accessed`)
9. Wrapped in try/except — falls back to plain `search_hybrid()` on any error

**Signature matches `search_hybrid()` exactly** — drop-in replacement at call site.

---

### Step 3: Update chat_service.py call site — `backend/app/services/chat_service.py`

Lines 215 and 218 — change import and function call:

**Before** (line 215):
```python
from app.services.memory_service import search_hybrid, get_memories_by_ids
```

**After**:
```python
from app.services.memory_service import search_with_stanford_scoring, get_memories_by_ids
```

**Before** (line 218):
```python
memory_results = await search_hybrid(
```

**After**:
```python
memory_results = await search_with_stanford_scoring(
```

No other changes needed — same arguments, same return type.

---

## Files Modified

| File | Change | Lines |
|------|--------|-------|
| `backend/app/config.py` | Add 6 config settings | +6 lines after line 64 |
| `backend/app/services/memory_service.py` | Add 3 functions (scoring + helpers) | +~80 lines after line 455 |
| `backend/app/services/chat_service.py` | Change import + function name | 2 lines changed |

## Files NOT Modified

- `backend/app/models/rpg.py` — fields already exist
- `backend/app/database.py` — no schema changes
- No Alembic migration needed
- No frontend changes

---

## Verification Plan

### 1. Backend startup check
```bash
cd backend && uvicorn app.main:app --reload
```
Confirm no import errors or startup crashes.

### 2. Chrome MCP end-to-end test
1. Navigate to app, select/create a D&D conversation
2. Play a few turns to generate game memories (create character, explore, talk to NPC)
3. Send a query referencing earlier events
4. Verify memories are injected in chat context (check backend logs for "Injected N game memories" and "Stanford rerank" debug line)
5. Send another query — verify `last_accessed` timestamps are updating (recently accessed memories should score higher on subsequent retrievals)

### 3. Fallback test
- Set `MEMORY_STANFORD_SCORING_ENABLED=false` in env
- Verify plain RRF search still works unchanged

### 4. Log verification
- Check for `Stanford rerank: N candidates -> M results` in debug logs
- Confirm no warnings about Stanford scoring failures
