# Phase 4.2: Narrator Agent

## Context

Phase 4.1 (Agent Orchestrator) extracted the agent loop from `chat_service.py` into a multi-agent pipeline scaffolding: `AgentContext` dataclass, `BaseAgent` ABC, `SingleAgent` concrete class, and `AgentOrchestrator` sequential coordinator. All gated behind `multi_agent_enabled=False` (default) for full backward compatibility.

Phase 4.2 introduces the **Narrator Agent** — the first specialized agent. It replaces `SingleAgent` in the orchestrator pipeline when multi-agent mode is enabled, providing a storytelling-focused system prompt while retaining all production infrastructure (tool calling, history summarization, MemGPT eviction, tool validation).

Since Rules Engine (4.3) and Archivist (4.4) don't exist yet, the Narrator must handle ALL tools as a standalone agent. The narrative focus comes from the system prompt, not tool restriction.

---

## Design Decisions

### D1: NarratorAgent extends SingleAgent (inheritance)
`SingleAgent.run()` contains ~200 lines of critical infrastructure. NarratorAgent inherits it and only overrides `name`, `allowed_tool_names`, and `build_system_prompt`. Zero duplication.

### D2: All tools (interim)
`allowed_tool_names` returns `None` (all tools) until Rules Engine exists. A `_NARRATOR_FINAL_TOOLS` constant is defined for future narrowing.

### D3: Orchestrator wires `build_system_prompt` hook
`BaseAgent.build_system_prompt()` is defined but never called. The orchestrator must call it before each agent's `run()` and replace the system prompt in `ctx.messages`. Since Layer 3 (game state) requires async DB queries, we add a `build_system_prompt_async()` method that the orchestrator checks first.

### D4: System prompt identification by `/nothink` prefix
All RPG system prompts start with `/nothink`. RAG and memory system messages do not. This is a reliable identifier for replacement.

### D5: Existing `multi_agent_enabled` config — no new flags

---

## Files

### New (1)

| File | Purpose |
|------|---------|
| `backend/app/services/narrator_agent.py` | `NarratorAgent` class + narrator prompt builder (~100 lines) |

### Modified (2)

| File | Change |
|------|--------|
| `backend/app/services/agent_orchestrator.py` | Wire `build_system_prompt` hook + `_replace_system_prompt` helper |
| `backend/app/dependencies.py` | Swap `SingleAgent()` for `NarratorAgent()` in `get_orchestrator()` |

### Unchanged (reference)

| File | Why |
|------|-----|
| `backend/app/services/agent_base.py` | NarratorAgent inherits `SingleAgent.run()` — no changes needed |
| `backend/app/services/agent_context.py` | Shared context — no changes |
| `backend/app/services/chat_service.py` | Dispatch logic unchanged — still uses orchestrator or direct SingleAgent |
| `backend/app/services/prompt_builder.py` | Reuse `_build_layer2_jit_rules`, `_build_layer3_state` via import (private-by-convention, same package) |
| `backend/app/config.py` | Existing `multi_agent_enabled` toggle is sufficient |
| `frontend/` | No changes — `agent?: string` field and `agent_start` handler already exist from 4.1 |

---

## Implementation Steps

### Step 1: Create `narrator_agent.py`

**File**: `backend/app/services/narrator_agent.py`

```python
class NarratorAgent(SingleAgent):
    """Storytelling agent — narration, dialogue, scene description."""

    @property
    def name(self) -> str:
        return "narrator"

    @property
    def allowed_tool_names(self) -> frozenset[str] | None:
        return None  # Interim: all tools until Rules Engine (4.3) exists

    def build_system_prompt(self, ctx: AgentContext) -> str | None:
        return None  # Sync — signals orchestrator to try async path

    async def build_system_prompt_async(self, ctx: AgentContext) -> str | None:
        return await _build_narrator_prompt(ctx)
```

**Narrator system prompt structure** (4 layers, ~420 tokens total):

- **Layer 1 — Narrator Identity (~220 tokens)**: Master storyteller role. Sensory descriptions, NPC voicing, tension/pacing. Retains ALL mechanical enforcement rules from original prompt (must still handle combat until 4.3).
- **Layer 2 — JIT Phase Rules**: Reused from `prompt_builder._build_layer2_jit_rules(phase)`.
- **Layer 3 — Live Game State**: Reused from `prompt_builder._build_layer3_state(session, game_session)`. Includes party, location, exits, NPCs, quests, environment, relationships.
- **Layer 4 — Narrator Format (~50 tokens)**: 2nd person narration, dramatic tool result descriptions, 2-3 player action suggestions, 200-word limit.

**Define future tool constant** (documentation + Phase 4.3 prep):
```python
_NARRATOR_FINAL_TOOLS: frozenset[str] = frozenset({
    "look_around", "move_to", "create_location", "connect_locations", "set_environment",
    "create_npc", "talk_to_npc", "update_npc_relationship", "npc_remember",
    "init_game_session", "get_game_state",
    "create_quest", "update_quest_objective", "complete_quest", "get_quest_journal",
    "archive_event", "search_memory",
})
```

### Step 2: Update `agent_orchestrator.py`

Add system prompt wiring before each agent's `run()`:

```python
async def run_pipeline(self, ctx):
    for i, agent in enumerate(self.agents):
        ctx.current_agent = agent.name

        # Phase 4.2: Apply agent-specific system prompt
        new_prompt = None
        if hasattr(agent, "build_system_prompt_async"):
            new_prompt = await agent.build_system_prompt_async(ctx)
        if new_prompt is None:
            new_prompt = agent.build_system_prompt(ctx)
        if new_prompt is not None:
            _replace_system_prompt(ctx, new_prompt)

        yield ServerSentEvent(...)  # agent_start event (existing)

        async for event in agent.run(ctx):  # existing delegation
            ...  # existing event injection
```

Add `_replace_system_prompt` helper:
- Find first system message starting with `/nothink` in `ctx.messages`
- Replace its content with the agent's prompt
- Update `ctx.budget.system_prompt_tokens` delta
- Fallback: insert at position 0 if no existing system prompt found

### Step 3: Update `dependencies.py`

```python
from app.services.narrator_agent import NarratorAgent

@lru_cache
def get_orchestrator() -> AgentOrchestrator:
    return AgentOrchestrator(agents=[NarratorAgent()])
```

The `chat_service.py` dispatch (line 277-287) is unchanged:
- `multi_agent_enabled=True` + `phase is not None` → orchestrator runs `[NarratorAgent()]`
- `multi_agent_enabled=False` (default) → direct `SingleAgent()` instantiation (line 285)

---

## Backward Compatibility

| Scenario | Behavior | Changed? |
|----------|----------|----------|
| `multi_agent_enabled=False` (default) | `SingleAgent()` created directly in chat_service.py line 285 | No |
| `multi_agent_enabled=True`, RPG | Orchestrator runs `NarratorAgent` (was `SingleAgent`) | Yes — better prompt |
| `multi_agent_enabled=True`, non-RPG | `phase is None` → direct `SingleAgent()` | No |
| Frontend SSE events | `agent: "narrator"` instead of `"default"` | Cosmetic only |
| DB schema | No changes | No |
| API routes | No changes | No |

---

## Verification

### 1. Backend startup
```bash
cd backend && uvicorn app.main:app --reload
```
No import errors or startup failures.

### 2. Default mode (`multi_agent_enabled=False`)
- Start D&D game, create characters, explore, combat
- Verify identical behavior — NarratorAgent never used
- Check logs: no `Agent started: narrator` messages

### 3. Narrator mode (`MULTI_AGENT_ENABLED=true`)
- Start new game
- Verify narrator prompt produces richer, more descriptive narration
- Check server logs for `Agent started: narrator` and token budget logs
- Verify all tools work: dice, combat, inventory, NPCs, quests, memory
- Verify SSE events have `agent: "narrator"`

### 4. Chrome MCP verification
- Navigate to chat, start a game session
- Send several messages exercising different game phases
- Verify tool results render correctly in all renderers
- Check browser console for `agent_start` with `"narrator"`
- Compare narration quality between modes

### 5. Type check
```bash
cd frontend && npx tsc --noEmit  # No frontend changes, should pass
```
