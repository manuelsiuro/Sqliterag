# RPG Engine Integration — Inspired by Mnehmos/rpg-mcp

## Context

The Mnehmos/rpg-mcp project is a **complete D&D 5e game engine** built as an MCP server with 28 consolidated tools (representing 195 features). It enforces deterministic game rules — the LLM proposes actions, the engine validates and executes. We want to bring this RPG functionality into sqliteRAG's existing tool calling system, adapted to our Python/FastAPI backend + React/Zustand frontend architecture.

**Key insight**: Each RPG feature becomes a Python `builtin` tool function registered in `BUILTIN_REGISTRY`. The LLM calls tools via Ollama's tool calling API. The engine enforces D&D rules. Rich React renderers display results. No MCP server needed — we integrate directly.

---

## Mnehmos/rpg-mcp Complete Feature Report

### 28 Consolidated Tools (195 features total)

| # | Tool | Actions | What It Does |
|---|------|---------|--------------|
| 1 | `character_manage` | 8 | Create/update/delete characters, XP, leveling (1-20), D&D 5e stats |
| 2 | `party_manage` | 16 | Form parties, roles, formation, movement, member management |
| 3 | `combat_manage` | 9 | Initiative, encounter lifecycle, death saves, lair actions |
| 4 | `combat_action` | 9 | Attack, cast spell, heal, help, move, dash, disengage, dodge, ready |
| 5 | `combat_map` | 7 | ASCII tactical maps, AoE, terrain, procedural generation |
| 6 | `item_manage` | 6 | Item templates (weapon, armor, consumable, quest, scroll, misc) |
| 7 | `inventory_manage` | 8 | Give/remove/transfer/equip/unequip, weight capacity enforcement |
| 8 | `corpse_manage` | 14 | Loot drops, harvesting, loot tables, decay mechanics |
| 9 | `world_manage` | 7 | World creation, environment (weather, day/night, seasons) |
| 10 | `world_map` | 9 | Procedural world gen (28+ biomes), tile grids, POI placement |
| 11 | `spatial_manage` | 5 | Rooms, exits, biomes, atmospheric effects, movement |
| 12 | `quest_manage` | 8 | Multi-objective quests, rewards, prerequisites, journal |
| 13 | `npc_manage` | 7 | Relationships, memory, spatial perception, stealth mechanics |
| 14 | `scroll_manage` | 6 | Spell scrolls, DC calculation, identification, class validation |
| 15 | `concentration_manage` | 5 | D&D 5e concentration rules, damage saves, auto-breaks |
| 16 | `aura_manage` | 7 | Area effects (buff/debuff/damage/heal), triggers, duration |
| 17 | `rest_manage` | 2 | Short rest (hit dice) and long rest (full recovery) |
| 18 | `improvisation_manage` | 8 | "Rule of Cool" stunts, custom effects, spell synthesis |
| 19 | `theft_manage` | 10 | Stealing, fence economy, heat system, bounties |
| 20 | `secret_manage` | 9 | DM secrets, reveal conditions, leak detection |
| 21 | `narrative_manage` | 6 | Plot threads, canonical moments, NPC voices, foreshadowing |
| 22 | `travel_manage` | 3 | Party movement, auto-discovery, encounter loot collection |
| 23 | `session_manage` | 2 | Initialize/resume game, comprehensive state context |
| 24 | `turn_manage` | 5 | Turn-based strategy, diplomatic/territorial actions |
| 25 | `strategy_manage` | 6 | Nation management, diplomacy, alliances, territorial expansion |
| 26 | `spawn_manage` | 5 | 1100+ creature presets, location gen, encounter gen |
| 27 | `batch_manage` | 7 | Bulk creation, workflow templates, chained tool execution |
| 28 | `math_manage` | 5 | Full dice notation, probability, algebra, projectile physics |

### Key Design Principles from rpg-mcp
- LLMs propose intentions; engine validates and executes
- Zero direct mutation — all state flows through tools
- Seeded RNG for reproducible outcomes
- Guiding error messages with actionable suggestions
- SQLite for complete persistence across sessions

---

## Decisions
- **First sprint**: Phase 0 (Foundation) + Phase 1 (Dice) together
- **Tool strategy**: All individual tools registered separately. User decides which to enable per conversation via existing toggle UI.
- **UI style**: Use `frontend-design` skill for each RPG renderer — distinctive, polished components.

---

## Implementation Plan — Feature by Feature

### Phase 0: Foundation (prerequisite for all RPG features)

#### 0A. Async Builtin Tool Execution with DB Access

Currently `_execute_builtin` in `tool_service.py:49` is sync and has no DB access. RPG tools need to read/write game state.

**Changes:**
- `backend/app/services/tool_service.py` — Make `_execute_builtin` async-aware. Detect `asyncio.iscoroutinefunction(func)` and `await` if needed. Pass `session` and `conversation_id` as keyword args to builtin functions that accept them.
- `backend/app/services/chat_service.py:147` — Pass `session` and `conversation_id` through `execute_tool()`.
- `backend/app/services/builtin_tools.py` — Existing `roll_d20` stays unchanged (no session needed). New RPG tools accept optional `session`/`conversation_id` kwargs.

#### 0B. RPG Data Models

New file `backend/app/models/rpg.py` with SQLAlchemy models:
- **GameSession** — ties RPG state to a conversation (1:1). Fields: `conversation_id` (FK unique), `world_name`, `current_location`, `environment` (JSON), `combat_state` (JSON), `created_at`.
- **Character** — `session_id` (FK), `name`, `race`, `char_class`, `level`, `xp`, 6 ability scores, `max_hp`, `current_hp`, `temp_hp`, `armor_class`, `speed`, `conditions` (JSON), `spell_slots` (JSON), `is_player`, `is_alive`.
- **Item** — template: `name`, `item_type`, `description`, `weight`, `value_gp`, `properties` (JSON), `rarity`.
- **InventoryItem** — `character_id` (FK), `item_id` (FK), `quantity`, `is_equipped`.
- **Location** — `session_id` (FK), `name`, `description`, `biome`, `exits` (JSON), `props` (JSON).
- **NPC** — `session_id` (FK), `name`, `description`, `location_id`, `disposition`, `familiarity`, `memory` (JSON).
- **Quest** — `session_id` (FK), `title`, `description`, `status`, `objectives` (JSON), `rewards` (JSON).

Import in `backend/app/models/__init__.py` so `Base.metadata.create_all` picks them up.

#### 0C. RPG Service Layer

New file `backend/app/services/rpg_service.py` — central game logic class with D&D 5e math:
- `_calculate_modifier(score)`, `_calculate_proficiency(level)`, `_calculate_hp(class, level, con_mod)`
- `_get_or_create_session(db_session, conversation_id)` — auto-creates GameSession on first RPG tool call
- XP thresholds table (levels 1-20)
- Methods added incrementally per phase

---

### Phase 1: Dice & Math System
*Inspired by: `math_manage` (5 actions)*

**Backend** — New functions in `BUILTIN_REGISTRY`:
| Tool | Parameters | Returns |
|------|-----------|---------|
| `roll_dice` | `notation` (e.g. "2d6+3"), `label` | Parsed rolls, modifiers, total |
| `roll_check` | `character_name`, `ability`, `dc`, `advantage` | d20 + modifier vs DC, pass/fail |
| `roll_save` | `character_name`, `ability`, `dc` | d20 + save modifier vs DC |

Dice parser handles: `XdY`, `+/-N`, `kh/kl` (keep highest/lowest), `dh/dl` (drop), `r` (reroll), `!` (exploding).

**Frontend** — New renderers:
- `DiceRollRenderer.tsx` — Enhanced dice display with any die size, kept/dropped visualization, crit highlighting
- `CheckResultRenderer.tsx` — d20 + modifier vs DC bar, pass/fail badge, advantage display

**Files to modify**: `builtin_tools.py`, `database.py` (seed), `renderers/index.ts`
**New files**: `backend/app/services/rpg/dice.py`, `frontend/src/components/tools/renderers/DiceRollRenderer.tsx`, `CheckResultRenderer.tsx`

---

### Phase 2: Character Management
*Inspired by: `character_manage` (8 actions)*

**Backend** — New tools:
| Tool | Parameters | Returns |
|------|-----------|---------|
| `create_character` | `name`, `race`, `char_class`, `level`, 6 ability scores | Full character sheet JSON |
| `get_character` | `name` | Character sheet |
| `update_character` | `name`, `hp_change`, `add_condition`, `remove_condition`, `add_xp` | Updated sheet |
| `list_characters` | — | All characters in session |

Auto-computes: HP (by class hit die + CON), AC (10 + DEX mod default), proficiency bonus, ability modifiers. Auto-level-up when XP threshold crossed. Condition tracking (blinded, charmed, frightened, etc.).

**Frontend** — New renderers:
- `CharacterSheetRenderer.tsx` — Ability scores grid with modifiers, HP bar, AC shield, conditions as badges, class/race/level header
- `CharacterListRenderer.tsx` — Compact card list

**Files**: `rpg_service.py`, `builtin_tools.py`, `database.py`, new renderers
**Depends on**: Phase 0, Phase 1 (dice for ability score generation)

---

### Phase 3: Combat System
*Inspired by: `combat_manage` (9), `combat_action` (9), `combat_map` (7)*

**Backend** — New tools:
| Tool | Parameters | Returns |
|------|-----------|---------|
| `start_combat` | `combatant_names` (list) | Initiative order, round 1 |
| `get_combat_status` | — | Current turn, HP summary, conditions |
| `next_turn` | — | Advances turn, triggers effects |
| `end_combat` | — | Combat summary, XP awards |
| `attack` | `attacker`, `target`, `weapon`, `advantage` | Attack roll vs AC, damage, crit detection |
| `cast_spell` | `caster`, `spell_name`, `target`, `level` | Spell effect, slot consumed, save/attack |
| `heal` | `healer`, `target`, `amount` or `spell` | HP restored |
| `take_damage` | `character`, `damage`, `type` | HP reduced, death save if 0 |
| `death_save` | `character` | d20 roll, success/fail tracking |
| `combat_action` | `character`, `action` (dodge/dash/disengage/help/hide) | Action applied |

Combat state stored as JSON in `GameSession.combat_state`. Core SRD spells (~20 most common) as a Python dict.

**Frontend** — New renderers:
- `InitiativeOrderRenderer.tsx` — Turn tracker with HP bars, current turn highlight, round counter
- `AttackResultRenderer.tsx` — d20 roll vs AC, hit/miss, damage breakdown, crit celebration
- `SpellCastRenderer.tsx` — Spell name/level, slot consumed, effect description
- `DeathSaveRenderer.tsx` — Three success/failure circles

**Files**: `rpg_service.py`, `rpg/spells.py` (spell data), `builtin_tools.py`, `database.py`, new renderers
**Depends on**: Phase 2 (characters), Phase 1 (dice)

---

### Phase 4: Inventory & Items
*Inspired by: `item_manage` (6), `inventory_manage` (8)*

**Backend** — New tools:
| Tool | Parameters | Returns |
|------|-----------|---------|
| `create_item` | `name`, `type`, `description`, `weight`, `value_gp`, `properties` | Item details |
| `give_item` | `character`, `item_name`, `quantity` | Updated inventory |
| `equip_item` | `character`, `item_name` | Equipment change, AC update |
| `unequip_item` | `character`, `item_name` | Equipment change |
| `get_inventory` | `character` | Full inventory with weight/capacity |
| `transfer_item` | `from`, `to`, `item_name`, `quantity` | Transfer confirmation |

Seed ~30 core items (longsword, leather armor, healing potion, etc.). Weight capacity = STR * 15.

**Frontend** — New renderer:
- `InventoryRenderer.tsx` — Item grid with type icons, equipped badge, weight bar, gold total

**Depends on**: Phase 2 (characters for inventory ownership)

---

### Phase 5: World & Spatial System
*Inspired by: `spatial_manage` (5), `world_manage` (7)*

**Backend** — New tools:
| Tool | Parameters | Returns |
|------|-----------|---------|
| `create_location` | `name`, `description`, `biome`, `exits` | Location details |
| `connect_locations` | `location1`, `location2`, `direction` | Bidirectional link |
| `move_to` | `character`, `direction` or `location_name` | New location description |
| `look_around` | — | Location, exits, characters/NPCs present |
| `set_environment` | `time_of_day`, `weather`, `season` | Updated environment |

**Frontend** — New renderer:
- `LocationRenderer.tsx` — Atmospheric card with biome, description, exit arrows, who's here

**Depends on**: Phase 0 (models), Phase 2 (characters for placement)

---

### Phase 6: NPC System
*Inspired by: `npc_manage` (7 actions)*

**Backend** — New tools:
| Tool | Parameters | Returns |
|------|-----------|---------|
| `create_npc` | `name`, `description`, `location`, `disposition` | NPC details |
| `talk_to_npc` | `npc_name`, `topic` | NPC context for LLM roleplay |
| `update_npc_relationship` | `npc`, `character`, `familiarity_change`, `disposition_change` | Updated relationship |
| `npc_remember` | `npc_name`, `event` | Memory recorded |

Disposition scale: hostile > unfriendly > neutral > friendly > helpful.
Familiarity scale: stranger > acquaintance > friend > close_friend.

**Frontend** — New renderer:
- `NPCRenderer.tsx` — Disposition meter (gradient), familiarity level, memory list

**Depends on**: Phase 5 (locations for NPC placement)

---

### Phase 7: Quest System
*Inspired by: `quest_manage` (8 actions)*

**Backend** — New tools:
| Tool | Parameters | Returns |
|------|-----------|---------|
| `create_quest` | `title`, `description`, `objectives`, `rewards` | Quest details |
| `update_quest_objective` | `quest_title`, `objective_index`, `completed` | Updated quest |
| `complete_quest` | `quest_title` | Rewards distributed (XP, gold, items) |
| `get_quest_journal` | — | All quests by status |

**Frontend** — New renderer:
- `QuestJournalRenderer.tsx` — Quest log with checkbox objectives, reward previews, status badges

**Depends on**: Phase 2 (characters for rewards), Phase 6 (NPCs as quest givers)

---

### Phase 8: Rest & Recovery
*Inspired by: `rest_manage` (2 actions)*

**Backend** — New tools:
| Tool | Parameters | Returns |
|------|-----------|---------|
| `short_rest` | `character`, `hit_dice_to_spend` | HP healed, resources recovered |
| `long_rest` | `character` | Full HP, spell slots restored, hit dice recovered |

**Frontend** — New renderer:
- `RestResultRenderer.tsx` — Before/after HP, spell slots recovered

**Depends on**: Phase 2 (characters), Phase 3 (spell slots)

---

### Phase 9: Session Management & Game Panel
*Inspired by: `session_manage` (2 actions)*

**Backend** — New tools:
| Tool | Parameters | Returns |
|------|-----------|---------|
| `init_game_session` | `world_name` | Welcome context, session created |
| `get_game_state` | — | Full state: party, location, quests, combat, environment |

System prompt injection: When RPG tools are enabled for a conversation, auto-inject game state + DM instructions into the system message (in `chat_service.py` alongside RAG injection).

**Frontend** — New panel:
- `GamePanel.tsx` — RPG dashboard in sidebar: party summary, location, active quests, combat indicator
- New button in `Sidebar.tsx` alongside existing Tools/Database/Settings buttons

**Depends on**: All previous phases

---

### Deferred Features (Phase 10+)
These can be added after the core gameplay loop works:
- Concentration management (auto-break on damage)
- Aura/area effects
- Theft & fence economy
- Secret management (DM-only info)
- Narrative management (plot threads)
- Combat map (ASCII tactical grid)
- Spawn system (creature presets)
- Corpse & loot tables
- Travel with random encounters
- Batch operations
- Turn-based strategy/nation management

---

## Critical Files

| File | Role |
|------|------|
| `backend/app/services/tool_service.py` | Dispatch — must add async support + session/conversation_id passthrough |
| `backend/app/services/builtin_tools.py` | Registry — grows from 1 to ~33 tool functions |
| `backend/app/services/chat_service.py` | Agent loop — must pass session/conversation_id to tools, inject RPG system prompt |
| `backend/app/database.py` | Seed — register all new tools at startup |
| `backend/app/models/rpg.py` | New — all RPG SQLAlchemy models |
| `backend/app/services/rpg_service.py` | New — D&D 5e game logic |
| `backend/app/services/rpg/dice.py` | New — full dice notation parser/roller |
| `frontend/src/components/tools/renderers/index.ts` | Registration hub for all new renderers |

## Verification

For each phase:
1. Start backend (`uvicorn app.main:app`) — confirm new tables created, tools seeded
2. Open frontend — confirm new tools appear in Tools panel
3. Enable tools on a conversation
4. Chat with the LLM and verify it calls the tools correctly
5. Verify rich renderers display in the chat UI
6. Verify data persists across page reloads (SQLite)

Full gameplay test after Phase 9:
- Init a game session, create characters, explore locations, talk to NPCs, fight enemies, complete quests, rest, level up — all through natural conversation with the LLM
