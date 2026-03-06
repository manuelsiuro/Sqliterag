# Phase 4.3: Rules Engine Agent

## Summary

Added a strict mechanical agent (`RulesEngineAgent`) that handles D&D 5e combat resolution separately from narrative. During COMBAT, the Rules Engine resolves all mechanics first (attack rolls, damage, death saves, initiative), then the Narrator dramatizes the results.

## Architecture

```
User message arrives
  |
  v
chat_service.py: builds AgentContext, detects phase
  |
  v
AgentOrchestrator.run_pipeline(ctx)
  |
  +-- RulesEngineAgent.should_run(ctx)?
  |     COMBAT: YES -> resolve mechanics (22 tools)
  |     Non-combat: NO -> skip
  |
  +-- NarratorAgent.should_run(ctx)?
        Always YES -> narrate (35 tools; combat addendum when COMBAT)
```

## Changes

### Created
- `backend/app/services/rules_engine_agent.py` — `RulesEngineAgent(SingleAgent)` with combat-only `should_run()`, strict RAW system prompt, 22 mechanical tools

### Modified
- `backend/app/services/agent_base.py` — Added `should_run()` to `BaseAgent` (default `True`); wired `allowed_tool_names` filtering into `SingleAgent.run()`
- `backend/app/services/agent_orchestrator.py` — `should_run` gate skips inactive agents; suppresses `token`/`done` SSE from non-final agents (emits `agent_done` instead); captures agent text into `ctx.agent_outputs`
- `backend/app/services/narrator_agent.py` — Expanded `_NARRATOR_FINAL_TOOLS` (35 tools); activated `allowed_tool_names` filtering; added COMBAT NARRATION MODE addendum
- `backend/app/dependencies.py` — Wired `[RulesEngineAgent(), NarratorAgent()]` into orchestrator

## Key Design Decisions

1. **should_run gate**: Concrete method on `BaseAgent` (not abstract) — defaults to `True`, overridden by `RulesEngineAgent` to check `ctx.phase == GamePhase.COMBAT`
2. **Token/done suppression**: Non-final agents' text tokens and `done` events are hidden from the live stream. Tool events (`tool_calls`, `tool_result`) still pass through for frontend rendering. A separate `agent_done` event marks non-final agent completion.
3. **Two-layer tool filtering**: Phase filtering (Layer 1.4) runs first, then agent-level narrowing (Layer 4.3) runs second — both in `SingleAgent.run()`
4. **Combat handoff**: Narrator calls `start_combat` to initiate. Rules Engine activates on the *next* turn when phase detection picks up `combat_state`.
