# Phase 2.8: MemGPT-Style Eviction with Recall Storage

## Context

After completing Phases 2.1-2.7 (game memory table, FTS5, hybrid RRF search, Stanford scoring, memory tools, session summarization, metadata pre-filtering), the system still lacks a critical MemGPT concept: **recall storage**. When conversation history is evicted by Phase 1.2 summarization or truncation, those messages are permanently lost — the LLM cannot retrieve them.

Phase 2.8 adds the final two MemGPT concepts:
1. **Recall storage**: Evicted messages are archived to `game_memories` (type `"recall"`) before deletion, making them searchable via existing hybrid search
2. **Context pressure warning**: The LLM is told when context is filling up, enabling self-directed memory management via `archive_event` and a new `recall_context` tool

**Key insight**: Phase 1.2 already implements 70% threshold + recursive summarization. Phase 2.8 wraps around it, adding persistence (recall storage) and LLM awareness (warnings + recall tool).

## Architecture

```
Message flow after Phase 2.8:

stream_chat()
  |-- Phase 1.2: apply_history_summarization() [70% threshold, recursive summary]
  |-- Phase 2.8: evict_and_store()             [95% threshold, recall storage + warning]
  |-- Safety:    truncate_history()             [hard cap, final safety net]
```

Three-tier defense:
| Layer | Threshold | Action | Messages Lost? |
|-------|-----------|--------|----------------|
| Phase 1.2 | 70% | Summarize old groups | Yes (replaced by summary) |
| Phase 2.8 | 95% | Archive to recall + summarize | No (stored in game_memories) |
| Truncation | 100% | Hard cut oldest groups | Yes (safety net only) |

## Implementation Steps

### Step 1: Config Settings
**File**: `backend/app/config.py`

Add after existing memory settings:
```python
# MemGPT-style eviction (Phase 2.8)
memgpt_eviction_enabled: bool = True
memgpt_warning_threshold: float = 0.7     # Inject context pressure warning
memgpt_flush_threshold: float = 0.95      # Auto-evict at this utilization
memgpt_flush_target_pct: float = 0.5      # Evict ~50% of oldest groups
memgpt_recall_importance: float = 0.6     # Importance score for recall memories
memgpt_max_recall_tokens: int = 400       # Max tokens for recall summary
```

### Step 2: Bug Fix — `think=False` in `generate_summary`
**File**: `backend/app/services/token_utils.py` (line 376)

Add `think=False` to the `llm_service.chat()` call. Without this, qwen3.5's native thinking mode consumes the token budget and returns empty content.

```python
# Before:
response = await llm_service.chat(
    model,
    [{"role": "user", "content": prompt}],
    options={"num_predict": max_tokens + 100},
)

# After:
response = await llm_service.chat(
    model,
    [{"role": "user", "content": prompt}],
    think=False,
    options={"num_predict": max_tokens + 100},
)
```

### Step 3: Eviction Service (NEW FILE)
**File**: `backend/app/services/eviction_service.py`

Core module with these functions:

- `should_warn(budget) -> bool` — Check if context pressure warning needed
- `build_context_warning(budget) -> dict` — System message warning the LLM about context pressure
- `evict_and_store(messages, budget, llm_service, model, *, session, conversation_id, embedding_service, preserve_recent=10) -> list[dict]` — Main eviction pipeline:
  1. Separate system vs conversation messages
  2. Strip old warnings/eviction notices (prevent accumulation)
  3. If below flush threshold but above warning threshold: inject warning only
  4. If above flush threshold: evict ~50% of oldest groups
  5. Archive evicted messages to `game_memories` with `memory_type="recall"`, `entity_type="conversation"`
  6. Generate recursive summary of evicted content (reuses `generate_summary` from `token_utils.py`)
  7. Inject eviction notice telling LLM to use `recall_context`
  8. Update budget tracking

- `_store_recall(session, conversation_id, evicted_messages, embedding_service)` — Archive evicted messages using existing `memory_service.create_memory()` (auto-syncs to FTS5 + sqlite-vec)
- `_extract_entities_from_messages(messages) -> list[str]` — Scan tool results for character/NPC/location names to make recall searchable

**Reuses from `token_utils.py`**:
- `SUMMARY_PREFIX`, `_build_message_groups`, `_format_messages_for_summary`, `generate_summary`, `estimate_message_tokens`, `estimate_tokens`

### Step 4: `recall_context` Tool
**File**: `backend/app/services/builtin_tools/memory.py`

Add new function:
```python
async def recall_context(
    query: str,
    *,
    session: AsyncSession,
    conversation_id: str,
    embedding_service=None,
) -> str:
```
- Calls `memory_service.search_with_stanford_scoring()` with `memory_types=["recall"]`
- Returns `{"type": "recall_results", "query", "memories", "count", "message?"}`
- Leverages existing hybrid search + Stanford scoring infrastructure

### Step 5: Register Tool in Backend
**Files**:
- `backend/app/services/builtin_tools/__init__.py` — Import `recall_context`, add to `BUILTIN_REGISTRY`
- `backend/app/database.py` — Add tool definition in `_builtin_tool_defs()` after `end_session`
- `backend/app/services/prompt_builder.py` — Add `"recall_context"` to `RPG_TOOL_NAMES` set and `_CORE_TOOLS` frozenset (always available)

### Step 6: Integrate into Chat Service
**File**: `backend/app/services/chat_service.py`

Insert eviction call between Phase 1.2 summarization and `truncate_history()`:

```python
# Phase 1.2: Summarize older history if over threshold
if settings.history_summary_enabled:
    messages = await apply_history_summarization(...)

# Phase 2.8: MemGPT-style eviction with recall storage
if settings.memgpt_eviction_enabled:
    messages = await evict_and_store(
        messages, budget, self.llm_service, model,
        session=session,
        conversation_id=conversation_id,
        embedding_service=self.embedding_service,
        preserve_recent=settings.history_preserve_recent,
    )

messages = truncate_history(messages, budget)
```

### Step 7: Frontend Renderer
**File**: `frontend/src/components/tools/renderers/MemoryRenderer.tsx`

Add `RecallResultsData` interface and `RecallView` component to existing multi-dispatch renderer. Style matches existing `ResultsView` pattern with distinct icon (recycling/recall).

**File**: `frontend/src/components/tools/renderers/index.ts`

Add: `registerToolRenderer("recall_results", MemoryRenderer);`

## Critical Files

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/config.py` | Edit | Add 6 new config settings |
| `backend/app/services/token_utils.py` | Edit | Fix `think=False` bug (line 376) |
| `backend/app/services/eviction_service.py` | **Create** | Core eviction logic with recall storage |
| `backend/app/services/builtin_tools/memory.py` | Edit | Add `recall_context` function |
| `backend/app/services/builtin_tools/__init__.py` | Edit | Import + register `recall_context` |
| `backend/app/database.py` | Edit | Seed `recall_context` tool definition |
| `backend/app/services/prompt_builder.py` | Edit | Add to `RPG_TOOL_NAMES` + `_CORE_TOOLS` |
| `backend/app/services/chat_service.py` | Edit | Wire `evict_and_store` into stream_chat() |
| `frontend/src/components/tools/renderers/MemoryRenderer.tsx` | Edit | Add `recall_results` view |
| `frontend/src/components/tools/renderers/index.ts` | Edit | Register `recall_results` renderer |

## Reused Infrastructure (DO NOT recreate)

- `memory_service.create_memory()` — auto-syncs ORM + FTS5 + sqlite-vec
- `memory_service.search_with_stanford_scoring()` — hybrid RRF + Stanford reranking
- `token_utils.generate_summary()` — recursive LLM summarization
- `token_utils._build_message_groups()` — atomic tool-call group builder
- `token_utils._format_messages_for_summary()` — message formatting
- `token_utils.SUMMARY_PREFIX` — summary message marker
- `MemoryRenderer` pattern — multi-dispatch by `type` field
- `tool_service` injection via `inspect.signature()` — auto-injects `session`, `conversation_id`, `embedding_service`

## Design Decisions

1. **No new table** — use `game_memories` with `memory_type="recall"`, `entity_type="conversation"`. Existing FTS5 + vec search works immediately.
2. **Eviction is synchronous** — must happen before LLM call to ensure context fits.
3. **Warning is a system message** — inserted at 70%, stripped on re-entry to prevent accumulation.
4. **Dedicated `recall_context` tool** — simpler interface than `search_memory` with filters. Always in `_CORE_TOOLS`.
5. **Evicted batch → single recall memory** — concatenated text block, not individual messages. More efficient for storage and retrieval.
6. **Config toggle** — `memgpt_eviction_enabled=True` by default. When `False`, behavior identical to Phase 2.7.
7. **Recall NOT auto-injected** — `_PHASE_MEMORY_TYPES` does NOT include `"recall"`. Recall is on-demand via tool calls only, to avoid wasting context budget.

## Verification

1. **Backend startup**: Restart, confirm no errors, `recall_context` tool seeded (tool count = 46)
2. **Warning injection**: Send 10+ messages, check backend logs for "Context pressure warning" at 70%
3. **Eviction + recall storage**: Send 15+ messages, verify `game_memories` has `memory_type="recall"` entries
4. **Recall tool**: After eviction, ask "What happened at the beginning?" — verify LLM calls `recall_context`
5. **Frontend**: Verify `recall_results` renders correctly in chat
6. **`think=False` fix**: Verify summaries are non-empty in logs
7. **Toggle off**: Set `memgpt_eviction_enabled=False`, verify behavior identical to Phase 2.7
8. **Edge case**: Short conversation (<10 messages) — no eviction, no warning
