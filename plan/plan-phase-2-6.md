# Phase 2.6: Session Summarization

## Context

Phases 2.1-2.5 built the full game memory infrastructure: `GameMemory` model, FTS5 + sqlite-vec hybrid search, Stanford retrieval scoring, and three LLM-callable tools (`archive_event`, `search_memory`, `get_session_summary`). However, the current `get_session_summary` is purely programmatic — it counts memories and returns a date range with no LLM narrative. There is no session lifecycle (no "end session" concept, no session numbering), and no hierarchical summarization.

Phase 2.6 adds:
1. **Session lifecycle fields** — `session_number`, `status`, `session_summary` on `GameSession`
2. **`end_session` builtin tool** — triggers LLM-based narrative summarization and stores the result
3. **Upgraded `get_session_summary`** — returns LLM narrative when available (generates on-demand otherwise)
4. **Summarization service** — reuses the `generate_summary()` pattern from `token_utils.py` with game-memory-aware prompts
5. **Frontend renderer upgrade** — new `session_ended` view + narrative badge on summaries

Scope: **Session-level summarization only**. Encounter-level and campaign-level are deferred (encounter grouping requires combat-boundary detection; campaign = aggregation of session summaries).

## Design Decisions

- **Trigger**: Explicit `end_session` tool call by the LLM/player. No automatic MemGPT-style trigger (that's Phase 2.8).
- **Storage**: Dual — LLM narrative stored on `GameSession.session_summary` (fast retrieval) AND archived as a `GameMemory` with `memory_type="summary"` (searchable via hybrid search, injectable into future contexts).
- **Session numbering**: `session_number` default=1 on `GameSession`. Due to the 1:1 unique constraint (`conversation_id`), multi-session-per-conversation is deferred to Phase 5.1.
- **`llm_service` injection**: Follows the proven `embedding_service` pattern in `tool_service.py` (lines 104-105).

## Changes Overview

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/models/rpg.py` | Modify | Add `session_number`, `status`, `session_summary` to `GameSession` |
| `backend/app/database.py` | Modify | Migration for new columns + `end_session` tool def + update `get_session_summary` description |
| `backend/app/config.py` | Modify | Add `session_summary_enabled`, `session_summary_max_tokens` settings |
| `backend/app/services/summarization_service.py` | **New** | LLM-based session summarization logic |
| `backend/app/services/tool_service.py` | Modify | Add `llm_service` kwarg injection (mirrors `embedding_service`) |
| `backend/app/services/chat_service.py` | Modify | Pass `self.llm_service` at both `execute_tool` call sites |
| `backend/app/services/builtin_tools/memory.py` | Modify | Add `end_session()`, upgrade `get_session_summary()`, extract `_memory_to_event()` helper |
| `backend/app/services/builtin_tools/__init__.py` | Modify | Import + register `end_session` |
| `backend/app/services/prompt_builder.py` | Modify | Add `end_session` to `RPG_TOOL_NAMES` and `_CORE_TOOLS` |
| `frontend/src/components/tools/renderers/MemoryRenderer.tsx` | Modify | Add `SessionEndedData` interface, `EndedView` component, narrative badge on `SummaryView` |
| `frontend/src/components/tools/renderers/index.ts` | Modify | Register `session_ended` type |

## Step 1: Add fields to `GameSession` model

**File**: `backend/app/models/rpg.py` (lines 17-34)

Add three columns after `combat_state` (line 27), before `created_at` (line 28):

```python
session_number: Mapped[int] = mapped_column(Integer, default=1)
status: Mapped[str] = mapped_column(String(20), default="active")  # active | ended
session_summary: Mapped[str | None] = mapped_column(Text, nullable=True)  # LLM narrative
```

## Step 2: Add column migration in `database.py`

**File**: `backend/app/database.py`

Add `_migrate_game_sessions_table(conn)` following the `_migrate_messages_table()` pattern (lines 135-147). Call it from `init_db()` after line 125:

```python
async def _migrate_game_sessions_table(conn) -> None:
    """Add columns introduced in Phase 2.6 (idempotent)."""
    columns_to_add = [
        ("session_number", "INTEGER DEFAULT 1"),
        ("status", "VARCHAR(20) DEFAULT 'active'"),
        ("session_summary", "TEXT"),
    ]
    for col_name, col_type in columns_to_add:
        try:
            await conn.execute(
                text(f"ALTER TABLE rpg_game_sessions ADD COLUMN {col_name} {col_type}")
            )
            logger.info("Added column rpg_game_sessions.%s", col_name)
        except Exception:
            pass  # Column already exists
```

Call in `init_db()` right after `await _migrate_messages_table(conn)` (line 125):
```python
await _migrate_game_sessions_table(conn)
```

Also add the `end_session` tool definition in `_builtin_tool_defs()` after the `get_session_summary` entry (line 654), and update the `get_session_summary` description to mention narrative summaries.

## Step 3: Add config settings

**File**: `backend/app/config.py` (after line 71, after the Stanford scoring settings)

```python
# Session summarization (Phase 2.6)
session_summary_enabled: bool = True
session_summary_max_tokens: int = 300
```

## Step 4: Create summarization service

**File**: `backend/app/services/summarization_service.py` (**NEW**)

LLM-based session summarization. Gathers all `GameMemory` records for the session + current characters + quests, constructs a prompt, calls `llm_service.chat()`. Returns narrative text string.

Key function: `generate_session_summary(db, game_session, llm_service, model) -> str`

Reuses the exact pattern from `token_utils.py:generate_summary()` (lines 336-381): build prompt, call `llm_service.chat()` with `num_predict` cap, return content string.

Prompt focuses on: key story beats, character actions, discoveries, combat outcomes, quest progress. 2-4 sentences, past tense, third person.

## Step 5: Inject `llm_service` into tool execution pipeline

**File**: `backend/app/services/tool_service.py`

Mirrors the existing `embedding_service` injection (lines 38, 83, 46, 104-105):

1. Add `llm_service=None` to `execute_tool()` signature (line 38)
2. Add `llm_service=None` to `_execute_builtin()` signature (line 83)
3. Pass `llm_service=llm_service` in the `_execute_builtin()` call (line 44-46)
4. Add injection block after the `embedding_service` block (after line 105):
   ```python
   if "llm_service" in sig.parameters and llm_service is not None:
       arguments = {**arguments, "llm_service": llm_service}
   ```

Functions that don't declare `llm_service` have it stripped by the existing unknown-argument filter (lines 110-121).

## Step 6: Pass `llm_service` from `chat_service.py`

**File**: `backend/app/services/chat_service.py`

At both `execute_tool` call sites (lines 343-348 and 354-358), add `llm_service=self.llm_service`.

## Step 7: Add `end_session` tool and upgrade `get_session_summary`

**File**: `backend/app/services/builtin_tools/memory.py`

### Extract `_memory_to_event()` helper
Deduplicate the event-building logic currently in `get_session_summary` (lines 130-136):
```python
def _memory_to_event(m) -> dict:
    return {
        "content": m.content,
        "memory_type": m.memory_type,
        "importance": round((m.importance_score or 0.5) * 9 + 1),
        "entities": json.loads(m.entity_names) if m.entity_names else [],
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }
```

### New `end_session()` function

```python
async def end_session(
    summary_override: str = "",
    *,
    session: AsyncSession,
    conversation_id: str,
    llm_service=None,
    embedding_service=None,
) -> str:
```

Logic:
1. Get game session via `get_or_create_session()`
2. If `gs.status == "ended"`, return error
3. Generate summary: use `summary_override` if provided, else call `summarization_service.generate_session_summary()` if `llm_service` available, else fall back to programmatic summary
4. Set `gs.status = "ended"`, `gs.session_summary = summary_text`
5. Archive summary as `GameMemory` with `memory_type="summary"`, `entity_type="session_summary"`, `importance_score=0.9`
6. Return `{"type": "session_ended", "session_number", "world_name", "summary", "status"}`

### Upgrade `get_session_summary()`

Add `llm_service=None, embedding_service=None` to signature. Logic:
1. If `gs.session_summary` exists, return it directly (cached narrative)
2. If memories exist and `llm_service` available, generate narrative on-the-fly and cache on `gs.session_summary`
3. Fall back to existing programmatic summary
4. Add `"narrative": True/False` flag to response JSON

## Step 8: Register in `__init__.py`

**File**: `backend/app/services/builtin_tools/__init__.py`

Update import (line 55) to include `end_session`:
```python
from app.services.builtin_tools.memory import archive_event, end_session, get_session_summary, search_memory
```

Add to `BUILTIN_REGISTRY` (after line 120):
```python
"end_session": end_session,
```

## Step 9: Update `prompt_builder.py`

**File**: `backend/app/services/prompt_builder.py`

1. Add `"end_session"` to `RPG_TOOL_NAMES` set (line 45)
2. Add `"end_session"` to `_CORE_TOOLS` frozenset (line 123)

## Step 10: Upgrade `MemoryRenderer.tsx`

**File**: `frontend/src/components/tools/renderers/MemoryRenderer.tsx`

### Add `SessionEndedData` interface
```typescript
interface SessionEndedData {
  type: "session_ended";
  session_number: number;
  world_name?: string;
  summary: string;
  status: string;
  error?: string;
}
```

### Add `EndedView` component
Card with book icon, "Session Ended" header, session number + world name, summary text in italic.

### Upgrade `SummaryView`
When `narrative: true` is in the response, show scroll icon instead of clipboard, add amber "narrative" badge, render summary in italic.

### Update switch statement
Add `case "session_ended"` dispatching to `EndedView`.

## Step 11: Register `session_ended` in `index.ts`

**File**: `frontend/src/components/tools/renderers/index.ts`

```typescript
registerToolRenderer("session_ended", MemoryRenderer);
```

## Implementation Order

1. `backend/app/models/rpg.py` — Schema changes (unblocks everything)
2. `backend/app/database.py` — Migration + tool defs (unblocks startup)
3. `backend/app/config.py` — Settings (unblocks service)
4. `backend/app/services/summarization_service.py` — New service (can parallel with 5-6)
5. `backend/app/services/tool_service.py` — `llm_service` injection
6. `backend/app/services/chat_service.py` — Pass `llm_service`
7. `backend/app/services/builtin_tools/memory.py` — `end_session` + upgrade `get_session_summary`
8. `backend/app/services/builtin_tools/__init__.py` — Registry
9. `backend/app/services/prompt_builder.py` — Tool name sets
10. `frontend/src/components/tools/renderers/MemoryRenderer.tsx` — Renderer (can parallel with 4-9)
11. `frontend/src/components/tools/renderers/index.ts` — Register

## Verification

1. Restart backend — confirm new columns created on `rpg_game_sessions` (check logs for migration messages)
2. Confirm 45 tools seeded (was 44 after Phase 2.5: +1 `end_session`)
3. Chrome MCP: Start a game session, play a few turns with combat/exploration
4. Verify the LLM calls `archive_event` for significant events (prerequisite for good summaries)
5. Call `get_session_summary` — verify it generates an LLM narrative (scroll icon + "narrative" badge)
6. Ask the LLM to "end the session" — verify it calls `end_session`
7. Verify `session_ended` card renders with narrative summary
8. Call `get_session_summary` again after ending — verify cached narrative is returned
9. Search memory for summary content — verify archived as `GameMemory` with `memory_type="summary"`
10. Start a new game and verify previous summary is recallable via `search_memory`
