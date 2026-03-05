# Phase 3.5: Recursive CTE Queries for Multi-Hop Graph Traversal

## Summary

Replaced iterative in-memory traversal in `query_relationships()` with a single SQL recursive CTE. Added `find_connections()` tool for path discovery between entities. Frontend renderers added for `connection_paths` and `connection_map` types.

## Changes

| File | Change |
|------|--------|
| `backend/app/config.py` | Added `graph_max_traversal_depth: int = 3` |
| `backend/app/services/builtin_tools/relationships.py` | Rewrote `query_relationships()` with CTE, added `_resolve_names_batch()`, added `find_connections()` |
| `backend/app/services/builtin_tools/__init__.py` | Import + register `find_connections` |
| `backend/app/database.py` | Updated `query_relationships` description, added `find_connections` seed def |
| `backend/app/services/tool_service.py` | Added argument aliases for `find_connections` |
| `backend/app/services/prompt_builder.py` | Added `find_connections` to `RPG_TOOL_NAMES` + `_CORE_TOOLS` |
| `frontend/src/components/tools/renderers/RelationshipRenderer.tsx` | Added `ConnectionPathsCard` + `ConnectionMapCard` sub-renderers |
| `frontend/src/components/tools/renderers/index.ts` | Registered `connection_paths` + `connection_map` types |

## Key Design Decisions

- **CTE over iterative**: Single SQL query replaces N+1 pattern. CTE traverses both directions (outgoing + incoming edges).
- **Cycle prevention**: Path tracking via pipe-delimited `type:id` string with `NOT LIKE` check.
- **Depth cap**: Configurable via `graph_max_traversal_depth` (default 3).
- **Two modes in find_connections**: With `target_name` → path finding; without → discovery map.
- **Backward compatible**: `query_relationships` return format unchanged; `depth` field on edges is additive.
- **Tool count**: 51 (was 50 before `find_connections`).

## Return Types

- `connection_paths`: Source/target entity refs + list of paths (each with nodes + relationship chain)
- `connection_map`: Entity ref + list of connected entities grouped by depth with `via` relationship chain
