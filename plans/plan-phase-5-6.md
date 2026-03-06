# Phase 5.6: Frontend Memory/Graph Visualization

> **Status**: Ready for implementation
> **Priority**: P3 | **Complexity**: High | **Dependencies**: Phase 2 (memory), Phase 3 (graph) — both complete
> **Goal**: Add UI panels showing knowledge graph, memory tier browser, and context budget usage

---

## Context

The backend has a rich memory system (5 memory types, Stanford scoring, hybrid search) and knowledge graph (relationships with recursive CTE traversal), but the frontend has **zero visibility** into these systems. All graph/memory data is only accessible through LLM tool calls — the player and developer cannot browse memories, inspect the relationship graph, or see how the token budget is allocated. This phase adds three visualization panels to make these systems visible and debuggable.

---

## Architecture Decisions

1. **Tab system in GamePanel** — Add 3 tabs (Game | Memory | Insights) to the existing right sidebar. Game tab = current content unchanged. Memory tab = filterable memory browser. Insights tab = token budget bar + graph stats + "View Graph" button.
2. **Knowledge graph modal** — The graph needs more space than 320px sidebar. Opens as a full modal (like Settings/Tools/Database) with a pure SVG force-directed layout. No external library — D&D session graphs are small (5-30 nodes).
3. **Budget via SSE** — Token budget is computed per-request in the agent loop. Emit a new `budget` SSE event before `done` so the frontend gets real-time data. Cache last budget per conversation for REST fallback.
4. **New REST endpoints** — 3 endpoints in a new `visualization` router for direct frontend queries (memories, graph, budget). No LLM involvement.
5. **No new npm dependencies** — Pure SVG + Tailwind. Force layout in ~150 lines of TypeScript.

---

## Sub-phase A: Backend Endpoints

### A1. Add `to_dict()` to TokenBudget

**File**: `backend/app/services/token_utils.py` (after line 148)

```python
def to_dict(self) -> dict:
    return {
        "num_ctx": self.num_ctx,
        "system_prompt_tokens": self.system_prompt_tokens,
        "rag_context_tokens": self.rag_context_tokens,
        "tool_definitions_tokens": self.tool_definitions_tokens,
        "conversation_history_tokens": self.conversation_history_tokens,
        "response_reserve": self.response_reserve,
        "safety_buffer": self.safety_buffer,
        "total_input_tokens": self.total_input_tokens,
        "input_budget": self.input_budget,
        "utilization_pct": round(self.utilization_pct, 1),
        "tokens_remaining": self.tokens_remaining,
        "summarized_message_count": self.summarized_message_count,
        "truncated_message_count": self.truncated_message_count,
    }
```

### A2. Emit `budget` SSE event

**File**: `backend/app/services/agent_base.py` (before `done` event at line ~325)
- After `budget.log_summary()` at line 140, store budget on ctx: `ctx.budget_snapshot = ctx.budget.to_dict()`
- Before yielding the `done` event (line ~325), yield: `ServerSentEvent(data=json.dumps(ctx.budget.to_dict()), event="budget")`

**File**: `backend/app/services/chat_service.py` (no-tools path, before `done` at line ~323)
- Same pattern: yield `budget` SSE event before the `done` event

### A3. Budget cache on ChatService

**File**: `backend/app/services/chat_service.py`
- Add class-level `_budget_cache: dict[str, dict] = {}` on `ChatService`
- After emitting `budget` SSE, store: `self._budget_cache[conversation_id] = budget.to_dict()`
- Add method `get_cached_budget(conversation_id) -> dict | None`

### A4. Create visualization router

**New file**: `backend/app/routers/visualization.py`

Three endpoints:

| Endpoint | Method | Response |
|----------|--------|----------|
| `/conversations/{id}/rpg/memories` | GET | `{ memories: [...], total, types_summary }` |
| `/conversations/{id}/rpg/graph` | GET | `{ nodes: [...], edges: [...] }` |
| `/conversations/{id}/rpg/budget` | GET | `TokenBudget dict or null` |

**Memories endpoint** (`?type=&entity_type=&limit=50&offset=0`):
- Query `GameMemory` table filtered by session_id (from GameSession linked to conversation)
- Optional filters: memory_type, entity_type
- `types_summary`: `GROUP BY memory_type` count
- Order by `created_at DESC`

**Graph endpoint** (`?min_strength=0`):
- Query all `Relationship` rows for the session
- Collect unique `(entity_type, entity_id)` as nodes, resolve names via existing helpers in `relationships.py` (`_auto_detect_entity`, `_resolve_names_batch` patterns)
- Return flat `{ nodes, edges }` structure

**Budget endpoint**:
- Read from `ChatService._budget_cache[conversation_id]`
- Return `null` if no budget computed yet

### A5. Register router

**File**: `backend/app/main.py` (line 42)
- Add `visualization` to import
- Add `app.include_router(visualization.router, prefix="/api")`

### A6. Config

**File**: `backend/app/config.py`
```python
# Phase 5.6 — Frontend visualization
visualization_enabled: bool = True
visualization_memory_page_size: int = 50
visualization_graph_max_nodes: int = 100
```

---

## Sub-phase B: Frontend Store + API + Types

### B1. TypeScript interfaces

**File**: `frontend/src/types/index.ts` — add:

```typescript
interface MemoryItem {
  id: string; memory_type: string; entity_type: string | null;
  content: string; importance_score: number; entity_names: string[];
  session_number: number | null; created_at: string;
}
interface GraphNode { id: string; name: string; type: string; entity_id: string; }
interface GraphEdge {
  source_id: string; target_id: string; relationship: string;
  strength: number; source_type: string; target_type: string;
}
interface TokenBudgetSnapshot {
  num_ctx: number; system_prompt_tokens: number; rag_context_tokens: number;
  tool_definitions_tokens: number; conversation_history_tokens: number;
  response_reserve: number; total_input_tokens: number; input_budget: number;
  utilization_pct: number; tokens_remaining: number;
  summarized_message_count: number; truncated_message_count: number;
}
```

### B2. API methods

**File**: `frontend/src/services/api.ts` — add 3 methods + extend `streamChat`:

```typescript
getMemories: (conversationId, params?) => request<{memories, total, types_summary}>(...)
getGraph: (conversationId, params?) => request<{nodes, edges}>(...)
getBudget: (conversationId) => request<TokenBudgetSnapshot | null>(...)
```

Extend `streamChat` signature with `onBudget?: (data: TokenBudgetSnapshot) => void` callback. Add handler in `onmessage`:
```typescript
} else if (ev.event === "budget") {
  onBudget?.(JSON.parse(ev.data));
}
```

### B3. Zustand store

**New file**: `frontend/src/store/visualizationStore.ts`

State: `memories`, `memoriesLoading`, `memoryTypeSummary`, `memoryFilter`, `graphNodes`, `graphEdges`, `graphLoading`, `budget`

Actions: `loadMemories(conversationId)`, `loadGraph(conversationId)`, `setBudget(data)`, `setMemoryFilter(filter)`, `clear()`

### B4. UI store extensions

**File**: `frontend/src/store/uiStore.ts`
- Extend `ModalId`: `"settings" | "tools" | "database" | "knowledge-graph" | null`
- Add `gamePanelTab: "game" | "memory" | "insights"` state + `setGamePanelTab` action

### B5. Wire budget SSE in chatStore

**File**: `frontend/src/store/chatStore.ts`
- In `sendMessage`, pass `onBudget` callback to `streamChat` that calls `useVisualizationStore.getState().setBudget(data)`

---

## Sub-phase C: GamePanel Tab System

### C1. Tab bar in GamePanel

**File**: `frontend/src/components/rpg/GamePanel.tsx`
- Add tab bar below header (3 buttons: Game | Memory | Insights)
- Read `gamePanelTab` from `uiStore`
- Conditionally render: `game` = existing content, `memory` = `<MemoryBrowser />`, `insights` = `<InsightsPanel />`
- Existing game content stays exactly as-is, just wrapped in a conditional
- Tabs only shown when `gameState` exists (no tabs in empty state)

Tab styling: small pills matching existing dark theme, active = amber highlight.

---

## Sub-phase D: Token Budget Bar (fastest visual payoff)

### D1. TokenBudgetBar component

**New file**: `frontend/src/components/rpg/TokenBudgetBar.tsx`

Segmented horizontal stacked bar:
- System prompt = purple segment
- RAG/memories = green segment
- Tool definitions = blue segment
- History = amber segment
- Remaining = dark gray segment

Below bar: `"4,000 / 5,892 tokens (67.9%)"` summary line.
Below that: mini breakdown rows (one per component).
Color warning: bar turns red-tinted when utilization > 90%.

### D2. InsightsPanel component

**New file**: `frontend/src/components/rpg/InsightsPanel.tsx`

Contains:
1. `<TokenBudgetBar />` — real-time from SSE
2. Graph stats summary (node count, edge count, entity type breakdown)
3. "View Knowledge Graph" button — opens `knowledge-graph` modal
4. Loads graph data on mount for stats; budget from store

---

## Sub-phase E: Memory Browser

### E1. MemoryBrowser component

**New file**: `frontend/src/components/rpg/MemoryBrowser.tsx`

- **Filter row**: Horizontal scrollable type pills with counts from `types_summary`
  - Colors: episodic=blue, semantic=green, procedural=purple, summary=amber, recall=cyan
  - Click to filter, click again to clear
- **Memory list**: Scrollable cards, each showing:
  - Type pill (small, colored)
  - Importance: thin colored bar (0-1 scale, green to amber to red)
  - Content text (3-line truncation, click to expand)
  - Entity name pills (gray)
  - Relative timestamp
- **Data loading**: Fetches on tab switch + refreshes when `messages.length` changes
- **Pagination**: "Load more" button at bottom (offset-based)

---

## Sub-phase F: Knowledge Graph Modal

### F1. ForceGraph SVG component

**New file**: `frontend/src/components/rpg/ForceGraph.tsx`

Pure TypeScript force-directed layout (~150 lines):
- Nodes: colored circles sized by edge count, with text labels
- Edges: lines with strength-based opacity
- Entity type colors: character=blue, npc=purple, location=amber, quest=green, item=gray
- Forces: repulsion (all pairs), attraction (edges), centering
- Runs 60 iterations on mount for stable layout
- Mouse drag on nodes for repositioning
- Hover tooltip with entity type + name + edge count

### F2. KnowledgeGraphModal component

**New file**: `frontend/src/components/rpg/KnowledgeGraphModal.tsx`

- Wider modal: `max-w-5xl`
- Contains `<ForceGraph />` filling available space
- Controls: entity type filter checkboxes, strength threshold slider
- Legend: color key for entity types
- Relationship labels shown on hover/click of edges
- Empty state: "No relationships yet — play the game to build the world graph"

### F3. Register modal in App.tsx

**File**: `frontend/src/App.tsx`
- Add `"knowledge-graph"` to `MODAL_TITLES`
- Add conditional render: `{activeModal === "knowledge-graph" && <KnowledgeGraphModal />}`

---

## Files Summary

### New Files (8)
| File | Purpose |
|------|---------|
| `backend/app/routers/visualization.py` | 3 REST endpoints (memories, graph, budget) |
| `frontend/src/store/visualizationStore.ts` | Zustand store for viz data |
| `frontend/src/components/rpg/TokenBudgetBar.tsx` | Segmented bar chart |
| `frontend/src/components/rpg/InsightsPanel.tsx` | Budget + graph stats panel |
| `frontend/src/components/rpg/MemoryBrowser.tsx` | Memory list with filters |
| `frontend/src/components/rpg/KnowledgeGraphModal.tsx` | Modal wrapper for graph |
| `frontend/src/components/rpg/ForceGraph.tsx` | Pure SVG force layout |

### Modified Files (10)
| File | Changes |
|------|---------|
| `backend/app/services/token_utils.py` | Add `to_dict()` to TokenBudget |
| `backend/app/services/agent_base.py` | Emit `budget` SSE event before `done` |
| `backend/app/services/chat_service.py` | Emit `budget` SSE in no-tools path; add budget cache |
| `backend/app/main.py` | Register visualization router |
| `backend/app/config.py` | Add visualization config |
| `frontend/src/types/index.ts` | Add MemoryItem, GraphNode, GraphEdge, TokenBudgetSnapshot |
| `frontend/src/services/api.ts` | Add 3 API methods + onBudget SSE handler |
| `frontend/src/store/uiStore.ts` | Add gamePanelTab + knowledge-graph ModalId |
| `frontend/src/components/rpg/GamePanel.tsx` | Add tab bar, conditional rendering |
| `frontend/src/App.tsx` | Add KnowledgeGraphModal to modal switch |
| `frontend/src/store/chatStore.ts` | Wire onBudget callback in sendMessage |

### Reuse Existing Code
| What | Where | How |
|------|-------|-----|
| Entity name resolution | `builtin_tools/relationships.py:_resolve_names_batch()` | Extract to shared helper or duplicate pattern in router |
| Memory type colors | `MemoryRenderer.tsx` | Reuse color mapping constants |
| Entity type icons | `RelationshipRenderer.tsx`, `EntityContextRenderer.tsx` | Reuse `ENTITY_TYPE_COLORS` pattern |
| Card container style | All renderers | `bg-gray-800/30 rounded-lg px-3 py-2.5 border border-gray-700/30` |
| Modal component | `frontend/src/components/common/Modal` | Existing reusable modal |
| GamePanel refresh pattern | `GamePanel.tsx` useEffect on messageCount | Same pattern for viz data |

---

## Implementation Order

```
A1 - A2 - A3 - A4 - A5 - A6    (Backend: budget SSE + REST endpoints)
B1 - B2 - B3 - B4 - B5          (Frontend: types + API + stores)
C1                                (GamePanel tab system)
D1 - D2                          (Token budget bar + insights panel)
E1                                (Memory browser)
F1 - F2 - F3                     (Knowledge graph modal)
Verification                      (Chrome MCP testing)
```

A and B can run in parallel (backend vs frontend). C-F are sequential (each builds on previous).

---

## Verification

1. **Backend**: `cd backend && uvicorn app.main:app --reload` — check 3 new endpoints return data after a game session
2. **Budget SSE**: Open browser DevTools Network tab, send a message, confirm `budget` event appears in SSE stream
3. **Tab system**: Click Game/Memory/Insights tabs — each shows correct content, Game tab unchanged
4. **Token budget**: Send messages, watch budget bar update in real-time via SSE
5. **Memory browser**: Start a game, archive events, switch to Memory tab — see memories with correct types and filters
6. **Knowledge graph**: Create NPCs, locations, relationships — open graph modal, verify nodes and edges render correctly with drag interaction
7. **Chrome MCP**: Full end-to-end screenshots of all 3 tabs + graph modal
