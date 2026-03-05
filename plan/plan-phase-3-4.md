# Phase 3.4: Graph-to-Context Compiler

## Summary
Injects a compact relationship summary from the knowledge graph (`rpg_relationships`) into the dynamic system prompt's Layer 3 (State Injection). The LLM knows about entity connections every turn without tool calls.

## Files Modified
- `backend/app/config.py` — 3 config fields: `graph_context_enabled`, `graph_context_strength_threshold`, `graph_context_max_relations`
- `backend/app/services/prompt_builder.py` — `_compile_graph_context()` helper + entity_names map in `_build_layer3_state()` + updated truncation cascade
- `backend/tests/test_prompt_builder.py` — `TestGraphContext` class (4 tests)

## Design
- Single batch query against `rpg_relationships` for scene entities (both endpoints must be in scene)
- Names resolved from in-memory map (zero additional DB queries)
- Compact format: `Relations: Grim knows(70) Arin | Arin party_member(100) Mira`
- Truncation cascade: Relations dropped first → quests → NPCs → hard cut
- Config toggle: `GRAPH_CONTEXT_ENABLED=false` disables the feature
