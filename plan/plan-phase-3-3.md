# Phase 3.3: Auto-Extract Relationships

## Context

Phases 3.1 and 3.2 established a knowledge graph overlay (`rpg_relationships` table) and tools for manual relationship management (`add_relationship`, `query_relationships`, `get_entity_context`). Currently, the LLM must explicitly call `add_relationship` to create graph edges — it rarely does this unprompted. Phase 3.3 adds **automatic, rule-based relationship extraction** as a post-hook after tool execution, so the knowledge graph populates itself as the game progresses.

## Approach: Post-Execution Hook in tool_service.py

A new `relationship_extractor.py` service with a dispatch dict maps tool names to extractor functions. A thin hook in `_execute_builtin()` calls the extractor after each tool returns. No modifications to individual tool modules.

**Why this approach:**
- Single integration point (~8 lines in tool_service.py) instead of editing 12+ tool functions
- Separation of concerns — tool modules stay focused on domain logic
- Easy to disable via config flag
- Silent failures — extraction errors never break tool execution

## Files to Create/Modify

| File | Action | Lines Changed |
|------|--------|---------------|
| `backend/app/services/relationship_extractor.py` | **CREATE** | ~300 lines |
| `backend/app/services/tool_service.py` | **MODIFY** (after line 134) | ~8 lines |
| `backend/app/config.py` | **MODIFY** (after line 90) | ~3 lines |

No new tools, no new frontend renderers, no new ORM models, no migrations needed.

## Step 1: Config Flag (`config.py`)

Add after line 90 (after `knowledge_graph_enabled`):

```python
# Auto-extract relationships from tool results (Phase 3.3)
auto_extract_relationships: bool = True
```

## Step 2: Create `relationship_extractor.py`

### Core Helpers

**`_upsert_edge(session, session_id, source_type, source_id, target_type, target_id, relationship, strength, detail)`**
- Checks for existing edge with same (session_id, source_type, source_id, target_type, target_id, relationship) tuple
- Updates strength if found, creates new Relationship if not
- Pattern extracted from `add_relationship` tool (relationships.py lines 84-120)

**`_remove_edge(session, session_id, source_type, source_id, target_type, target_id, relationship)`**
- Deletes a specific edge if it exists (for unequip/transfer operations)

**`_replace_located_at(session, session_id, source_type, source_id, new_target_id, strength)`**
- Deletes ALL existing `located_at` edges for a source entity, then creates the new one
- Ensures exactly one `located_at` edge per entity at any time

### 12 Per-Tool Extractors

Each receives `(session, session_id, args, result_data)` where `result_data` is parsed JSON.

| # | Tool | Edge Created | Strength | Notes |
|---|------|-------------|----------|-------|
| 1 | `create_npc` | `npc --located_at--> location` | 80 | Only if location provided and != "unknown". Extract `name` and `location` from result (type `npc_info`). |
| 2 | `connect_locations` | `loc1 --connected_to--> loc2` (bidirectional) | 100 | Store direction in `detail` JSON. Extract `location1`, `location2`, `direction`, `reverse_direction` from result (type `location_connected`). |
| 3 | `move_to` | `char --located_at--> location` (replaces old) | 100 | Use `_replace_located_at`. Extract `moved_by` and `name` from result (type `location`). |
| 4 | `give_item` | `char --owns--> item` | 70 | Result is `inventory` type (no item name) — extract `character` and `item_name` from **args**. |
| 5 | `equip_item` | `char --equipped--> item` | 90 | Result is `inventory` type — extract from **args**. Does NOT remove `owns` edge. |
| 6 | `unequip_item` | Remove `equipped` edge, ensure `owns` remains | 70 | Extract from **args**. Call `_remove_edge` for "equipped", `_upsert_edge` for "owns". |
| 7 | `transfer_item` | Remove `from --owns/equipped--> item`, create `to --owns--> item` | 70 | Result has `from`, `to`, `item` keys (type `transfer_result`). Also try args as fallback. |
| 8 | `update_npc_relationship` | `npc --knows--> character` | 20-90 | Strength mapped from `familiarity` field: stranger=20, acquaintance=40, friend=70, close_friend=90. Extract from result (type `npc_info`). |
| 9 | `complete_quest` | `char --completed--> quest` (per PC) | 100 | Iterate `distributed_to` array in result (type `quest_complete`). One edge per character. |
| 10 | `start_combat` | `combatant --fighting--> combatant` (pairwise) | 60 | Iterate `order` array in result (type `initiative_order`). All combatants resolve as "character" type. |
| 11 | `attack` | `attacker --attacked--> target` | 40-90 | Strength = min(90, 40 + damage*3). Extract `attacker`, `target`, `damage` from result (type `attack_result`). |
| 12 | `create_character` | `char --party_member--> char` (bidirectional, per existing PC) | 100 | Only for `is_player=True`. Query existing PCs, create bidirectional edges. |

### Entry Point

```python
async def extract_relationships(
    func_name: str,
    arguments: dict,
    result: str,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> None:
```

- Checks `settings.auto_extract_relationships` flag
- Looks up `func_name` in `_EXTRACTORS` dispatch dict
- Parses result JSON, skips if error or invalid
- Resolves `session_id` via `get_or_create_session`
- Cleans injected dependencies from arguments
- Calls extractor in try/except (logs warning, never raises)

## Step 3: Hook in `tool_service.py`

After line 134 (`result = await result`), before `return result` on line 135:

```python
# Phase 3.3: Auto-extract relationship edges
if session is not None and conversation_id is not None:
    try:
        from app.services.relationship_extractor import extract_relationships
        await extract_relationships(
            func_name, arguments, result,
            session=session, conversation_id=conversation_id,
        )
    except Exception:
        logger.debug("Relationship extraction hook error for %s", func_name, exc_info=True)
```

Lazy import avoids circular imports. Double try/except (outer here + inner in extractor) for belt-and-suspenders safety.

## Key Reusable Code

| What | Where | Used For |
|------|-------|----------|
| `Relationship` ORM model | `backend/app/models/rpg.py:193-215` | Creating edge objects |
| `resolve_entity()` | `backend/app/services/rpg_service.py:225` | Name-to-ID resolution in extractors |
| `get_or_create_session()` | `backend/app/services/rpg_service.py` | Getting session_id from conversation_id |
| `_normalize_relationship()` | `backend/app/services/builtin_tools/relationships.py:27` | Consistent edge naming (import or replicate) |
| Upsert pattern | `backend/app/services/builtin_tools/relationships.py:84-120` | Model for `_upsert_edge` helper |

## Edge Cases

1. **Error results**: Every extractor returns early on `result.get("error")`. Top-level also checks before dispatch.
2. **Missing entities**: `resolve_entity` returns `(type, None)` for unfound entities. All extractors guard with `if id1 and id2`.
3. **Duplicate edges**: `_upsert_edge` queries before inserting — updates strength on existing edges.
4. **located_at uniqueness**: `_replace_located_at` deletes ALL old `located_at` edges before creating the new one.
5. **give_item/equip_item/unequip_item return inventory type**: Extract entity names from `args`, not `result`.
6. **transfer_item uses "from"/"to" keys**: Not "from_character"/"to_character". Check both result and args.
7. **Combat edges are permanent**: `end_combat` does NOT auto-remove `fighting` edges (historical markers). Can be added later if desired.
8. **Transaction atomicity**: Same session as parent tool — commits/rolls back together.

## Verification

1. **Backend startup**: `uvicorn` starts without import errors
2. **Character + party edges**: Create 2 player characters -> `query_relationships` shows bidirectional `party_member` edges
3. **Location graph**: Create 2 locations, `connect_locations` -> `connected_to` edges appear (bidirectional with direction detail)
4. **Movement**: `move_to` character to location A, then B -> only one `located_at` edge (to B, not A)
5. **NPC at location**: `create_npc` with location -> `located_at` edge to that location
6. **Inventory**: `give_item` -> `owns` edge. `equip_item` -> `equipped` edge. `unequip_item` -> `equipped` removed, `owns` remains. `transfer_item` -> ownership transferred.
7. **NPC familiarity**: `update_npc_relationship` with familiarity_change="friend" -> `knows` edge with strength 70
8. **Combat**: `start_combat` -> pairwise `fighting` edges. `attack` -> `attacked` edge with damage-scaled strength.
9. **Quest**: `complete_quest` -> `completed` edges for all PCs in `distributed_to`
10. **Config toggle**: Set `AUTO_EXTRACT_RELATIONSHIPS=false` -> no auto edges created
11. **Error resilience**: Tool with invalid data returns its normal error, no extraction crash
12. **Chrome MCP**: Use `get_entity_context` tool in chat to see auto-populated relationships in EntityContextRenderer
