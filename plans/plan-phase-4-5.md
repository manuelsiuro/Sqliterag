# Phase 4.5-4.7: Agent Communication & PALADIN Self-Correction

## Context

Phases 4.1-4.4 are complete: the multi-agent pipeline has 3 specialized agents (RulesEngine, Narrator, Archivist) running sequentially via `AgentOrchestrator`. Each already has tailored 4-layer system prompts (Phase 4.5 is done). What remains:

- **Phase 4.6**: Explicit agent communication — structured handoff summaries between agents
- **Phase 4.7**: PALADIN self-correction — retry when LLM narrates without calling required tools

**Problem (4.6)**: Downstream agents see ALL raw messages from prior agents (verbose tool JSON consuming 300-500 tokens) but have no structured summary. The small qwen3.5:9b model struggles to extract key facts from raw JSON in the message stream.

**Problem (4.7)**: qwen3.5:9b sometimes narrates mechanical actions ("You swing your sword and deal 7 damage!") without calling tools. Game state never updates. PALADIN paper shows self-correction raises tool success from 17.5% to 78.7% on similar-scale models.

---

## Phase 4.6: Agent Communication (Handoff Summaries)

### Step 1: Add `agent_handoffs` field to AgentContext

**File**: `backend/app/services/agent_context.py` (line 49)

Add to dataclass:
```python
agent_handoffs: dict[str, str] = field(default_factory=dict)
```

### Step 2: Create `backend/app/services/handoff.py` (~120 lines)

New file with two main functions:

**`summarize_tool_result(tool_name: str, result_json: str) -> str`**
- Parse JSON, dispatch on `"type"` field
- Type-specific one-line extractors (`_SUMMARIZERS` registry):
  - `attack_result` -> `"Arin attacks Goblin: d20+5=18 vs AC 15, HIT. 7 slashing."`
  - `spell_cast` -> `"Elara casts Fireball: 28 fire damage."`
  - `check_result` -> `"Arin Perception: d20+3=17 vs DC 15, SUCCESS."`
  - `damage_result` / `heal_result` -> `"{target} takes/heals {amount}. HP {hp}."`
  - `death_save` -> `"{character} death save: SUCCESS (2/3)."`
  - `initiative_order` -> `"Initiative: Arin(18), Goblin(12)."`
  - `location` -> `"At Dark Forest. Exits: north->Village."`
  - `npc_info` / `quest_info` / `memory_archived` -> compact one-liners
  - Fallback: `"{tool_name}: completed"`
- Each summarizer <= 30 tokens

**`build_handoff_summary(agent_name: str, messages: list[dict], start_index: int) -> str | None`**
- Scan `messages[start_index:]` for tool-role messages
- Summarize each via `summarize_tool_result()`
- Return formatted block or `None` if no tool results:
```
[HANDOFF from rules_engine]
- Arin attacks Goblin: d20+5=18 HIT, 7 slashing. Goblin HP 3/10.
- Next turn: Goblin (initiative 12).
[/HANDOFF]
```

### Step 3: Record message index + build handoff in orchestrator

**File**: `backend/app/services/agent_orchestrator.py`

In `run_pipeline()`, around line 73 (before `agent.run()`):
```python
msg_start_idx = len(ctx.messages)
```

After line 105 (after agent finishes):
```python
from app.services.handoff import build_handoff_summary
handoff = build_handoff_summary(agent.name, ctx.messages, msg_start_idx)
if handoff:
    ctx.agent_handoffs[agent.name] = handoff
```

### Step 4: Inject handoff message before each downstream agent

**File**: `backend/app/services/agent_orchestrator.py`

New helper `_inject_handoff_message(ctx, handoff_text)`:
- Strip any previous handoff message (marker `_handoff: True`) to prevent accumulation
- Find last user-message index in `ctx.messages`
- Insert `{"role": "system", "content": handoff_text, "_handoff": True}` before it
- Update `ctx.budget.conversation_history_tokens`

Call it after system prompt replacement, before `agent.run()`:
```python
if ctx.agent_handoffs:
    handoff_text = "\n".join(ctx.agent_handoffs.values())
    _inject_handoff_message(ctx, handoff_text)
```

### Step 5: Update agent prompts to reference handoffs

**File**: `backend/app/services/narrator_agent.py` (lines 130-135)
- Update combat addendum: `"See the [HANDOFF from rules_engine] message for a summary of mechanical outcomes."`

**File**: `backend/app/services/archivist_agent.py` (line 95)
- Add to Layer 1: `"- Check [HANDOFF] messages for a summary of what happened this turn.\n"`

### Token Impact
- Handoff summary per agent: ~50-150 tokens (compact one-liners)
- Raw messages remain in `ctx.messages` (conservative v1 — no stripping)
- Net cost: +100-150 tokens per turn in multi-agent mode

---

## Phase 4.7: PALADIN Self-Correction

### Step 1: Add config flags

**File**: `backend/app/config.py` (after line 111)

```python
# PALADIN self-correction (Phase 4.7)
paladin_enabled: bool = True
paladin_max_retries: int = 2
```

### Step 2: Create `backend/app/services/paladin.py` (~100 lines)

New file with two functions:

**`should_self_correct(agent_name, correction_mode, phase, content, user_message) -> bool`**

Three correction modes:
- `"minimal"` (Archivist): Never correct. "No archival needed." is legitimate text-only.
- `"aggressive"` (RulesEngine): Always correct if non-empty content during COMBAT. Exception: short pass-through responses (<50 chars like "The narrator handles storytelling.").
- `"moderate"` (Narrator, SingleAgent default): Correct only if content contains mechanical action keywords without tool calls.

Keyword patterns for moderate mode (`_MECHANICAL_PATTERNS`):
```python
[
    r"\b(?:attacks?|strikes?|swings?)\b.*\b(?:hits?|misses?|deals?\s+\d+|damage)\b",
    r"\b(?:rolls?\s+(?:a\s+)?d\d+)\b",
    r"\btakes?\s+\d+\s+(?:damage|points?\s+of)\b",
    r"\b(?:heals?|recovers?)\s+\d+\s+(?:hit\s+points?|hp)\b",
    r"\bcasts?\s+\w+\s+(?:spell|on)\b",
    r"\bmakes?\s+a\s+\w+\s+(?:check|save|saving\s+throw)\b",
    r"\brolls?\s+initiative\b",
    r"\bdeath\s+sav(?:e|ing)\b",
]
```

Returns True if phase is not None AND at least one pattern matches (moderate) or non-empty content (aggressive).

**`build_correction_message(content, attempt, phase) -> dict`**

Returns an ephemeral system message (never saved to DB):
```python
{
    "role": "system",
    "content": (
        "[SELF-CORRECTION REQUIRED]\n"
        "Your previous response described mechanical game actions without calling tools.\n"
        f"Your response was: \"{content[:300]}\"\n\n"
        "You MUST use tool calls for attacks, damage, ability checks, spells, dice, and movement.\n"
        "Retry now. Call the appropriate tool(s)."
    )
}
```

On attempt 2, append: `"This is your FINAL attempt. You MUST call at least one tool."`

Also export `CORRECTION_MARKER = "[SELF-CORRECTION REQUIRED]"` for cleanup.

### Step 3: Add `correction_mode` property to BaseAgent

**File**: `backend/app/services/agent_base.py` (after line 57)

```python
@property
def correction_mode(self) -> str:
    """Self-correction aggressiveness: 'aggressive', 'moderate', 'minimal'."""
    return "moderate"
```

### Step 4: Insert self-correction gate in SingleAgent.run()

**File**: `backend/app/services/agent_base.py`

Before the `for _round` loop (line 136), add:
```python
correction_attempts = 0
```

In the `else` branch (line 255), BEFORE the streaming block (line 257), insert:
```python
# PALADIN self-correction gate
if (
    settings.paladin_enabled
    and correction_attempts < settings.paladin_max_retries
    and should_self_correct(
        self.name, self.correction_mode,
        ctx.phase, content, ctx.user_message,
    )
):
    correction_attempts += 1
    correction_msg = build_correction_message(content, correction_attempts, ctx.phase)
    ctx.messages.append(correction_msg)
    ctx.budget.conversation_history_tokens += estimate_message_tokens(correction_msg)
    logger.info(
        "PALADIN correction #%d/%d for agent '%s'",
        correction_attempts, settings.paladin_max_retries, self.name,
    )
    yield ServerSentEvent(
        data=json.dumps({"agent": self.name, "attempt": correction_attempts}),
        event="self_correction",
    )
    continue  # Re-enter loop for another LLM call
```

After max retries exhausted, the existing streaming logic runs (graceful degradation).

### Step 5: Override correction_mode in specialized agents

**File**: `backend/app/services/rules_engine_agent.py`
```python
@property
def correction_mode(self) -> str:
    return "aggressive"
```

**File**: `backend/app/services/archivist_agent.py`
```python
@property
def correction_mode(self) -> str:
    return "minimal"
```

NarratorAgent inherits `"moderate"` from BaseAgent — no change needed.

### Step 6: Handle `self_correction` SSE event in frontend

**File**: `frontend/src/services/api.ts` (after line 86)

```typescript
} else if (ev.event === "self_correction") {
  console.debug("PALADIN self-correction:", JSON.parse(ev.data));
} else if (ev.event === "agent_done") {
  console.debug("Agent done:", JSON.parse(ev.data));
```

No UI changes — correction is invisible to the user.

### Token Impact
- Each correction attempt: ~200-300 tokens (correction message + quoted failed response)
- Max 2 retries: worst case +400-600 tokens
- Fits within the 8192 budget (existing eviction handles overflow)

---

## File Change Summary

| File | Change | New/Edit |
|------|--------|----------|
| `backend/app/services/handoff.py` | Tool result summarizers + handoff builder | NEW (~120 lines) |
| `backend/app/services/paladin.py` | Detection heuristics + correction message builder | NEW (~100 lines) |
| `backend/app/services/agent_context.py` | Add `agent_handoffs` field | Edit (+1 line) |
| `backend/app/services/agent_orchestrator.py` | Record msg index, build handoff, inject handoff message | Edit (+35 lines) |
| `backend/app/services/agent_base.py` | Add `correction_mode` property + self-correction gate in `run()` | Edit (+25 lines) |
| `backend/app/services/narrator_agent.py` | Update combat addendum to reference handoff | Edit (~3 lines) |
| `backend/app/services/archivist_agent.py` | Add handoff reference + `correction_mode = "minimal"` | Edit (+5 lines) |
| `backend/app/services/rules_engine_agent.py` | Add `correction_mode = "aggressive"` | Edit (+4 lines) |
| `backend/app/config.py` | Add `paladin_enabled`, `paladin_max_retries` | Edit (+3 lines) |
| `frontend/src/services/api.ts` | Handle `self_correction` + `agent_done` SSE events | Edit (+4 lines) |

---

## Implementation Order

1. **Phase 4.6 first** (handoff summaries):
   - `agent_context.py` -> `handoff.py` -> `agent_orchestrator.py` -> `narrator_agent.py` + `archivist_agent.py`
2. **Phase 4.7 second** (PALADIN):
   - `config.py` -> `paladin.py` -> `agent_base.py` -> `rules_engine_agent.py` + `archivist_agent.py` -> `frontend api.ts`
3. **Commit each phase separately**

---

## Verification

### Phase 4.6 Verification
1. Set `MULTI_AGENT_ENABLED=true` in `.env`
2. Start a combat session, send "I attack the goblin"
3. Check backend logs for handoff summaries being built
4. Verify Narrator sees `[HANDOFF from rules_engine]` in its context
5. Chrome MCP: Take snapshot, verify combat narration references the mechanical outcomes

### Phase 4.7 Verification
1. Set `PALADIN_ENABLED=true` (default)
2. Start combat, send "I attack the goblin"
3. If model narrates without tools, verify backend logs show `PALADIN correction #1`
4. Verify the final response includes tool_result events (attack, damage)
5. Test graceful degradation: if correction fails twice, text still streams
6. Test Archivist bypass: verify "No archival needed." never triggers correction
7. Test non-combat: send "Tell me about this town" — verify no false positive corrections
8. Chrome MCP: Full multi-turn test with screenshots

### Regression Safety
- Single-agent mode (`MULTI_AGENT_ENABLED=false`): PALADIN still works (SingleAgent inherits moderate mode), handoffs are not generated (orchestrator not used)
- `PALADIN_ENABLED=false`: No corrections fire, existing behavior preserved
- All existing tool validation (fuzzy match, alias remap, arg stripping) unchanged
