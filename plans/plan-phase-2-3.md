# Phase 2.3: Build Hybrid Search (RRF) for Game Memories

## Context

The game memory system has ORM + FTS5 (Phase 2.1-2.2) but no vector embeddings and no hybrid retrieval. Game memories exist in `game_memories` + `fts_memories` but are never retrieved or injected into the LLM context. The `vec_memories` virtual table was created but is unpopulated.

**Goal**: Combine sqlite-vec vector search + FTS5 full-text search using Reciprocal Rank Fusion (RRF) scoring, then inject relevant game memories into the chat context alongside document RAG.

**Why both?** Vector search captures semantic meaning ("the party fought monsters" matches "combat encounter") but misses exact names. FTS5 captures exact terms ("Thordak", "Silverdale") that vector search confuses.

---

## Files to Modify

| File | Changes |
|------|---------|
| `backend/app/config.py` | Add 6 hybrid search settings |
| `backend/app/database.py` | Add `vec_memory_map` table + startup sync warning |
| `backend/app/services/memory_service.py` | Add vec helpers, FTS sanitization, `search_vec`, `search_hybrid`, `get_memories_by_ids`, `rebuild_vec_index` |
| `backend/app/services/chat_service.py` | Add `embedding_service` param, game memory retrieval block |
| `backend/app/dependencies.py` | Wire `embedding_service` into `ChatService` |

---

## Implementation Steps

### Step 1: Config (`config.py`, after line 56)

Add settings to `Settings` class:

```python
# Game memory hybrid search (Phase 2.3)
memory_hybrid_search_enabled: bool = True
memory_rrf_k: int = 60                  # RRF smoothing constant
memory_weight_fts: float = 0.4          # FTS5 weight in RRF
memory_weight_vec: float = 0.6          # Vector weight in RRF
memory_search_top_k: int = 5            # Final results returned
memory_search_candidates_k: int = 20    # Candidates per source before merge
```

### Step 2: Database (`database.py`)

**2a.** Add `vec_memory_map` table in `init_db()` after `vec_memories` creation (after line 87):

```sql
CREATE TABLE IF NOT EXISTS vec_memory_map (
    rowid INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id TEXT NOT NULL UNIQUE
)
```

**Why?** `vec_memories` uses integer rowid but `GameMemory.id` is UUID string. This mapping table bridges them.

**2b.** Add `_sync_vec_on_startup()` after `_sync_fts_on_startup()` — just logs a warning if `vec_memory_map` is empty but `game_memories` has rows (full rebuild requires embedding service, too slow for startup).

### Step 3: FTS Query Sanitization (`memory_service.py`)

Add `_sanitize_fts_query()` to escape FTS5 special characters (`*`, `"`, `()`, `+`, `-`, `^`) and operators (`AND`, `OR`, `NOT`, `NEAR`). Each token is wrapped in double quotes for literal matching.

Apply to `search_fts()` before MATCH — fixes a latent bug where user queries with special chars would crash FTS5.

### Step 4: Vector Helpers (`memory_service.py`)

Add internal helpers mirroring the FTS pattern:

- **`_vec_insert(session, memory, embedding_service)`**: Generate embedding via `search_document: {content}`, insert into `vec_memory_map` + `vec_memories`
- **`_vec_delete(session, memory_id)`**: Clean up from both tables

Both wrapped in try/except for graceful degradation (if Ollama is down, memory still saves to ORM + FTS).

### Step 5: Update Public API (`memory_service.py`)

Add optional `embedding_service: BaseEmbeddingService | None = None` parameter to:

- `create_memory()` — call `_vec_insert` when provided
- `update_memory()` — call `_vec_delete` + `_vec_insert` when content changes
- `delete_memory()` — call `_vec_delete` (no embedding_service needed)
- `delete_session_memories()` — call `_vec_delete` for each memory

**Backward-compatible**: existing callers without embedding_service continue to work (FTS-only).

### Step 6: Vector Search (`memory_service.py`)

Add `search_vec()` returning `list[tuple[str, int]]` — (memory_id, rank_position) pairs:

1. Generate query embedding with `search_query:` prefix
2. Query `vec_memories WHERE embedding MATCH :query` via sqlite-vec
3. JOIN through `vec_memory_map` to get memory_id
4. Optional `session_id` filtering via JOIN to `game_memories`
5. Return rank positions (1-based, pre-sorted by distance)

### Step 7: RRF Hybrid Search (`memory_service.py`)

Add `search_hybrid()` — the core function:

```python
async def search_hybrid(
    session, query, *, embedding_service, session_id=None, top_k=None
) -> list[tuple[str, float]]:
```

1. Run `search_fts()` and `search_vec()` concurrently via `asyncio.gather`
2. Build rank maps: `{memory_id: rank_position}` for each source
3. Compute RRF score per memory: `w_fts / (rrf_k + fts_rank) + w_vec / (rrf_k + vec_rank)`
4. Sort by score descending, return top_k

**Graceful degradation**: If FTS fails → vec-only. If vec fails → FTS-only. If both fail → empty list.

### Step 8: Helper (`memory_service.py`)

Add `get_memories_by_ids(session, memory_ids) -> list[GameMemory]` — fetches full ORM objects preserving input order (for chat context injection).

### Step 9: Rebuild Utility (`memory_service.py`)

Add `rebuild_vec_index(session, embedding_service) -> int` — generates embeddings for all existing `game_memories` rows. One-time migration utility for memories created before Phase 2.3.

### Step 10: Chat Integration (`chat_service.py`)

**10a.** Add `embedding_service` param to `ChatService.__init__()` (optional, backward-compatible).

**10b.** After the RPG system prompt injection block (after line 202), add game memory retrieval:

```python
if phase is not None and settings.memory_hybrid_search_enabled:
    try:
        game_session = await get_or_create_session(session, conversation_id)
        memory_results = await search_hybrid(
            session, user_message,
            embedding_service=self.embedding_service,
            session_id=game_session.id,
        )
        if memory_results:
            memory_ids = [mid for mid, _score in memory_results]
            memories = await get_memories_by_ids(session, memory_ids)
            if memories:
                memory_text = "\n---\n".join(
                    f"[{m.memory_type}] {m.content}" for m in memories
                )
                memory_system = (
                    "Relevant game memories (use these to maintain consistency "
                    "and recall past events):\n" + memory_text
                )
                messages.insert(0, {"role": "system", "content": memory_system})
                budget.rag_context_tokens += estimate_tokens(memory_system)
    except Exception:
        logger.warning("Game memory retrieval failed", exc_info=True)
```

### Step 11: Dependencies (`dependencies.py`)

Pass `embedding_service=get_ollama_service()` to `ChatService` constructor.

---

## Reusable Existing Code

| What | Where | Usage |
|------|-------|-------|
| `serialize_float32()` | `rag_service.py:18` | Pack embeddings for sqlite-vec |
| `OllamaService.generate_embedding()` | `ollama_service.py:75` | Generate nomic-embed-text embeddings |
| `BaseEmbeddingService` | `services/base.py` | Type hint for embedding_service param |
| `estimate_tokens()` | `token_utils.py` | Budget tracking for injected memories |
| `get_or_create_session()` | `rpg_service.py` | Get game session from conversation_id |
| Task prefix pattern | `rag_service.py:67,85` | `search_document:` / `search_query:` prefixes |

---

## Verification

1. Start backend: `cd backend && uvicorn app.main:app --reload`
2. Check logs for: `vec_memory_map` table creation, no startup errors
3. Open chat UI, create RPG session with `init_game_session`
4. Play a few turns (create characters, explore, fight)
5. Check server logs for `"Injected N game memories into context"` (requires memories to exist — Phase 2.5 adds `archive_event` tool for automatic memory creation)
6. For manual testing: use a Python script to call `create_memory()` with `embedding_service`, then verify `search_hybrid()` returns results
7. Verify existing document RAG still works (upload a document, ask questions about it)
