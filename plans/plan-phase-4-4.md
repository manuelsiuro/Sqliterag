# Phase 4.4: Archivist Agent — Memory & Knowledge Graph Maintenance

## Context

The multi-agent pipeline currently has two agents:
- **RulesEngineAgent** (Phase 4.3) — COMBAT only, resolves mechanics with 14 tools
- **NarratorAgent** (Phase 4.2) — all phases, storytelling with 26 tools

The Archivist is the third agent from the AGENTS_FEATURE.md research document: a **silent bookkeeping agent** that maintains long-term memory, updates the knowledge graph, and tracks NPC/quest state. It runs last in the pipeline, processes all prior agent outputs, and never streams text to the user.

**Goal**: Separate memory/graph write operations from the Narrator into a dedicated agent, improving separation of concerns and memory quality.

---

## Key Design Decisions

### 1. Pipeline Order: RulesEngine → Narrator → Archivist

The Archivist runs **last** because it needs to process the Narrator's output (archive what was narrated). Its output is meta-bookkeeping, not player-facing narrative.

### 2. Silent Agent (non-user-facing)

The orchestrator currently suppresses `token`/`done` events from non-final agents. Since the Archivist is the final agent but should NOT stream to the user, we add an `is_user_facing` property to `BaseAgent`. The orchestrator uses this instead of position to decide suppression. The Narrator becomes the last **user-facing** agent.

### 3. Always Runs, Self-Limiting

The Archivist runs every turn but its prompt instructs it to say "No archival needed." and exit immediately when nothing significant happened. This avoids missed events while minimizing cost (single LLM call, no tool calls on quiet turns).

### 4. Write Tools Move to Archivist

When `multi_agent_enabled=True`, memory/graph **write** tools are removed from the Narrator. Read tools stay on the Narrator for narrative context. When multi-agent is disabled, the Narrator keeps all tools (backward-compatible).

---

## Files to Modify/Create

| Action | File | Change |
|--------|------|--------|
| CREATE | `backend/app/services/archivist_agent.py` | New ArchivistAgent class |
| MODIFY | `backend/app/services/agent_base.py` | Add `is_user_facing` property to BaseAgent |
| MODIFY | `backend/app/services/agent_orchestrator.py` | Suppression based on `is_user_facing`, suppress errors from silent agents |
| MODIFY | `backend/app/services/narrator_agent.py` | Remove write tools when multi-agent enabled |
| MODIFY | `backend/app/dependencies.py` | Add ArchivistAgent to pipeline |

---

## Step-by-Step Implementation

### Step 1: Add `is_user_facing` to BaseAgent

**File**: `backend/app/services/agent_base.py`

Add to `BaseAgent` class (after `should_run`):

```python
@property
def is_user_facing(self) -> bool:
    """Whether this agent's text output should stream to the user."""
    return True
```

No change to `SingleAgent` — it inherits the default `True`.

### Step 2: Update Orchestrator Suppression Logic

**File**: `backend/app/services/agent_orchestrator.py`

Replace position-based suppression (`is_last`) with `is_user_facing`-based logic:

1. Before the loop, find the index of the **last user-facing agent**:
   ```python
   last_uf_idx = max(
       (seq for seq, (_, a) in enumerate(active_agents) if a.is_user_facing),
       default=len(active_agents) - 1,
   )
   ```

2. In the event loop, replace `if not is_last` with:
   ```python
   is_streaming = (seq == last_uf_idx and agent.is_user_facing)
   ```

3. Suppress `token`/`done` from non-streaming agents (non-final user-facing OR all non-user-facing).

4. Suppress `error` events from non-user-facing agents (log them instead):
   ```python
   if event.event == "error" and not agent.is_user_facing:
       logger.warning("Silent agent '%s' error: %s", agent.name, event_data)
       continue
   ```

### Step 3: Create ArchivistAgent

**New file**: `backend/app/services/archivist_agent.py`

Following the exact pattern of `narrator_agent.py` and `rules_engine_agent.py`:

**Tool set** (`_ARCHIVIST_TOOLS`, 18 tools):

| Category | Tools |
|----------|-------|
| Memory (write) | `archive_event` |
| Memory (read) | `search_memory`, `recall_context`, `get_session_summary`, `end_session` |
| Graph (write) | `add_relationship` |
| Graph (read) | `query_relationships`, `get_entity_relationships`, `get_entity_context` |
| NPC state | `npc_remember`, `update_npc_relationship` |
| Quest tracking | `update_quest_objective` |
| Read-only state | `get_game_state`, `get_character`, `list_characters`, `get_inventory`, `get_quest_journal`, `look_around` |

**Class overrides**:
- `name` → `"archivist"`
- `allowed_tool_names` → `_ARCHIVIST_TOOLS`
- `is_user_facing` → `False`
- `build_system_prompt_async(ctx)` → 4-layer prompt

**System prompt (4 layers)**:

**Layer 1 — Identity** (~180 tokens):
```
/nothink
You are the Archivist for a D&D 5e game. You maintain the game's long-term memory and knowledge graph.

ROLE:
- Review what happened this turn and decide what is worth remembering.
- Use archive_event for significant story beats, discoveries, combat outcomes, player decisions.
- Use add_relationship to track connections between characters, NPCs, locations, quests.
- Use npc_remember to record events NPCs witnessed or participated in.
- Use update_npc_relationship when NPC attitudes changed.
- Use update_quest_objective when quest progress was made.

RULES:
- ONLY archive genuinely significant events (importance >= 5). Skip routine actions.
- Before archiving, use search_memory to check for duplicates.
- Importance: 2-3 minor, 5-6 moderate, 8-10 major story beats.
- Extract entity names accurately from conversation context.
- If nothing significant happened, respond "No archival needed." and stop.
- Never narrate or describe scenes. You are a silent bookkeeper.
- Keep tool calls to a maximum of 3-4 per turn.
```

**Layer 2** — Reuse `_build_layer2_jit_rules(phase)` from prompt_builder.py
**Layer 3** — Reuse `_build_layer3_state(session, game_session)` from prompt_builder.py

**Layer 4 — Format** (~40 tokens):
```
FORMAT:
- Respond with a brief summary of what you archived (not shown to player).
- If nothing to archive: "No archival needed."
- Never use dramatic narration. Be concise and factual.
```

**Prompt builder** follows same pattern as `_build_narrator_prompt` / `_build_rules_engine_prompt`:
```python
async def _build_archivist_prompt(ctx: AgentContext) -> str:
    layer1 = _build_archivist_layer1()
    try:
        game_session = await get_or_create_session(ctx.session, ctx.conversation_id)
        phase = ctx.phase or GamePhase.EXPLORATION
        layer2 = _build_layer2_jit_rules(phase)
        layer3 = await _build_layer3_state(ctx.session, game_session)
    except Exception:
        logger.warning("Archivist prompt: layers 2-3 failed", exc_info=True)
        layer2, layer3 = "", ""
    layer4 = _build_archivist_layer4()
    return f"{layer1}\n{layer2}\n{layer3}\n{layer4}"
```

### Step 4: Narrow Narrator Tools When Multi-Agent Active

**File**: `backend/app/services/narrator_agent.py`

Define the tools that move exclusively to the Archivist:

```python
_ARCHIVIST_EXCLUSIVE_TOOLS: frozenset[str] = frozenset({
    "archive_event", "add_relationship",
    "npc_remember", "update_npc_relationship",
    "update_quest_objective",
})
```

Update the Narrator's `allowed_tool_names` property:

```python
@property
def allowed_tool_names(self) -> frozenset[str] | None:
    if settings.multi_agent_enabled:
        return _NARRATOR_FINAL_TOOLS - _ARCHIVIST_EXCLUSIVE_TOOLS
    return _NARRATOR_FINAL_TOOLS
```

Also update the combat narration addendum to remove the mention of `archive_event` (since the Narrator no longer has it in multi-agent mode).

### Step 5: Wire Into Pipeline

**File**: `backend/app/dependencies.py`

```python
from app.services.archivist_agent import ArchivistAgent

@lru_cache
def get_orchestrator() -> AgentOrchestrator:
    return AgentOrchestrator(agents=[
        RulesEngineAgent(),   # COMBAT only
        NarratorAgent(),      # All phases (user-facing)
        ArchivistAgent(),     # All phases (silent, last)
    ])
```

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| **Token budget pressure** (3 agents share budget) | Archivist has small tool set (18 vs 26), lightweight prompt (~270 tokens). "No archival needed" exit adds only 1 LLM call. |
| **Latency** (+1 LLM call per turn) | Quick exit path when nothing to archive. Future: skip via `should_run()` heuristic. |
| **Spurious writes** (bad memories/relationships) | Prompt instructs `search_memory` check before archiving; importance >= 5 threshold. Phase 3.3 auto-extraction already handles most relationships. |
| **think=False compliance** | Inherited from `SingleAgent.run()` line 127 — already passes `{"think": False}`. |
| **Archivist errors breaking UX** | Runs after Narrator (user already has response). Non-user-facing errors are logged but suppressed from frontend. |
| **Backward compatibility** | Narrator keeps all tools when `multi_agent_enabled=False`. Archivist only instantiated in orchestrator (not used in single-agent path). |

---

## Verification (Chrome MCP End-to-End)

1. Set `MULTI_AGENT_ENABLED=True` in environment
2. Start backend + frontend dev servers
3. Create new conversation, enable RPG tools
4. **Test 1 — Game start**: "Start a D&D game with a character named Kaelen, level 3 elf ranger"
   - Verify backend logs show: `agent_start: rules_engine` (skipped — not COMBAT), `agent_start: narrator`, `agent_start: archivist`
   - Verify chat shows Narrator text only (no Archivist bookkeeping text)
5. **Test 2 — Significant event**: "Kaelen enters the dark cave and finds a mysterious glowing amulet"
   - Verify Archivist calls `archive_event` in backend logs
   - Check DB: `SELECT * FROM game_memories WHERE memory_type='episodic'` has new record
6. **Test 3 — Quiet turn**: "Kaelen looks around the tavern"
   - Verify Archivist responds "No archival needed" (visible in logs, not in chat)
7. **Test 4 — Combat**: Enter combat, verify all 3 agents run in order
   - RulesEngine resolves mechanics → Narrator narrates → Archivist archives combat outcome
8. **Test 5 — Narrator tool scope**: Verify Narrator logs show `archive_event` NOT in tool list
9. **Test 6 — Single-agent fallback**: Set `MULTI_AGENT_ENABLED=False`, verify Narrator still has all tools including `archive_event`
