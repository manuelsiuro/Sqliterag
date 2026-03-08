# Phase 4.1: Agent Orchestrator — Implementation Plan

## Context

Phase 3 (Knowledge Graph & World Model) is fully complete (3.1-3.6). The current system runs a single monolithic agent loop in `chat_service.py` that handles narration, rules enforcement, and memory in one pass. Phase 4.1 refactors this into a multi-agent orchestrator that can run specialized agents (Narrator, Rules Engine, Archivist) in a sequential pipeline — while maintaining 100% backward compatibility with the existing single-agent behavior.

**Goal**: Create the scaffolding/infrastructure for multi-agent execution. Phase 4.1 does NOT implement the specialized agents (that's 4.2-4.4). It extracts the current agent loop into a `SingleAgent` class, wraps it in an orchestrator, and proves the pipeline works identically to the current code.

---

## Files Overview

### New Files (3)

| File | Purpose | Est. Lines |
|------|---------|-----------|
| `backend/app/services/agent_context.py` | `AgentContext` dataclass — shared mutable state flowing through the pipeline | ~60 |
| `backend/app/services/agent_base.py` | `BaseAgent` ABC + `SingleAgent` (extracted from chat_service.py lines 260-452) | ~250 |
| `backend/app/services/agent_orchestrator.py` | `AgentOrchestrator` — sequential pipeline coordinator | ~100 |

### Modified Files (4)

| File | Change | Risk |
|------|--------|------|
| `backend/app/services/chat_service.py` | Extract agent loop, add `AgentContext` construction + orchestrator dispatch | High |
| `backend/app/config.py` | Add `multi_agent_enabled: bool = False` | Low |
| `backend/app/dependencies.py` | Wire `AgentOrchestrator` into `get_chat_service()` | Low |
| `frontend/src/types/index.ts` | Add optional `agent?: string` to SSE event interfaces | Low |

---

## Step 1: Create `agent_context.py`

Shared mutable state dataclass passed through the pipeline. Created once per user turn.

**File**: `backend/app/services/agent_context.py`

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.tool import Tool
from app.services.token_utils import TokenBudget

if TYPE_CHECKING:
    from app.services.base import BaseLLMService
    from app.services.prompt_builder import GamePhase
    from app.services.tool_service import ToolService

@dataclass
class AgentContext:
    # Per-turn identifiers
    session: AsyncSession
    conversation_id: str
    model: str
    user_message: str
    options: dict

    # Shared services
    llm_service: BaseLLMService
    tool_service: ToolService
    embedding_service: BaseLLMService | None

    # Token budget (shared across all agents — NOT split)
    budget: TokenBudget

    # Conversation state
    messages: list[dict] = field(default_factory=list)
    conv_tools: list[Tool] = field(default_factory=list)
    tool_map: dict[str, Tool] = field(default_factory=dict)
    phase: GamePhase | None = None

    # Pipeline outputs
    final_response: str | None = None
    actions: list[dict] = field(default_factory=list)
    current_agent: str = ""
    agent_outputs: dict[str, str] = field(default_factory=dict)
```

**Key decisions**:
- Single shared `TokenBudget` — 8192 tokens is too small to split across agents. Agents are specialized by tools and prompts, not by separate context windows.
- `messages` list is the canonical conversation context mutated by all agents.
- `agent_outputs` lets later agents see earlier agents' text output.

---

## Step 2: Create `agent_base.py`

Base agent protocol + `SingleAgent` that wraps the existing agent loop verbatim.

**File**: `backend/app/services/agent_base.py`

### `BaseAgent` ABC

```python
class BaseAgent(abc.ABC):
    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @property
    @abc.abstractmethod
    def allowed_tool_names(self) -> frozenset[str] | None:
        """Tool names this agent may use, or None for all tools."""
        ...

    @abc.abstractmethod
    def build_system_prompt(self, ctx: AgentContext) -> str | None:
        """Build agent-specific system prompt. Return None to use existing."""
        ...

    @abc.abstractmethod
    async def run(self, ctx: AgentContext) -> AsyncGenerator[ServerSentEvent, None]:
        """Execute agent logic, yield SSE events."""
        ...
```

### `SingleAgent` — Exact Extraction

`SingleAgent.run()` is a **mechanical extraction** of `chat_service.py` lines 260-452. Every reference changes:
- `self.llm_service` → `ctx.llm_service`
- `self.tool_service` → `ctx.tool_service`
- `self.embedding_service` → `ctx.embedding_service`
- `conv_tools` → `ctx.conv_tools`
- `budget` → `ctx.budget`
- `messages` → `ctx.messages`
- `phase` → `ctx.phase`
- `tool_map` → `ctx.tool_map`
- `merged_options`/`options` → `ctx.options`
- `model` → `ctx.model`
- `conversation_id` → `ctx.conversation_id`
- `session` → `ctx.session`

The extracted code includes:
1. Phase-based tool filtering (reuses `filter_tools_by_phase()`)
2. Building `ollama_tools` list
3. History summarization (Phase 1.2) via `apply_history_summarization()`
4. MemGPT eviction (Phase 2.8) via `evict_and_store()`
5. History truncation via `truncate_history()`
6. Budget logging
7. The `for _round in range(MAX_TOOL_ROUNDS)` loop:
   - LLM call with `think=False`
   - Tool call validation + execution + SSE emission
   - Final response chunking + action extraction + done event

```python
class SingleAgent(BaseAgent):
    @property
    def name(self) -> str:
        return "default"

    @property
    def allowed_tool_names(self) -> frozenset[str] | None:
        return None  # All tools

    def build_system_prompt(self, ctx: AgentContext) -> str | None:
        return None  # System prompt already in ctx.messages

    async def run(self, ctx: AgentContext) -> AsyncGenerator[ServerSentEvent, None]:
        # --- Extracted verbatim from chat_service.py lines 260-452 ---
        # (with self.X → ctx.X substitutions)
        ...
```

**Critical**: `_extract_suggestions()` stays in `chat_service.py` as a module-level function and is imported by `agent_base.py`.

---

## Step 3: Create `agent_orchestrator.py`

Sequential pipeline coordinator.

**File**: `backend/app/services/agent_orchestrator.py`

```python
class AgentOrchestrator:
    def __init__(self, agents: list[BaseAgent]):
        self.agents = agents

    async def run_pipeline(
        self, ctx: AgentContext,
    ) -> AsyncGenerator[ServerSentEvent, None]:
        for i, agent in enumerate(self.agents):
            ctx.current_agent = agent.name

            # Emit agent_start event (new SSE type)
            yield ServerSentEvent(
                data=json.dumps({"agent": agent.name, "index": i}),
                event="agent_start",
            )

            # Run agent, inject agent attribution into events
            async for event in agent.run(ctx):
                try:
                    event_data = json.loads(event.data) if event.data else {}
                    event_data["agent"] = agent.name
                    yield ServerSentEvent(
                        data=json.dumps(event_data),
                        event=event.event,
                    )
                except (json.JSONDecodeError, TypeError):
                    yield event
```

**Pipeline semantics for Phase 4.1**: Only one agent (`SingleAgent`) runs, so the orchestrator is a pass-through with agent attribution added.

**Future phases (4.2-4.4)**: Pipeline becomes `[NarratorAgent, RulesEngineAgent, ArchivistAgent]`. Each agent:
1. Gets its own tool subset via `allowed_tool_names`
2. Gets its own system prompt via `build_system_prompt()`
3. Appends tool results to shared `ctx.messages`
4. Stores text output in `ctx.agent_outputs[self.name]`

---

## Step 4: Add config toggle

**File**: `backend/app/config.py` — add after line 108 (after GraphRAG settings):

```python
    # Multi-agent pipeline (Phase 4.1)
    multi_agent_enabled: bool = False
```

---

## Step 5: Wire dependencies

**File**: `backend/app/dependencies.py`

```python
from app.services.agent_base import SingleAgent
from app.services.agent_orchestrator import AgentOrchestrator

@lru_cache
def get_orchestrator() -> AgentOrchestrator:
    return AgentOrchestrator(agents=[SingleAgent()])

@lru_cache
def get_chat_service() -> ChatService:
    return ChatService(
        llm_service=get_ollama_service(),
        rag_service=get_rag_service(),
        tool_service=get_tool_service(),
        embedding_service=get_ollama_service(),
        orchestrator=get_orchestrator(),  # NEW
    )
```

---

## Step 6: Refactor `chat_service.py`

### Changes to `ChatService.__init__`

Add `orchestrator` parameter:

```python
def __init__(
    self,
    llm_service: BaseLLMService,
    rag_service: RAGService,
    tool_service: ToolService,
    embedding_service: BaseLLMService | None = None,
    orchestrator: AgentOrchestrator | None = None,  # NEW
):
    ...
    self.orchestrator = orchestrator
```

### Changes to `stream_chat()`

**Lines 1-254 (setup)**: Stay in `ChatService`. No changes except wrapping outputs into `AgentContext`.

**Lines 256-259 (kwargs)**: Move into `AgentContext.options`.

**Lines 260-452 (agent loop with tools)**: Replace with:

```python
if conv_tools:
    ctx = AgentContext(
        session=session,
        conversation_id=conversation_id,
        model=model,
        user_message=user_message,
        options=options,
        llm_service=self.llm_service,
        tool_service=self.tool_service,
        embedding_service=self.embedding_service,
        budget=budget,
        messages=messages,
        conv_tools=conv_tools,
        tool_map={t.name: t for t in conv_tools},
        phase=phase,
    )

    if (
        settings.multi_agent_enabled
        and self.orchestrator is not None
        and phase is not None  # Only RPG conversations
    ):
        async for event in self.orchestrator.run_pipeline(ctx):
            yield event
    else:
        agent = SingleAgent()
        async for event in agent.run(ctx):
            yield event
```

**Lines 460-494 (no-tools streaming)**: Stay in `ChatService` unchanged.

**`_extract_suggestions()`**: Stays in `chat_service.py` as module-level function — imported by `agent_base.py`.

**`_load_conversation_tools()`**: Stays in `ChatService` as private method.

---

## Step 7: Extend frontend types

**File**: `frontend/src/types/index.ts`

Add optional `agent` field to existing interfaces (backward compatible):

```typescript
export interface ToolCallEvent {
  tool_calls: Array<{ function: { name: string; arguments: Record<string, unknown> } }>;
  message_id: string;
  agent?: string;  // Phase 4.1
}

export interface ToolResultEvent {
  tool_name: string;
  arguments: Record<string, unknown>;
  result: string;
  message_id: string;
  agent?: string;  // Phase 4.1
}
```

In `frontend/src/services/api.ts`, add handling for the new `agent_start` event (debug log only, no UI changes):

```typescript
} else if (ev.event === "agent_start") {
  console.debug("Agent started:", JSON.parse(ev.data));
}
```

---

## Backward Compatibility Guarantees

1. **`multi_agent_enabled = False` (default)**: `ChatService` instantiates `SingleAgent()` directly — no orchestrator involved. Identical code path to current.
2. **`multi_agent_enabled = True`**: Orchestrator runs `[SingleAgent()]` — same behavior with agent attribution in SSE events.
3. **Non-RPG conversations**: `phase is None` → always uses `SingleAgent` directly, never orchestrator.
4. **SSE events**: `agent` field is optional — existing frontend ignores it.
5. **No router changes**: `routers/chat.py` continues calling `chat_service.stream_chat()` unchanged.
6. **No DB schema changes**: No new tables or columns.

---

## Token Budget Strategy

All agents share one `TokenBudget`. No splitting.

```
Total: 8192 tokens
  Response reserve: 2000
  Safety buffer:     300
  Input budget:     5892

  System prompt:    ~300 (shared)
  RAG/memory:       ~200 (shared)
  Tool defs:        ~400-800 (per-agent subset saves tokens)
  History:          ~3900-4600 (shared)
```

Per-agent tool subset savings (future, Phase 4.2+):
- Narrator: ~10 tools (~400 tokens) vs all 46 (~1800 tokens)
- Rules Engine: ~15 tools (~600 tokens)
- Archivist: ~10 tools (~400 tokens)

Orchestrator skips optional agents if `ctx.budget.tokens_remaining < 800`.

---

## Implementation Order

1. `agent_context.py` — standalone dataclass, no deps on new code
2. `agent_base.py` — ABC + `SingleAgent` extracted from chat_service
3. `agent_orchestrator.py` — pipeline coordinator
4. `config.py` — add toggle
5. `dependencies.py` — wire orchestrator
6. `chat_service.py` — refactor: extract loop, add dispatch
7. `frontend/src/types/index.ts` + `api.ts` — extend SSE types

---

## Verification

1. **Start backend**: `cd backend && uvicorn app.main:app --reload`
2. **Start frontend**: `cd frontend && npm run dev`
3. **Test with `multi_agent_enabled=False`** (default):
   - Start new D&D game, create characters, explore, enter combat
   - Verify identical behavior to pre-refactor
   - Check all tool results render correctly
4. **Test with `multi_agent_enabled=True`** (set in .env: `MULTI_AGENT_ENABLED=true`):
   - Same test — should produce identical results
   - Check console for `agent_start` debug logs
   - Verify SSE events have `agent: "default"` field
5. **Chrome MCP verification**:
   - Navigate to chat, take snapshot
   - Send RPG messages, verify tool call/result bubbles render
   - Check browser console for `agent_start` events
6. **TypeScript check**: `cd frontend && npx tsc --noEmit` — no type errors
