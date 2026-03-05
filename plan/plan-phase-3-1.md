# Phase 3.1: Knowledge Graph — `rpg_relationships` Table + Relationship Tools

## Context

Phases 1.1-2.8 are complete. The system has token counting, dynamic prompts, phase-based tool injection, three-tier memory with hybrid search, session summarization, and MemGPT eviction. However, there is **no structured relationship tracking** between game entities. NPC relationships are limited to global `disposition`/`familiarity` fields — not per-character, not cross-entity.

Phase 3.1 creates a **graph overlay on SQLite** to track relationships between all entity types (characters, NPCs, locations, quests, items). Per the dev philosophy ("every feature must deliver visible, testable value"), this plan includes the table, three tools, and a frontend renderer — enough for a complete vertical slice.

## Architecture

```
rpg_relationships — lightweight graph overlay
  |
  |-- Polymorphic edges: source_type/source_id -> target_type/target_id
  |-- No FK constraints on source_id/target_id (they point to different tables)
  |-- Session-scoped via session_id FK -> rpg_game_sessions
  |-- Cascade delete with session
  |
  Tools:
  |-- add_relationship       (create/update edges)
  |-- query_relationships    (traverse graph, depth 1-2)
  |-- get_entity_relationships (compact summary, depth 1)
  |
  Renderer:
  |-- RelationshipRenderer   (handles relationship_added + relationship_graph types)
```

## Files to Modify/Create

| File | Action | Purpose |
|------|--------|---------|
| `backend/app/models/rpg.py` | Modify | Add `Relationship` ORM model + `GameSession.relationships` backref |
| `backend/app/models/__init__.py` | Modify | Export `Relationship` |
| `backend/app/database.py` | Modify | Add composite indexes + 3 tool seed definitions |
| `backend/app/config.py` | Modify | Add `knowledge_graph_enabled` feature flag |
| `backend/app/services/rpg_service.py` | Modify | Add `get_npc_by_name`, `get_quest_by_title`, `resolve_entity`, `resolve_entity_name` helpers |
| `backend/app/services/builtin_tools/_common.py` | Modify | Export new rpg_service helpers |
| `backend/app/services/builtin_tools/relationships.py` | **Create** | 3 tools: `add_relationship`, `query_relationships`, `get_entity_relationships` |
| `backend/app/services/builtin_tools/__init__.py` | Modify | Import + register 3 tools in `BUILTIN_REGISTRY` |
| `backend/app/services/prompt_builder.py` | Modify | Add 3 tools to `RPG_TOOL_NAMES` + phase sets |
| `backend/app/services/tool_service.py` | Modify | Add argument aliases for new tools |
| `frontend/src/components/tools/renderers/RelationshipRenderer.tsx` | **Create** | Renderer for `relationship_added` + `relationship_graph` |
| `frontend/src/components/tools/renderers/index.ts` | Modify | Register 2 renderer types |

## Implementation Steps

### Step 1: ORM Model (`backend/app/models/rpg.py`)

Add `Relationship` class after `GameMemory` (after line 189), following the `InventoryItem` pattern:

```python
class Relationship(Base):
    __tablename__ = "rpg_relationships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("rpg_game_sessions.id", ondelete="CASCADE"))
    source_type: Mapped[str] = mapped_column(String(20))    # character | npc | location | quest | item
    source_id: Mapped[str] = mapped_column(String(36))
    target_type: Mapped[str] = mapped_column(String(20))
    target_id: Mapped[str] = mapped_column(String(36))
    relationship: Mapped[str] = mapped_column(String(50))    # knows_about, allied_with, enemy_of, etc.
    strength: Mapped[int] = mapped_column(Integer, default=50)  # 0-100
    detail: Mapped[str] = mapped_column(Text, default="{}")  # JSON extra context
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())

    game_session: Mapped[GameSession] = relationship(back_populates="relationships")
```

**Notes**:
- No FK on `source_id`/`target_id` — they're polymorphic (point to different tables based on `*_type`)
- Column named `detail` (not `metadata`) to avoid any SQLAlchemy `Base.metadata` shadowing risk
- `updated_at` set via Python on update since SQLite lacks `ON UPDATE CURRENT_TIMESTAMP`

Add to `GameSession` (after line 37):
```python
relationships: Mapped[list[Relationship]] = relationship(back_populates="game_session", cascade="all, delete-orphan")
```

### Step 2: Export Model (`backend/app/models/__init__.py`)

Add `Relationship` to the import from `app.models.rpg` and to `__all__`.

### Step 3: Database Indexes (`backend/app/database.py`)

Add after Phase 2.7 indexes (after line 130):

```python
# Indexes for knowledge graph (Phase 3.1)
for idx_name, idx_cols in [
    ("idx_rel_source", "session_id, source_type, source_id"),
    ("idx_rel_target", "session_id, target_type, target_id"),
    ("idx_rel_type", "session_id, relationship"),
]:
    try:
        await conn.execute(text(
            f"CREATE INDEX IF NOT EXISTS {idx_name} ON rpg_relationships({idx_cols})"
        ))
    except Exception:
        pass
```

### Step 4: Tool Seed Definitions (`backend/app/database.py`)

Add 3 entries to `_builtin_tool_defs()` after `end_session` (before the closing `}`):

```python
# Phase 11 -- Knowledge Graph
"add_relationship": {
    "description": "Create or update a relationship between two game entities (characters, NPCs, locations, quests, items). Tracks social bonds, spatial connections, quest involvement, ownership, and knowledge.",
    "parameters_schema": _schema(["source_name", "source_type", "target_name", "target_type", "relationship"], {
        "source_name": {"type": "string", "description": "Name of the source entity"},
        "source_type": {"type": "string", "description": "Type: character, npc, location, quest, or item"},
        "target_name": {"type": "string", "description": "Name of the target entity"},
        "target_type": {"type": "string", "description": "Type: character, npc, location, quest, or item"},
        "relationship": {"type": "string", "description": "Relationship: knows_about, allied_with, enemy_of, fears, trusts, located_at, quest_giver, owns, guards, seeks, etc."},
        "strength": {"type": "integer", "description": "Strength 0-100 (default 50). 0=weak, 100=defining"},
    }),
    "execution_type": "builtin",
    "execution_config": _config("add_relationship"),
},
"query_relationships": {
    "description": "Query the relationship graph for an entity. Returns connections and optionally 2-hop neighbors. Use to understand who knows what and how entities relate.",
    "parameters_schema": _schema(["entity_name"], {
        "entity_name": {"type": "string", "description": "Name of the entity to query"},
        "entity_type": {"type": "string", "description": "Type: character, npc, location, quest, item. Auto-detected if empty."},
        "relationship_filter": {"type": "string", "description": "Filter by relationship type. Empty for all."},
        "depth": {"type": "integer", "description": "Traversal depth: 1=direct, 2=two-hop. Default 1."},
    }),
    "execution_type": "builtin",
    "execution_config": _config("query_relationships"),
},
"get_entity_relationships": {
    "description": "Get a compact summary of an entity's direct relationships. Simpler than query_relationships.",
    "parameters_schema": _schema(["entity_name"], {
        "entity_name": {"type": "string", "description": "Name of the entity"},
        "entity_type": {"type": "string", "description": "Type: character, npc, location, quest, item. Auto-detected if empty."},
    }),
    "execution_type": "builtin",
    "execution_config": _config("get_entity_relationships"),
},
```

### Step 5: Config Flag (`backend/app/config.py`)

Add after MemGPT settings:
```python
# Knowledge graph (Phase 3.1)
knowledge_graph_enabled: bool = True
```

### Step 6: Entity Resolution Helpers (`backend/app/services/rpg_service.py`)

Add after existing `get_location_by_name` function. These are needed by the relationship tools to resolve entity names to IDs.

```python
async def get_npc_by_name(db: AsyncSession, session_id: str, name: str) -> NPC | None:
    result = await db.execute(
        select(NPC).where(NPC.session_id == session_id, NPC.name.ilike(name))
    )
    return result.scalars().first()

async def get_quest_by_title(db: AsyncSession, session_id: str, title: str) -> Quest | None:
    result = await db.execute(
        select(Quest).where(Quest.session_id == session_id, Quest.title.ilike(title))
    )
    return result.scalars().first()

async def resolve_entity(db: AsyncSession, session_id: str, entity_type: str, name: str) -> tuple[str, str | None]:
    """Resolve entity name -> (type, id). Returns (type, None) if not found."""
    if entity_type == "character":
        e = await get_character_by_name(db, session_id, name)
    elif entity_type == "npc":
        e = await get_npc_by_name(db, session_id, name)
    elif entity_type == "location":
        e = await get_location_by_name(db, session_id, name)
    elif entity_type == "quest":
        e = await get_quest_by_title(db, session_id, name)
    elif entity_type == "item":
        result = await db.execute(select(Item).where(Item.name.ilike(name)))
        e = result.scalars().first()
    else:
        return (entity_type, None)
    return (entity_type, e.id if e else None)

async def resolve_entity_name(db: AsyncSession, entity_type: str, entity_id: str) -> str:
    """Reverse lookup: entity ID -> display name."""
    model_map = {
        "character": (Character, "name"),
        "npc": (NPC, "name"),
        "location": (Location, "name"),
        "quest": (Quest, "title"),
        "item": (Item, "name"),
    }
    entry = model_map.get(entity_type)
    if not entry:
        return entity_id
    model_cls, name_col = entry
    result = await db.execute(select(getattr(model_cls, name_col)).where(model_cls.id == entity_id))
    return result.scalar() or entity_id
```

Imports to add at top of `rpg_service.py`: `NPC`, `Quest`, `Item` (currently only imports `Character`, `GameSession`, `Location`).

### Step 7: Update `_common.py` (`backend/app/services/builtin_tools/_common.py`)

Add new exports from rpg_service:
```python
from app.services.rpg_service import (
    ...,
    get_npc_by_name,
    get_quest_by_title,
    resolve_entity,
    resolve_entity_name,
)
```

### Step 8: Relationship Tools (`backend/app/services/builtin_tools/relationships.py`) — NEW FILE

Three tools following the established async pattern:

#### `add_relationship(source_name, source_type, target_name, target_type, relationship, strength=50)`
- Resolves both entities via `resolve_entity()`
- Returns error if either entity not found
- Checks for existing edge (same session + source + target + relationship) — updates strength + `updated_at` if found
- Creates new `Relationship` row otherwise
- Returns `{"type": "relationship_added", "source": {name, type}, "target": {name, type}, "relationship", "strength", "is_update"}`

#### `query_relationships(entity_name, entity_type="", relationship_filter="", depth=1)`
- Auto-detects entity_type if empty: tries character -> npc -> location -> quest -> item
- Depth 1: simple SELECT where entity is source OR target
- Depth 2: recursive CTE with cycle prevention (track visited entity IDs in a set)
- Resolves all entity IDs back to names via `resolve_entity_name()`
- Returns `{"type": "relationship_graph", "entity": {name, type}, "relationships": [{source_name, source_type, target_name, target_type, relationship, strength, direction}], "depth", "count"}`

#### `get_entity_relationships(entity_name, entity_type="")`
- Thin wrapper: calls same logic as `query_relationships` with depth=1, no filter
- Returns same `"relationship_graph"` type

**Relationship type normalization**: Accept any string, normalize to lowercase + underscores. Define `KNOWN_RELATIONSHIP_TYPES` set for reference but don't reject unknown types.

### Step 9: Register Tools (`backend/app/services/builtin_tools/__init__.py`)

Add imports and registry entries:
```python
from app.services.builtin_tools.relationships import (
    add_relationship,
    get_entity_relationships,
    query_relationships,
)

# In BUILTIN_REGISTRY:
# Phase 11 -- Knowledge Graph
"add_relationship": add_relationship,
"query_relationships": query_relationships,
"get_entity_relationships": get_entity_relationships,
```

### Step 10: Prompt Builder (`backend/app/services/prompt_builder.py`)

1. Add to `RPG_TOOL_NAMES` set:
```python
"add_relationship", "query_relationships", "get_entity_relationships",
```

2. Add read tools to `_CORE_TOOLS` (always available):
```python
"query_relationships", "get_entity_relationships",
```

3. Add write tool to `_PHASE_TOOLS`:
```python
GamePhase.EXPLORATION: frozenset({..., "add_relationship"}),
GamePhase.SOCIAL: frozenset({..., "add_relationship"}),
```

Result: 49 RPG tool names, 16 core tools, EXPLORATION 36, SOCIAL 28, COMBAT 31.

### Step 11: Argument Aliases (`backend/app/services/tool_service.py`)

Add to `_ARGUMENT_ALIASES`:
```python
"add_relationship": {"source": "source_name", "target": "target_name", "type": "relationship", "rel_type": "relationship"},
"query_relationships": {"name": "entity_name", "type": "entity_type"},
"get_entity_relationships": {"name": "entity_name", "type": "entity_type"},
```

### Step 12: Frontend Renderer (`frontend/src/components/tools/renderers/RelationshipRenderer.tsx`) — NEW FILE

Multi-dispatch renderer handling two types:

**`relationship_added`**: Confirmation card with source -> relationship -> target, strength bar, "Updated" badge if `is_update`.

**`relationship_graph`**: Entity-centered view with list of edges, each showing direction (outgoing/incoming), relationship type pill, connected entity name, and strength indicator.

Styling:
- Card container: `bg-gray-800/30 rounded-lg px-3 py-2.5 border border-gray-700/30 space-y-2`
- Entity type icons: sword (character), chat (npc), map-pin (location), scroll (quest), gem (item)
- Relationship category colors:
  - Social (knows, allied, enemy, fears, trusts): purple
  - Spatial (located_at, connected_to, guards): amber
  - Quest (quest_giver, seeks, requires): blue
  - Ownership (owns, carries): green
  - Knowledge (knows_about, witnessed, suspects): cyan
- Strength: thin progress bar (0-100)
- Edge pills: `[icon name] --relationship--> [icon name]` with directional arrows

### Step 13: Register Renderer (`frontend/src/components/tools/renderers/index.ts`)

Add after Phase 10 (Memory):
```typescript
// Phase 11 -- Knowledge Graph
import { RelationshipRenderer } from "./RelationshipRenderer";
registerToolRenderer("relationship_added", RelationshipRenderer);
registerToolRenderer("relationship_graph", RelationshipRenderer);
```

## Verification

1. **Table creation**: Restart backend, check logs for table creation. Run:
   ```bash
   sqlite3 backend/sqliterag.db ".schema rpg_relationships"
   ```
   Confirm table + 3 indexes exist.

2. **Tool seeding**: Check backend logs for "Seeded built-in tool: add_relationship" etc. Tool count should be 48.

3. **Chrome MCP end-to-end test**:
   - Start a game session, create 2 characters and an NPC
   - Ask the LLM: "Note that Arin trusts Gundren the merchant"
   - Verify `add_relationship` is called and `relationship_added` card renders
   - Ask: "What relationships does Arin have?"
   - Verify `query_relationships` or `get_entity_relationships` is called and `relationship_graph` card renders
   - Ask: "Update the trust between Arin and Gundren to very strong"
   - Verify `is_update: true` in the response

4. **Cascade delete**: Delete the conversation, verify relationships are cascade-deleted.

5. **Phase filtering**: During combat, verify `add_relationship` is NOT in the tool list but `query_relationships`/`get_entity_relationships` are (they're in `_CORE_TOOLS`).
