# Phase 3.6: GraphRAG Integration

## Context

Phases 3.1-3.5 built a knowledge graph (rpg_relationships table, auto-extraction, graph-to-context compiler, recursive CTE traversal). Phase 2 built a hybrid memory/RAG system (game_memories + FTS5 + sqlite-vec + RRF + Stanford scoring). These two systems currently operate **independently**:

- **Memory search** (Phase 2): Finds memories by text similarity (FTS5 + vector). Misses structurally related information.
- **Graph context** (Phase 3.4): Injects a "Relations:" line into the system prompt for entities in the current scene. Does not influence memory retrieval.

**The gap**: When a player asks "What does Gundren know?", vector/FTS search finds memories mentioning "Gundren" textually. But it misses memories about the Lost Mine he seeks or his ally Sildar -- entities connected via graph edges, not text overlap. Phase 3.6 bridges this by using graph structure to **expand memory retrieval queries**.

## Approach

Add a `search_graphrag()` function that wraps the existing `search_with_stanford_scoring()` and augments it with graph-derived entity expansion. No new LLM calls -- entity extraction is rule-based (match query against known entity names in DB). Token-neutral -- changes *which* memories are retrieved, not how many.

## Files to Modify

| File | Change |
|------|--------|
| `backend/app/config.py` | Add 5 GraphRAG config flags |
| `backend/app/services/memory_service.py` | Add 3 new functions (~120 lines) |
| `backend/app/services/chat_service.py` | Swap 1 import + 1 function call |

## Implementation Steps

### Step 1: Config flags (`backend/app/config.py`)

Add after line 101 (before `# Server` section):

```python
# GraphRAG integration (Phase 3.6)
graphrag_enabled: bool = True
graphrag_max_expansion_entities: int = 6
graphrag_traversal_depth: int = 1          # 1 = direct neighbors only
graphrag_min_strength: int = 30            # min relationship strength for expansion
graphrag_weight: float = 0.3              # score multiplier for graph-expanded results
```

### Step 2: Entity extraction (`backend/app/services/memory_service.py`)

Add `_extract_entities_from_query()`:

1. Fetch all known entity names for the session in one UNION ALL query across `rpg_characters`, `rpg_npcs`, `rpg_locations`, `rpg_quests` (session-scoped, typically <20 entities)
2. For each entity name, check word-boundary match against the user query using `re.search(r'\b' + re.escape(name) + r'\b', query, re.IGNORECASE)`
3. Return list of `(entity_type, entity_id, entity_name)` tuples

**Reuse**: Follow the same entity resolution pattern as `resolve_entity` in `rpg_service.py:210-240`.

### Step 3: Graph neighborhood expansion (`backend/app/services/memory_service.py`)

Add `_expand_entities_via_graph()`:

1. For all seed entities, batch query `rpg_relationships` for direct neighbors (both outgoing and incoming edges) with `strength >= graphrag_min_strength`
2. Deduplicate against seed entities
3. Resolve neighbor IDs to display names using `resolve_entity_name()` from `rpg_service.py:243`
4. Cap at `graphrag_max_expansion_entities`, sorted by strength descending
5. Return list of additional entity name strings

**Query pattern**: Reuse the batch OR-condition pattern from `_compile_graph_context()` in `prompt_builder.py:253-260` (SQLAlchemy `or_()` with source/target conditions).

### Step 4: Core `search_graphrag()` function (`backend/app/services/memory_service.py`)

Public function with same signature as `search_with_stanford_scoring()` plus `game_session_id` parameter.

Algorithm:
1. Run primary `search_with_stanford_scoring(query, ...)` -- unchanged behavior
2. If `graphrag_enabled` and `game_session_id` provided:
   a. `_extract_entities_from_query(session, game_session_id, query)` -> seed entities
   b. If seeds found: `_expand_entities_via_graph(session, game_session_id, seeds)` -> expansion names
   c. If expansion names found: build augmented query string (space-joined expansion names)
   d. Run secondary `search_with_stanford_scoring(augmented_query, ...)` with same filters
   e. Merge results:
      - Primary results keep full scores
      - Graph-expanded results scores multiplied by `graphrag_weight` (0.3)
      - Deduplicate by memory_id (primary wins on overlap)
      - Sort by final score descending
      - Trim to `top_k`
3. If graphrag disabled or no entities detected: return primary results only (zero overhead)
4. Wrap graph augmentation in try/except -- never breaks primary search

```
search_graphrag("What does Gundren know?")
  |
  +-> search_with_stanford_scoring("What does Gundren know?")  -> [mem_gundren_1, mem_gundren_2]
  |
  +-> _extract_entities_from_query(...)  -> [("npc", "uuid-123", "Gundren")]
  +-> _expand_entities_via_graph(...)    -> ["Lost Mine", "Sildar"]
  +-> search_with_stanford_scoring("Lost Mine Sildar")  -> [mem_lost_mine, mem_sildar]
  |
  +-> Merge + deduplicate + weight + trim to top_k
  |
  v
  Enriched memory list
```

### Step 5: Chat service integration (`backend/app/services/chat_service.py`)

At lines 224-235, change:

```python
# Before:
from app.services.memory_service import search_with_stanford_scoring, get_memories_by_ids
...
memory_results = await search_with_stanford_scoring(
    session, user_message,
    embedding_service=self.embedding_service,
    session_id=game_session.id,
    memory_types=preferred_types,
)

# After:
from app.services.memory_service import search_graphrag, get_memories_by_ids
...
memory_results = await search_graphrag(
    session, user_message,
    embedding_service=self.embedding_service,
    session_id=game_session.id,
    game_session_id=game_session.id,
    memory_types=preferred_types,
)
```

### Step 6: Logging

Add structured logging in the new functions:
- Entity extraction: `"GraphRAG: extracted %d entities from query: %s"`
- Graph expansion: `"GraphRAG: expanded to %d neighbors: %s"`
- Merge: `"GraphRAG: %d primary + %d graph -> %d merged"`

## Key Design Decisions

- **No new LLM calls**: Entity extraction is pure string matching against known DB entities. Critical for 8192-token budget.
- **Depth 1 only**: Direct graph neighbors are sufficient. Depth 2+ would explode entity count with diminishing returns.
- **Weight 0.3 for graph results**: Graph-derived memories are structurally related but may be less directly relevant. Primary search results always dominate.
- **Word-boundary matching**: Prevents "Inn" matching "beginning". Uses `\b` regex boundaries.
- **Fail-safe**: All graph augmentation wrapped in try/except. Errors fall through to standard search.

## Existing Code to Reuse

| What | Where |
|------|-------|
| `resolve_entity_name()` | `rpg_service.py:243` -- resolve entity ID to display name |
| `resolve_entity()` | `rpg_service.py:210` -- resolve entity name to (type, id) |
| Batch OR-condition pattern | `prompt_builder.py:253-260` -- SQLAlchemy `or_()` for relationship queries |
| `Relationship` ORM model | `models/rpg.py:194` -- for SQLAlchemy queries |
| `search_with_stanford_scoring()` | `memory_service.py:546` -- primary search, called internally |

## Verification

1. **Start backend**: `cd backend && uvicorn app.main:app --reload`
2. **Start frontend**: `cd frontend && npm run dev`
3. **Chrome MCP test flow**:
   - Create a game session with characters, NPCs, and locations
   - Build relationships (automatic via tool use: move_to, talk_to_npc, give_item)
   - Archive several events mentioning different entities
   - Ask the LLM about an entity (e.g., "Tell me about Gundren")
   - Verify via snapshot that the response includes information from graph-connected entities
4. **Backward compatibility**: Set `GRAPHRAG_ENABLED=false`, repeat queries, verify identical behavior
5. **Logging**: Check backend logs for GraphRAG extraction/expansion/merge messages
