# sqliteRAG — Project Guide

Local-first AI chat app with an integrated D&D 5e RPG engine. React+Vite frontend, FastAPI+SQLAlchemy backend, Ollama for inference, SQLite+sqlite-vec for storage and RAG.

## Architecture

```
frontend/   React 19 + Vite + Zustand + Tailwind CSS 4
backend/    FastAPI + SQLAlchemy async + aiosqlite + sqlite-vec
```

- **Dev proxy**: frontend `:5173` proxies `/api` to backend `:8000`
- **Streaming**: SSE (Server-Sent Events) for chat — events: `token`, `tool_calls`, `tool_result`, `done`, `error`
- **Agent loop**: Backend calls Ollama, executes tool calls in a loop (max 10 rounds), streams results

## Key Directories

| Path | Purpose |
|------|---------|
| `frontend/src/store/` | Zustand stores: chatStore, settingsStore, toolStore, uiStore, databaseStore |
| `frontend/src/services/api.ts` | Centralized API client (REST + SSE) |
| `frontend/src/components/tools/renderers/` | Tool result renderer registry (19 renderers, 9 phases) |
| `frontend/src/components/rpg/GamePanel.tsx` | RPG dashboard sidebar |
| `backend/app/routers/chat.py` | `POST /api/chat/{id}` SSE stream endpoint |
| `backend/app/services/chat_service.py` | Agent loop core (tool calling + RAG injection) |
| `backend/app/services/builtin_tools/` | 41 RPG tools across 9 modules |
| `backend/app/services/rpg_service.py` | D&D 5e rules engine + fantasy name generation |
| `backend/app/models/rpg.py` | ORM: GameSession, Character, Location, NPC, Quest, InventoryItem |

## Tool Renderer System

Backend tools return JSON with a `"type"` field. The frontend registry maps types to React components.

**Registry**: `frontend/src/components/tools/renderers/index.ts`
**Pattern**: `registerToolRenderer("type_name", RendererComponent)`

### Phases

| Phase | Domain | Types |
|-------|--------|-------|
| 0 | Original | `roll_d20` |
| 1 | Dice & Math | `roll_dice`, `check_result` |
| 2 | Characters | `character_sheet`, `character_list` |
| 3 | Combat | `initiative_order`, `attack_result`, `spell_cast`, `death_save`, `combat_action`, `damage_result`, `heal_result` |
| 4 | Inventory | `inventory`, `item_detail`, `transfer_result` |
| 5 | World | `location`, `location_connected`, `environment` |
| 6 | NPCs | `npc_info` |
| 7 | Quests | `quest_info`, `quest_journal`, `quest_complete` |
| 8 | Rest | `rest_result` |
| 9 | Game State | `game_session`, `game_state` |

### Creating a New Renderer

1. Define a TypeScript interface matching the backend JSON shape
2. Create `frontend/src/components/tools/renderers/{Name}Renderer.tsx`
3. Register in `index.ts` under the correct phase: `registerToolRenderer("type_name", NameRenderer)`
4. Rarity-driven styles use token maps: `RARITY_COLORS`, `RARITY_BORDER`, `TYPE_ICONS`

## Backend Tool Contracts

Each builtin tool returns `json.dumps({...})` with a `"type"` field matching a frontend renderer.

| Tool function | Returns `type` | Key fields |
|---------------|---------------|------------|
| `create_item` | `item_detail` | `name, item_type, description, weight, value_gp, properties, rarity` |
| `get_inventory` | `inventory` | `character, items[], total_weight, capacity, encumbered, total_value_gp` |
| `transfer_item` | `transfer_result` | `message, from_character, to_character, item_name` |
| `create_character` | `character_sheet` | Full character sheet fields |
| `attack` | `attack_result` | `attacker, target, weapon, attack_rolls, hit, damage, ...` |
| `roll_dice` | `roll_dice` | `notation, groups[], total` |
| `roll_check` | `check_result` | `character, ability, check_type, rolls, chosen, modifier, total, dc, success, nat20, nat1` |
| `look_around` | `location` | `name, description, biome, exits, characters_here, npcs_here, environment, moved_by` |
| `connect_locations` | `location_connected` | `location1, location2, direction, reverse_direction` (rendered by LocationRenderer) |
| `move_to` | `location` | `name, description, biome, exits, characters_here, npcs_here, environment, moved_by` |
| `set_environment` | `environment` | `time_of_day, weather, season` (rendered by LocationRenderer) |
| `get_game_state` | `game_state` | `world_name, characters[], current_location, active_quests, npcs, in_combat, environment` |

## Common Commands

```bash
# Frontend
cd frontend && npm run dev      # Dev server :5173
cd frontend && npx tsc --noEmit # Type check only

# Backend
cd backend && uvicorn app.main:app --reload  # Dev server :8000

# Database migrations
cd backend && alembic upgrade head
```

## Conventions

- **Styling**: Tailwind utility classes, dark theme (gray-900 backgrounds, colored accents per rarity)
- **State**: Zustand stores, no Redux
- **Types**: TypeScript strict, interfaces for all data shapes
- **Backend**: Async-first, `async def` everywhere, SQLAlchemy async sessions
- **Tool results**: Always include `"type"` field, optionally `"error"` for error states
- **Renderer error handling**: Every renderer checks `if (d.error)` first, returns red error text

## Development Philosophy

- **Value-first**: Every feature must deliver visible, testable value in the running application. No "write code to write code" — infrastructure is only justified when it directly enables a user-facing outcome.
- **Working app over unit tests**: Unit tests are welcome but secondary. The primary verification is a working application tested end-to-end via Chrome MCP (browser screenshots, snapshots, interaction).
- **Chrome MCP verification**: All features must include browser-based verification steps using Chrome DevTools MCP tools (take_snapshot, take_screenshot, click, fill, navigate_page). This confirms the feature works in the real UI, not just in isolation.
