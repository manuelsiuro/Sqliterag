# Phase 3.2: `get_entity_context` Tool — Unified Entity Dossier

## Context

Phase 3.1 is complete (commit `a65a3ec`). It delivered the `rpg_relationships` table, ORM model, and 3 relationship tools (`add_relationship`, `query_relationships`, `get_entity_relationships`), plus the frontend `RelationshipRenderer`.

The original AGENTS_FEATURE.md Phase 3.2 spec called for `add_relationship`, `query_relationships`, and `get_entity_context`. Since Phase 3.1 already implemented the first two, **Phase 3.2's remaining deliverable is `get_entity_context`** — the tool that compiles a compact context summary by aggregating:

1. **Entity DB record** — character stats, NPC disposition/memory, location details, quest status, item properties
2. **Knowledge graph** — relationships from `rpg_relationships` (depth=1)
3. **Game memories** — entries from `game_memories` mentioning the entity

This is the bridge between the knowledge graph (Phase 3) and context engineering (Phase 1), making entity information available in a single tool call.

## Architecture

```
get_entity_context(entity_name, entity_type?)
    |
    v
[1] _auto_detect_entity()       (reuse from relationships.py)
    -> entity_type, entity_id
    |
    +----------+----------+
    |          |          |
    v          v          v
[2] Fetch   [3] Query  [4] Search
    ORM      graph       memories
    record   depth=1     top_k=5
    |          |          |
    v          v          v
  details{}  rels[]    mems[]
    |          |          |
    +---- merge into -----+
    |
    v
  Build compact text summary
    |
    v
  {"type": "entity_context", ...}
    |
    v
  Frontend: EntityContextRenderer
```

## Files to Modify/Create

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/services/builtin_tools/relationships.py` | Modify | Add `get_entity_context` function + new imports |
| `backend/app/services/builtin_tools/__init__.py` | Modify | Import + register `get_entity_context` |
| `backend/app/database.py` | Modify | Add tool seed definition |
| `backend/app/services/prompt_builder.py` | Modify | Add to `RPG_TOOL_NAMES` + `_CORE_TOOLS` |
| `backend/app/services/tool_service.py` | Modify | Add argument aliases |
| `frontend/src/components/tools/renderers/EntityContextRenderer.tsx` | **Create** | New renderer for `entity_context` type |
| `frontend/src/components/tools/renderers/index.ts` | Modify | Register `entity_context` type |

## Implementation Steps

### Step 1: Add Imports to relationships.py

**File**: `backend/app/services/builtin_tools/relationships.py` (lines 8-15)

Expand the `_common` import block to include entity lookup helpers needed for fetching DB records:

```python
from app.services.builtin_tools._common import (
    AsyncSession,
    character_to_dict,          # NEW
    get_character_by_name,      # NEW
    get_location_by_name,       # NEW
    get_npc_by_name,            # NEW
    get_or_create_session,
    get_quest_by_title,         # NEW
    json,
    resolve_entity,
    resolve_entity_name,
    select,
)
```

### Step 2: Add `get_entity_context` Function

**File**: `backend/app/services/builtin_tools/relationships.py` (after line 253)

```python
async def get_entity_context(
    entity_name: str,
    entity_type: str = "",
    *,
    session: AsyncSession,
    conversation_id: str,
    embedding_service=None,
) -> str:
    """Compile a comprehensive context dossier for any game entity."""
```

**Logic**:

1. **Resolve entity** — reuse `_auto_detect_entity()` or `resolve_entity()` directly
2. **Fetch entity details** — branch on `entity_type`:
   - `character`: `get_character_by_name()` -> `character_to_dict()` (select key fields)
   - `npc`: `get_npc_by_name()` -> extract `name, description, disposition, familiarity, location (resolve name), memory (JSON parsed)`
   - `location`: `get_location_by_name()` -> extract `name, description, biome, exits (resolve names), environment`
   - `quest`: `get_quest_by_title()` -> extract `title, description, status, objectives, rewards`
   - `item`: `select(Item).where(Item.name.ilike(...))` -> extract `name, item_type, description, weight, value_gp, rarity, properties`
3. **Fetch relationships** — call existing `query_relationships()` with `depth=1`, parse JSON result
4. **Search memories** — if `embedding_service` available, call `memory_service.search_with_stanford_scoring()` with `top_k=5`, convert via `_memory_to_event()` pattern
5. **Build compact summary** — token-efficient text (< 300 chars):
   - Format: `"{Name} ({Type}, {key_attrs}). Relations: {rel1}, {rel2}. Recent: {mem1}."`
6. **Return JSON** with `type: "entity_context"`

**Response schema**:
```json
{
  "type": "entity_context",
  "entity": {"name": "Grim", "type": "npc"},
  "details": { /* type-specific fields */ },
  "relationships": [ /* edge objects from query_relationships */ ],
  "relationship_count": 3,
  "memories": [ /* {content, memory_type, importance, entities, created_at} */ ],
  "memory_count": 2,
  "summary": "Grim (NPC, friendly acquaintance) at Rusty Tavern. Relations: trusts Arin (65), knows_about Thieves Guild (80). Recent: revealed guild location."
}
```

### Step 3: Register in `__init__.py`

**File**: `backend/app/services/builtin_tools/__init__.py`

1. **Import** (lines 54-58): Add `get_entity_context` to the relationships import block
2. **Registry** (lines 129-131): Add `"get_entity_context": get_entity_context,`

Tool count: 46 -> 47.

### Step 4: Add Tool Seed in database.py

**File**: `backend/app/database.py` (after `get_entity_relationships` seed definition)

```python
"get_entity_context": {
    "description": "Get a comprehensive context summary for any game entity. Compiles the entity's database record, knowledge graph relationships, and relevant memories into a single view. Use to understand everything known about a character, NPC, location, quest, or item.",
    "parameters_schema": _schema(["entity_name"], {
        "entity_name": {"type": "string", "description": "Name of the entity to look up"},
        "entity_type": {"type": "string", "description": "Type: character, npc, location, quest, item. Auto-detected if empty."},
    }),
    "execution_type": "builtin",
    "execution_config": _config("get_entity_context"),
},
```

### Step 5: Update prompt_builder.py

**File**: `backend/app/services/prompt_builder.py`

1. **RPG_TOOL_NAMES** (line 47): Add `"get_entity_context"` to Knowledge Graph section
2. **_CORE_TOOLS** (line 127): Add `"get_entity_context"` — available in all phases since it's a read-only context tool

### Step 6: Add Argument Aliases in tool_service.py

**File**: `backend/app/services/tool_service.py` (lines 19-30)

Add entry:
```python
"get_entity_context": {"name": "entity_name", "type": "entity_type"},
```

Same alias pattern as `query_relationships` and `get_entity_relationships`.

### Step 7: Create EntityContextRenderer

**New file**: `frontend/src/components/tools/renderers/EntityContextRenderer.tsx`

Separate renderer (not extending RelationshipRenderer) because `entity_context` contains 3 distinct visual sections: details + relationships + memories.

**Component structure**:
```
EntityContextRenderer({ data })
  |
  +-- Error check -> red text early return
  |
  +-- Header: type icon + entity name (bold) + type badge pill
  |
  +-- Details section (branches by entity_type):
  |   - character: class/level, HP bar, AC, key abilities
  |   - npc: disposition, familiarity, description, location
  |   - location: biome badge, description, exit pills
  |   - quest: status badge, description, objectives
  |   - item: rarity-colored border, type, properties
  |
  +-- Relationships section (if any):
  |   - Header: "Connections (N)"
  |   - Edge list: direction arrow + rel pill + entity name + strength bar
  |
  +-- Memories section (if any):
  |   - Header: "Memories (N)"
  |   - Memory entries: type badge + importance dot + content
  |
  +-- Summary: gray italic compact text (collapsible)
```

**Styling**:
- Card container: `bg-gray-800/30 rounded-lg px-3 py-2.5 border border-gray-700/30 space-y-2`
- Entity type colors: character=blue, npc=purple, location=amber, quest=emerald, item=rarity-based
- Reuse `ENTITY_ICONS` pattern, `REL_CATEGORY_COLORS` pattern, `StrengthBar` pattern (duplicate small constants per project convention)
- ~200-250 lines

### Step 8: Register Renderer in index.ts

**File**: `frontend/src/components/tools/renderers/index.ts` (after line 89, Phase 11 section)

```typescript
import { EntityContextRenderer } from "./EntityContextRenderer";
registerToolRenderer("entity_context", EntityContextRenderer);
```

## Key Design Decisions

1. **Reuse `query_relationships()` via internal call** — simpler than extracting shared helpers. One extra JSON roundtrip is negligible for a user-initiated tool.
2. **Graceful memory degradation** — if `embedding_service` is None, memories section is empty. FTS fallback still works if available.
3. **Separate renderer** — `entity_context` has 3 distinct sections (details + relationships + memories) that would bloat RelationshipRenderer. Follows MemoryRenderer precedent.
4. **Always in `_CORE_TOOLS`** — read-only tool useful in all phases (combat, exploration, social).

## Edge Cases

- **Item entities are not session-scoped**: Items have no `session_id`. `resolve_entity` already handles this. Memory search is session-scoped, which is correct.
- **NPC location_id**: Stored as UUID, must resolve to display name via `resolve_entity_name(session, "location", npc.location_id)`.
- **Large relationship/memory counts**: Relationships limited to depth=1, memories to top_k=5. Frontend shows "N more..." for overflow.
- **Entity not found**: Returns `{"type": "entity_context", "error": "Entity 'X' not found."}`.

## Verification

1. **Backend startup**: Restart uvicorn, verify "Seeded built-in tool: get_entity_context" in logs. Tool count = 47.
2. **Schema check**: `sqlite3 backend/sqliterag.db "SELECT name FROM tools WHERE name='get_entity_context'"`
3. **Chrome MCP end-to-end**:
   - Start game, create character "Arin" (fighter), create NPC "Grim", create quest "Find Merchant"
   - Add relationship: "Grim trusts Arin with strength 65"
   - Archive memory: "Grim told Arin about the thieves guild"
   - Test: "What do we know about Grim?" -> should call `get_entity_context`
   - Verify renderer shows: NPC header (purple), details, relationship with strength bar, memory entry, compact summary
   - Test auto-detection: "Get context for Arin" -> auto-detects as character
   - Test error: "Get context for NonExistentEntity" -> red error text
   - Test character type: details show HP, class, level, AC
4. **Phase filtering**: During combat, verify `get_entity_context` IS available (it's in `_CORE_TOOLS`)
5. **Snapshot**: `take_snapshot` to verify DOM structure and styling
