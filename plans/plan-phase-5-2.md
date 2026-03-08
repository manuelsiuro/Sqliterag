# Phase 5.2: Matryoshka Embedding Optimization

> **Status**: Ready for implementation
> **Priority**: P2 | **Complexity**: Low | **Dependency**: Phase 2.1 (complete)
> **Goal**: Switch from 768-dim to 256-dim embeddings for 3x storage savings and faster vector search

---

## Context

`nomic-embed-text` supports Matryoshka Representation Learning (MRL) — the first 256 dimensions of a 768-dim embedding form a valid 256-dim embedding. Truncating client-side yields:
- **3x storage reduction**: 1,024 bytes/embedding (256x4) vs 3,072 bytes (768x4)
- **Faster cosine distance**: sqlite-vec computes distance over fewer dimensions
- **Minimal quality loss**: 62.28 -> 61.04 MTEB score (-1.24 points)

Currently two vec0 virtual tables (`vec_chunks`, `vec_memories`) are hardcoded to `float[768]`. The Ollama `/api/embed` endpoint returns full 768-dim vectors — truncation must happen client-side.

---

## Files to Modify

| # | File | Lines | Change |
|---|------|-------|--------|
| 1 | `backend/app/config.py` | 28 | Add `embedding_dimensions: int = 256` |
| 2 | `backend/.env.example` | 12 | Add `EMBEDDING_DIMENSIONS=256` |
| 3 | `backend/app/services/ollama_service.py` | 86 | Truncate embeddings to configured dim |
| 4 | `backend/app/database.py` | 56-262 | Dimension-aware tables + mismatch migration + auto-rebuild |
| 5 | `backend/app/services/rag_service.py` | 124+ | New `rebuild_vec_chunks_index()` function |
| 6 | `backend/tests/conftest.py` | 50, 76 | Use `settings.embedding_dimensions` |

No new files needed.

---

## Implementation

### 1. Configuration

**`backend/app/config.py`** — add after `embedding_model` (line 27):
```python
embedding_dimensions: int = 256  # 256 = Matryoshka optimized, 768 = full
```

**`backend/.env.example`** — add after `EMBEDDING_MODEL`:
```
# Embedding dimensions (256 = Matryoshka optimized, 768 = full)
EMBEDDING_DIMENSIONS=256
```

### 2. Embedding Truncation

**`backend/app/services/ollama_service.py`** — replace line 86 (`return embeddings[0]`):
```python
full = embeddings[0]
dim = settings.embedding_dimensions
if dim and dim < len(full):
    return full[:dim]
return full
```

Matryoshka truncation = slice first N dimensions. `settings` already imported at line 9.

### 3. Database Dimension Migration

**`backend/app/database.py`** — three new helpers + `init_db()` changes:

#### 3a. Detect current dimension (new function)
Parse `sqlite_master.sql` for the `float[N]` declaration — sqlite-vec has no metadata API.

#### 3b. Migrate on mismatch (new function)
For each vec table: detect dimension -> if mismatch, `DROP TABLE` + `CREATE VIRTUAL TABLE` with new dim. Also clears `vec_memory_map` since rowids are invalidated.

#### 3c. Update `init_db()` flow
```
1. Base.metadata.create_all           (unchanged)
2. _migrate_vec_dimensions(conn)      (NEW - detect+recreate if dim changed)
3. CREATE vec_chunks float[{dim}]     (was float[768])
4. CREATE vec_memories float[{dim}]   (was float[768])
5. ... rest unchanged ...
6. _rebuild_vec_on_startup()          (REPLACES _warn_vec_on_startup)
```

#### 3d. Replace `_warn_vec_on_startup` with `_rebuild_vec_on_startup`
Detects empty vec tables with non-empty source data and auto-rebuilds:
- `vec_memory_map` empty + `game_memories` has rows -> `rebuild_vec_index()`
- `vec_chunks` empty + `document_chunks` has rows -> `rebuild_vec_chunks_index()`

### 4. New Rebuild Utility

**`backend/app/services/rag_service.py`** — add `rebuild_vec_chunks_index()` after line 124:
- Module-level async function (matches `rebuild_vec_index` pattern in `memory_service.py`)
- Clears `vec_chunks`, iterates `document_chunks`, re-embeds with `search_document:` prefix
- Returns count of rebuilt rows

### 5. Test Updates

**`backend/tests/conftest.py`**:
- Import `settings` from `app.config`
- Line 50: `float[768]` -> `f"float[{settings.embedding_dimensions}]"`
- Line 76: `[0.1] * 768` -> `[0.1] * settings.embedding_dimensions`

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Fresh install | Tables created at 256-dim, no rebuild |
| Existing 768 data | Tables recreated at 256, auto-rebuild re-embeds |
| `EMBEDDING_DIMENSIONS=768` | No migration, fully backward compatible |
| Dimension changed back | Drop + recreate + rebuild (same path) |
| sqlite-vec unavailable | Existing try/except handles gracefully |
| No source data | Rebuild skips (0 rows detected) |

---

## Verification

1. `cd backend && python -m pytest` — tests pass with 256-dim mocks
2. Fresh start: delete DB, check logs for `float[256]` table creation
3. Migration: existing DB + restart -> logs show dimension migration + rebuild
4. Chrome MCP: upload doc -> RAG works; game session -> search_memory works
5. Backward compat: `EMBEDDING_DIMENSIONS=768` -> no migration
