# Phase 5.4: Automated Encounter Balancing

> **Status**: Ready for implementation
> **Priority**: P3 | **Complexity**: Medium | **Dependencies**: Phase 4 (complete), Phase 5.3 (complete)
> **Goal**: Use party level, size, and HP to suggest appropriate encounters. Add CR-based monster generation and XP rewards.

---

## Context

The combat system (`start_combat`) accepts any list of character names with **no difficulty assessment**. The DM (LLM) has no guidance on whether an encounter is Easy, Medium, Hard, or Deadly per D&D 5e DMG rules. There are no monster/enemy stat templates — every enemy must be manually created via `create_character`. After combat, there is no XP reward system.

Phase 5.4 adds:
1. D&D 5e encounter difficulty math (XP budgets, CR-to-XP, encounter multipliers)
2. CR-based monster stat generation (auto-creates `Character` with `is_player=False`)
3. XP reward distribution after combat (with auto level-up)
4. Difficulty badge injected into `start_combat` output and GamePanel sidebar

**Tool count**: 53 -> 56 (3 new tools)

---

## Files to Modify

| # | File | Action | Change |
|---|------|--------|--------|
| 1 | `backend/app/services/rpg_service.py` | MODIFY | +5 constant tables, +7 pure-math functions (~120 lines) |
| 2 | `backend/app/config.py` | MODIFY | +2 config flags after line 126 |
| 3 | `backend/app/services/builtin_tools/_common.py` | MODIFY | +8 new imports from rpg_service |
| 4 | `backend/app/services/builtin_tools/encounters.py` | CREATE | 3 tool functions: `balance_encounter`, `generate_monster`, `award_xp` (~150 lines) |
| 5 | `backend/app/services/builtin_tools/combat.py` | MODIFY | +15 lines in `start_combat` for difficulty injection |
| 6 | `backend/app/services/builtin_tools/__init__.py` | MODIFY | +1 import block, +3 registry entries |
| 7 | `backend/app/database.py` | MODIFY | +3 tool definitions in `_builtin_tool_defs()` |
| 8 | `backend/app/services/prompt_builder.py` | MODIFY | +3 tool names in RPG set, +tools in 2 phase sets, +lines in phase rules, +difficulty in Layer 3 |
| 9 | `backend/app/services/narrator_agent.py` | MODIFY | +3 tool names in `_NARRATOR_FINAL_TOOLS` |
| 10 | `backend/app/services/tool_service.py` | MODIFY | +2 alias entries in `_ARGUMENT_ALIASES` |
| 11 | `frontend/src/components/tools/renderers/EncounterRenderer.tsx` | CREATE | Multi-type renderer for 3 types (~200 lines) |
| 12 | `frontend/src/components/tools/renderers/index.ts` | MODIFY | +3 `registerToolRenderer` calls |
| 13 | `frontend/src/components/tools/renderers/InitiativeOrderRenderer.tsx` | MODIFY | +difficulty badge in combat header (~10 lines) |
| 14 | `frontend/src/components/rpg/GamePanel.tsx` | MODIFY | +difficulty pill in combat indicator (~15 lines) |

---

## Implementation

### Step 1: D&D 5e Encounter Constants & Functions

**`backend/app/services/rpg_service.py`** — insert after `ABILITY_NAMES` (line 52):

**Constants to add:**

- `ENCOUNTER_XP_THRESHOLDS: dict[int, dict[str, int]]` — per-level XP budgets for Easy/Medium/Hard/Deadly (levels 1-20, DMG Chapter 3)
- `CR_TO_XP: dict[str, int]` — CR string -> XP value (SRD: "0"->10, "1/8"->25, ... "20"->25000)
- `ENCOUNTER_MULTIPLIERS: list[tuple[int, float]]` — monster count -> multiplier [(1,1.0), (2,1.5), (3,2.0), (7,2.5), (11,3.0), (15,4.0)]
- `MONSTER_STATS_BY_CR: dict[str, dict]` — CR -> {ac, hp_min, hp_max, atk_bonus, dmg_min, dmg_max, save_dc} (DMG quick stats table, CR 0 through 20)
- `CREATURE_TYPE_TEMPLATES: dict[str, dict[str, int]]` — 14 creature types (beast, humanoid, undead, fiend, dragon, construct, aberration, elemental, monstrosity, giant, fey, celestial, plant, ooze) with base ability scores

**Pure-math functions to add (after `level_for_xp` at line 142):**

```python
def normalize_cr(cr_input) -> str:
    """Normalize CR input to string key (0.25 -> '1/4', 1 -> '1')."""

def get_encounter_multiplier(num_monsters: int) -> float:
    """DMG encounter multiplier based on monster count."""

def get_party_xp_thresholds(levels: list[int]) -> dict[str, int]:
    """Sum Easy/Medium/Hard/Deadly XP thresholds for a party."""

def calculate_encounter_difficulty(party_levels, enemy_crs) -> dict:
    """Full DMG encounter difficulty assessment.
    Returns: difficulty, adjusted_xp, raw_xp, multiplier, thresholds, counts."""

def generate_monster_stats(cr: str, creature_type: str = "humanoid") -> dict:
    """Generate D&D 5e monster stats from CR + creature type template.
    Returns: cr, xp, creature_type, armor_class, max_hp, attack_bonus,
    damage_per_round, save_dc, level, abilities, char_class."""

def estimate_cr_from_hp(max_hp: int) -> str:
    """Reverse lookup: find CR whose hp range contains max_hp (for award_xp)."""

def _cr_to_float(cr: str) -> float:
    """Convert CR string to float ('1/4' -> 0.25)."""
```

### Step 2: Config Flags

**`backend/app/config.py`** — insert after line 126 (NPC personality config):

```python
    # Encounter balancing (Phase 5.4)
    encounter_balancing_enabled: bool = True
    encounter_auto_difficulty: bool = True  # Inject difficulty into start_combat
```

### Step 3: Shared Imports

**`backend/app/services/builtin_tools/_common.py`** — add to the `rpg_service` import block:

```python
    CR_TO_XP,
    CREATURE_TYPE_TEMPLATES,
    MONSTER_STATS_BY_CR,
    calculate_encounter_difficulty,
    estimate_cr_from_hp,
    generate_monster_stats,
    get_party_xp_thresholds,
    normalize_cr,
```

### Step 4: New Tool Module — `encounters.py`

**`backend/app/services/builtin_tools/encounters.py`** (CREATE)

Three async tool functions following the standard pattern:

#### `balance_encounter(enemy_crs, desired_difficulty?, *, session, conversation_id)`
- Parse `enemy_crs` (comma-separated string: `"2, 2, 1/2"`)
- Fetch all `is_player=True` Characters from session for party levels
- Call `calculate_encounter_difficulty(party_levels, parsed_crs)`
- If `desired_difficulty` given, compute XP gap and suggest CR adjustments
- Return `type: "encounter_balance"` with: difficulty, adjusted_xp, raw_xp, multiplier, thresholds, per-enemy breakdown, recommendation
- Error if no player characters exist

#### `generate_monster(name, cr?, creature_type?, *, session, conversation_id)`
- Call `generate_monster_stats(cr, creature_type)` from rpg_service
- Create `Character` ORM object: `is_player=False`, `char_class=creature_type.capitalize()`, `race=creature_type`, ability scores from template, HP/AC from CR table
- Handle duplicate names by appending " (CR X)" suffix
- Return `type: "monster_generated"` with `character_to_dict()` + cr, xp_value, creature_type

#### `award_xp(*, session, conversation_id)`
- Find all `is_player=False` Characters in session
- Estimate each enemy's CR via `estimate_cr_from_hp(max_hp)`, sum XP
- Divide equally among `is_player=True` Characters (round down)
- Apply XP + check level-up (reuse `update_character` logic: recalc HP, set new level)
- Return `type: "xp_reward"` with total_xp, xp_per_character, per-character breakdown (with leveled_up flag), defeated enemy list

### Step 5: Enhance `start_combat` with Difficulty Injection

**`backend/app/services/builtin_tools/combat.py`** — modify `start_combat()` (lines 18-63):

When `settings.encounter_balancing_enabled` and `settings.encounter_auto_difficulty`:
1. After building initiative_order, partition combatants into players (`is_player=True`) and enemies (`is_player=False`)
2. For enemies, estimate CR via `estimate_cr_from_hp(char.max_hp)`
3. Call `calculate_encounter_difficulty(party_levels, enemy_crs)`
4. Add `encounter_difficulty` key to both `combat_state` JSON blob and returned JSON

```python
# Only when both player and non-player combatants exist
if settings.encounter_balancing_enabled and settings.encounter_auto_difficulty:
    party_levels = [...]  # is_player=True character levels
    enemy_crs = [...]     # estimated CRs for is_player=False
    if party_levels and enemy_crs:
        diff = calculate_encounter_difficulty(party_levels, enemy_crs)
        combat_state["encounter_difficulty"] = {
            "difficulty": diff["difficulty"],
            "adjusted_xp": diff["adjusted_xp"],
            "multiplier": diff["multiplier"],
        }
```

Backward compatible: the key only appears when both flags are on AND there are mixed player/non-player combatants.

### Step 6: Register Tools

**`backend/app/services/builtin_tools/__init__.py`**:

```python
# Add import
from app.services.builtin_tools.encounters import (
    award_xp,
    balance_encounter,
    generate_monster,
)

# Add to BUILTIN_REGISTRY after Phase 11 (line 137)
    # Phase 14 — Encounter Balancing
    "balance_encounter": balance_encounter,
    "generate_monster": generate_monster,
    "award_xp": award_xp,
```

### Step 7: Tool Definitions

**`backend/app/database.py`** — add to `_builtin_tool_defs()` after `find_connections`:

- `balance_encounter`: required `enemy_crs` (string, comma-separated CRs), optional `desired_difficulty` (string)
- `generate_monster`: required `name` (string), optional `cr` (string, default "1"), optional `creature_type` (string, default "humanoid")
- `award_xp`: no parameters

Keep descriptions concise (~40-45 tokens each, ~130 total for all 3).

### Step 8: Prompt Builder Updates

**`backend/app/services/prompt_builder.py`**:

- **`RPG_TOOL_NAMES`** (line 24-51): Add `"balance_encounter"`, `"generate_monster"`, `"award_xp"`
- **`_PHASE_TOOLS[GamePhase.COMBAT]`** (line 136): Add `"balance_encounter"`, `"award_xp"`
- **`_PHASE_TOOLS[GamePhase.EXPLORATION]`** (line 142): Add `"balance_encounter"`, `"generate_monster"`
- **`_COMBAT_RULES`** (line 204): Add `"- After combat ends, use award_xp to distribute XP rewards.\n"`
- **`_EXPLORATION_RULES`**: Add `"- Use generate_monster to create enemies and balance_encounter to check difficulty before combat.\n"`
- **Layer 3 state**: When `combat_state` has `encounter_difficulty`, show `"Combat: active (hard)"` instead of just `"active"`

### Step 9: Narrator Agent

**`backend/app/services/narrator_agent.py`** — add to `_NARRATOR_FINAL_TOOLS`:
`"balance_encounter"`, `"generate_monster"`, `"award_xp"`

### Step 10: Argument Aliases

**`backend/app/services/tool_service.py`** — add to `_ARGUMENT_ALIASES`:

```python
    "generate_monster": {"type": "creature_type", "monster_type": "creature_type"},
    "balance_encounter": {"crs": "enemy_crs", "enemies": "enemy_crs", "difficulty": "desired_difficulty"},
```

### Step 11: Frontend Renderer

**`frontend/src/components/tools/renderers/EncounterRenderer.tsx`** (CREATE)

Multi-type renderer dispatching on `data.type`:

**Types handled:**
- `encounter_balance` — Difficulty badge (green/amber/orange/red), XP bar showing adjusted_xp vs thresholds, enemy CR pills, party threshold breakdown, recommendation text
- `monster_generated` — Compact stat block card: name + CR badge + creature type icon, HP/AC/attack stats, 6 ability scores in mini grid (reuse pattern from GamePanel CharacterCard)
- `xp_reward` — Gold/amber theme, total XP header, per-character breakdown with XP gained + new total, green glow on level-up rows, defeated enemies summary

**Difficulty color map:**
```typescript
const DIFFICULTY_COLORS = {
  easy:   { bg: "bg-green-900/30",  text: "text-green-300",  border: "border-green-700/40" },
  medium: { bg: "bg-amber-900/30",  text: "text-amber-300",  border: "border-amber-700/40" },
  hard:   { bg: "bg-orange-900/30", text: "text-orange-300", border: "border-orange-700/40" },
  deadly: { bg: "bg-red-900/30",    text: "text-red-300",    border: "border-red-700/40" },
};
```

**Container**: Standard card `bg-gray-800/30 rounded-lg px-3 py-2.5 border border-gray-700/30 space-y-2`

### Step 12: Register Renderer

**`frontend/src/components/tools/renderers/index.ts`** — append:

```typescript
// Phase 14 — Encounter Balancing
import { EncounterRenderer } from "./EncounterRenderer";
registerToolRenderer("encounter_balance", EncounterRenderer);
registerToolRenderer("monster_generated", EncounterRenderer);
registerToolRenderer("xp_reward", EncounterRenderer);
```

### Step 13: Initiative Difficulty Badge

**`frontend/src/components/tools/renderers/InitiativeOrderRenderer.tsx`**:

- Add optional `encounter_difficulty?: { difficulty: string; adjusted_xp: number; multiplier: number }` to data interface
- Show colored difficulty pill next to "Round N" badge when present

### Step 14: GamePanel Combat Indicator

**`frontend/src/components/rpg/GamePanel.tsx`**:

- Add `DIFFICULTY_PILL_STYLES` constant (same green/amber/orange/red scheme)
- Enhance combat indicator section (lines 537-541): show difficulty pill alongside "Combat in Progress!" when `gameState.combat?.encounter_difficulty` exists
- Combat state already flows through `get_game_state` (session.py line 90-101), so `encounter_difficulty` in `combat_state` will automatically appear

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| No player characters | `balance_encounter` and `award_xp` return error JSON |
| CR as float (0.25), string ("1/4"), or int (2) | `normalize_cr()` handles all formats |
| `encounter_balancing_enabled=False` | All 3 tools return disabled message; `start_combat` unchanged |
| Empty/invalid `enemy_crs` string | `balance_encounter` returns error |
| Duplicate monster name | `generate_monster` appends " (CR X)" suffix |
| No enemies for `award_xp` | Returns error: "No defeated enemies found" |
| CR reverse lookup miss | `estimate_cr_from_hp` uses closest match, defaults to CR 1 |
| Mixed player/non-player in combat | Difficulty injected; player-only combat has no difficulty |
| LLM sends `type` instead of `creature_type` | Argument alias remaps it |

---

## Verification

1. **Backend starts**: `cd backend && uvicorn app.main:app --reload` — no import errors
2. **TypeScript**: `cd frontend && npx tsc --noEmit` — no type errors
3. **Chrome MCP end-to-end test**:
   - Start new game, create 2 player characters (L3 Fighter + L2 Wizard)
   - Ask LLM: "Generate a CR 2 goblin boss and two CR 1/4 goblins"
   - Verify `monster_generated` renderer shows stat blocks with CR badges
   - Ask LLM: "Check the difficulty of fighting these goblins"
   - Verify `encounter_balance` renderer shows difficulty rating with XP bar
   - Ask LLM: "Start combat with all characters and goblins"
   - Verify `initiative_order` renderer shows difficulty badge
   - Verify GamePanel shows difficulty pill next to "Combat in Progress!"
   - End combat, ask LLM to award XP
   - Verify `xp_reward` renderer shows XP distribution and any level-ups
4. **Feature gate**: Set `ENCOUNTER_BALANCING_ENABLED=false`, verify tools return disabled message and `start_combat` has no difficulty key
