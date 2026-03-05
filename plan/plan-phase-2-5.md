# Phase 2.5: Memory Management Tools

## Context

Phases 2.1-2.4 built the full game memory infrastructure: `GameMemory` ORM model, FTS5 full-text search, sqlite-vec vector search, hybrid RRF scoring, and Stanford Generative Agents retrieval scoring. However, **no tool exists that writes to `game_memories`** — the table is always empty. The retrieval pipeline in `chat_service.py` works but has no data to search.

Phase 2.5 closes this gap by adding three LLM-callable tools that let the DM agent store and recall memories.

## Changes Overview

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/services/tool_service.py` | Modify | Add `embedding_service` kwarg injection |
| `backend/app/services/chat_service.py` | Modify | Pass `self.embedding_service` at 2 `execute_tool` call sites |
| `backend/app/services/builtin_tools/memory.py` | **New** | 3 tool functions: `archive_event`, `search_memory`, `get_session_summary` |
| `backend/app/services/builtin_tools/__init__.py` | Modify | Import + add to `BUILTIN_REGISTRY` |
| `backend/app/database.py` | Modify | 3 entries in `_builtin_tool_defs()` |
| `backend/app/services/prompt_builder.py` | Modify | Add to `RPG_TOOL_NAMES`, `_CORE_TOOLS`, Layer 1 hint |
| `frontend/src/components/tools/renderers/MemoryRenderer.tsx` | **New** | Renderer for 3 types |
| `frontend/src/components/tools/renderers/index.ts` | Modify | Register 3 renderer types |

## Step 1: Inject `embedding_service` into tool execution pipeline

**File**: `backend/app/services/tool_service.py`

Add `embedding_service=None` kwarg to both `execute_tool()` (line 31) and `_execute_builtin()` (line 74). Pass it through at line 43-44. In `_execute_builtin`, add injection block after `conversation_id` injection (after line 100):

```python
if "embedding_service" in sig.parameters and embedding_service is not None:
    arguments = {**arguments, "embedding_service": embedding_service}
```

This mirrors the existing `session`/`conversation_id` injection pattern exactly. Existing tools that don't declare `embedding_service` will have it stripped by the unknown-argument filter (lines 102-116).

## Step 2: Pass `embedding_service` from `chat_service.py`

**File**: `backend/app/services/chat_service.py` (lines 343 and 353)

Add `embedding_service=self.embedding_service` to both `self.tool_service.execute_tool(...)` calls.

## Step 3: Create `backend/app/services/builtin_tools/memory.py`

Three functions following the `session.py` pattern (keyword-only `session`/`conversation_id`/`embedding_service`, ORM imports inside body, return `json.dumps({...})`):

### `archive_event(description, importance=5, entity_names="", memory_type="episodic", *, session, conversation_id, embedding_service=None)`
- Get game session via `get_or_create_session(session, conversation_id)`
- Normalize `importance` (1-10 int) → float: `max(0.0, min(1.0, (importance - 1) / 9.0))`
- Parse `entity_names` comma-separated string → `list[str]`
- Call `memory_service.create_memory(session, session_id=gs.id, memory_type=memory_type, entity_type="event", content=description, entity_names=entities, importance_score=score, embedding_service=embedding_service)`
- Return `{"type": "memory_archived", "description", "importance", "entities", "memory_type"}`

### `search_memory(query, memory_type="", *, session, conversation_id, embedding_service=None)`
- Get game session
- Call `memory_service.search_with_stanford_scoring(session, query, embedding_service=embedding_service, session_id=gs.id)`
- Fetch full memory objects via `get_memories_by_ids()`
- Filter by `memory_type` if non-empty
- Return `{"type": "memory_results", "query", "memories": [{content, importance, memory_type, entities, created_at}], "count"}`
- Empty result: `{"memories": [], "count": 0}`

### `get_session_summary(session_number=0, *, session, conversation_id)`
- No `embedding_service` needed — just a DB query
- Query `game_memories` WHERE `session_id=gs.id`, ordered by `created_at` ASC
- Build programmatic summary (type counts, date range)
- Return `{"type": "session_summary", "session_number", "events": [...], "count", "summary"}`

## Step 4: Register in `__init__.py`

**File**: `backend/app/services/builtin_tools/__init__.py`

```python
from app.services.builtin_tools.memory import archive_event, search_memory, get_session_summary

BUILTIN_REGISTRY = {
    ...
    # Phase 10 — Memory
    "archive_event": archive_event,
    "search_memory": search_memory,
    "get_session_summary": get_session_summary,
}
```

## Step 5: Seed tool definitions in `database.py`

**File**: `backend/app/database.py` in `_builtin_tool_defs()`

Add 3 entries with `_schema()` and `_config()` helpers:
- `archive_event`: required=["description"], optional: importance(int), entity_names(str), memory_type(str)
- `search_memory`: required=["query"], optional: memory_type(str)
- `get_session_summary`: required=[], optional: session_number(int)

## Step 6: Update `prompt_builder.py`

**File**: `backend/app/services/prompt_builder.py`

1. Add `"archive_event", "search_memory", "get_session_summary"` to `RPG_TOOL_NAMES` (line 24)
2. Add same 3 to `_CORE_TOOLS` (line 111) — memory should always be available regardless of game phase
3. Add one line to `_build_layer1_identity()`: `"- Use archive_event to record significant story moments for long-term memory.\n"`

## Step 7: Create `MemoryRenderer.tsx`

**File**: `frontend/src/components/tools/renderers/MemoryRenderer.tsx`

Single component dispatching on `raw.type` (multi-shape pattern like `LocationRenderer`):

- **`memory_archived`**: Confirmation card with brain icon, description text, importance dot (green 1-4, yellow 5-7, red 8-10), entity name pills, memory_type badge
- **`memory_results`**: Search results with query header, list of memories (memory_type color badge + content + importance + created_at), empty state
- **`session_summary`**: Summary header + chronological event list with badges

Memory type colors: episodic=blue, semantic=purple, procedural=amber. Card standard: `bg-gray-800/30 rounded-lg px-3 py-2.5 border border-gray-700/30 space-y-2`.

## Step 8: Register renderer in `index.ts`

```typescript
// Phase 10 — Memory
import { MemoryRenderer } from "./MemoryRenderer";
registerToolRenderer("memory_archived", MemoryRenderer);
registerToolRenderer("memory_results", MemoryRenderer);
registerToolRenderer("session_summary", MemoryRenderer);
```

## Implementation Order

1. `tool_service.py` (unblocks embedding injection)
2. `chat_service.py` (passes embedding_service)
3. `memory.py` (new tool module)
4. `__init__.py` (registry)
5. `database.py` (tool definitions)
6. `prompt_builder.py` (phase config + prompt hint)
7. `MemoryRenderer.tsx` (frontend, can parallel with 3-6)
8. `index.ts` (register renderer)

## Verification

1. Restart backend — confirm 44 tools seeded (was 41)
2. Chrome MCP: Start a game session, play a few turns
3. Verify the LLM calls `archive_event` for significant events
4. Verify `memory_archived` renderer shows in chat
5. Ask "what happened earlier?" — verify LLM uses `search_memory`
6. Verify `memory_results` renderer shows search results
7. Call `get_session_summary` — verify `session_summary` renderer
8. Check server logs for Stanford scoring and FTS/vec search activity
