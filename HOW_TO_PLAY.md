# How to Play: D&D 5e RPG Engine

A complete guide to playing Dungeons & Dragons 5th Edition through the chat interface. The LLM acts as your Dungeon Master, using 41 built-in tools across 9 game systems to run a fully rules-compliant tabletop RPG experience.

---

## Table of Contents

1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [Gameplay Walkthrough](#gameplay-walkthrough)
4. [Tool Reference by Category](#tool-reference-by-category)
5. [Dice Notation](#dice-notation)
6. [D&D 5e Quick Reference](#dd-5e-quick-reference)
7. [UI Guide](#ui-guide)
8. [Tips & Tricks](#tips--tricks)

---

## Overview

### What Is This?

This is a fully functional D&D 5th Edition game engine embedded in a chat application. Instead of rolling physical dice and tracking stats on paper, the LLM (your AI Dungeon Master) uses a suite of 41 tools to:

- Roll dice with proper D&D notation
- Create and manage characters with auto-calculated stats
- Run turn-based combat with initiative, attacks, and spells
- Track inventory, equipment, and encumbrance
- Build a connected game world with locations and NPCs
- Manage quests with objectives and rewards
- Handle resting and recovery mechanics

### How It Works

You speak to the AI in natural language — just like you would to a human DM. The AI interprets your intent, calls the appropriate game tools behind the scenes, and narrates the results. You never need to type tool names or parameters manually.

**Example flow:**
1. You say: *"I want to attack the goblin with my longsword"*
2. The AI calls the `attack` tool with your character, the goblin, and the weapon
3. The tool rolls a d20 + your modifiers vs the goblin's AC
4. If it hits, damage is rolled and applied automatically
5. The AI narrates the result: *"Your longsword cleaves through the goblin's leather armor for 8 slashing damage!"*

All game state is persisted in the database — your characters, locations, quests, and progress are saved across conversations.

---

## Getting Started

### Step 1: Start a Conversation

Open the app and create a new conversation (or use an existing one). All RPG tools are enabled by default.

### Step 2: Initialize a Game Session

Simply ask the AI to start a game:

> **You:** "Let's play D&D! Start a new game session called The Lost Mines."

The AI will call `init_game_session` to create (or resume) a session tied to your conversation.

### Step 3: Create Your Character

Describe the character you want:

> **You:** "Create a level 3 wood elf ranger named Thalion with 16 Dex, 14 Con, 12 Wis, and 10 in everything else."

The AI calls `create_character` and auto-calculates:
- **HP** based on class hit die + Constitution modifier
- **Ability modifiers** from your scores
- **Proficiency bonus** from your level
- **Spell slots** for spellcasting classes

### Step 4: Set the Scene

Ask the AI to build the world:

> **You:** "We start in the village of Phandalin. There's a tavern called the Stonehill Inn and a dark forest to the north."

The AI creates locations, connects them, sets the environment, and places your character.

### Step 5: Play!

From here, just talk naturally. The AI handles all the mechanics:

> **You:** "I walk into the tavern and look around for anyone suspicious."
>
> **You:** "I draw my bow and shoot the bandit."
>
> **You:** "Can I persuade the guard to let us through?"

---

## Gameplay Walkthrough

Here's a complete first-session example showing how the tools work together.

### Scene 1: Character Creation

> **You:** "I want to play a human fighter named Kael, level 1, with 16 Str, 14 Con, 12 Dex, 10 Int, 10 Wis, 8 Cha."

*AI creates Kael: 12 HP, AC 10, proficiency +2, Str modifier +3*

> **You:** "Give Kael a longsword and chain mail armor."

*AI calls `create_item` for each, then `give_item` and `equip_item`. Kael's AC updates to 16 (chain mail).*

### Scene 2: Exploration

> **You:** "I head north into the forest."

*AI calls `move_to` → Kael enters Darkwood Forest. Calls `look_around` → describes the surroundings.*

> **You:** "I search the area for tracks. Perception check?"

*AI calls `roll_check` with Kael, wisdom, DC 12 → rolls d20 + Wis modifier → "You notice goblin tracks leading deeper into the woods."*

### Scene 3: Combat

> **You:** "I follow the tracks and find the goblin camp. Let's fight!"

*AI calls `create_character` for 2 goblins (as NPCs), then `start_combat` with all combatants → rolls initiative for everyone → shows turn order.*

> **AI:** "Initiative order: Kael (17), Goblin 1 (12), Goblin 2 (8). It's your turn, Kael!"

> **You:** "I attack Goblin 1 with my longsword."

*AI calls `attack` → d20+5 (Str+Prof) vs AC 15 → hit! → 1d8+3 slashing → 7 damage.*

> **You:** "End my turn."

*AI calls `next_turn` → Goblin 1's turn → AI decides the goblin attacks Kael → rolls attack and damage.*

### Scene 4: After Combat

> **You:** "I loot the goblins and take a short rest."

*AI manages inventory transfers, then calls `short_rest` → Kael spends a hit die → heals 1d10+2 HP.*

> **You:** "How much XP did we get?"

*AI calls `update_character` with `add_xp: 100` → "Kael gains 100 XP (100/300 to level 2)."*

---

## Tool Reference by Category

### Phase 0: Original Die Roll (1 tool)

| Tool | Parameters | Description |
|------|-----------|-------------|
| `roll_d20` | `modifier?` (int), `num_dice?` (int) | Roll one or more d20s with an optional flat modifier |

### Phase 1: Dice & Math System (3 tools)

| Tool | Parameters | Description |
|------|-----------|-------------|
| `roll_dice` | **`notation`** (str), `label?` (str) | Roll using full D&D notation: `2d6+3`, `4d6kh3`, `1d20!` |
| `roll_check` | **`character_name`** (str), **`ability`** (str), `dc?` (int=10), `advantage?` (bool), `disadvantage?` (bool) | Ability check: d20 + modifier vs DC |
| `roll_save` | **`character_name`** (str), **`ability`** (str), `dc?` (int=10) | Saving throw: d20 + modifier vs DC |

### Phase 2: Character Management (4 tools)

| Tool | Parameters | Description |
|------|-----------|-------------|
| `create_character` | **`name`** (str), `race?` (str=Human), `char_class?` (str=Fighter), `level?` (int=1), `strength?`..`charisma?` (int=10), `is_player?` (bool=true) | Create a character with auto-calculated HP, modifiers, proficiency |
| `get_character` | **`name`** (str) | View full character sheet |
| `update_character` | **`name`** (str), `hp_change?` (int), `add_condition?` (str), `remove_condition?` (str), `add_xp?` (int), `set_armor_class?` (int) | Modify HP, conditions, XP (auto-levels), AC |
| `list_characters` | *(none)* | List all characters in the session |

### Phase 3: Combat System (10 tools)

| Tool | Parameters | Description |
|------|-----------|-------------|
| `start_combat` | **`combatant_names`** (str[]) | Begin combat, roll initiative, set turn order |
| `get_combat_status` | *(none)* | View turn order, HP, conditions, current turn |
| `next_turn` | *(none)* | Advance to next combatant's turn |
| `end_combat` | *(none)* | End the combat encounter |
| `attack` | **`attacker`** (str), **`target`** (str), `weapon?` (str=unarmed), `advantage?` (bool), `disadvantage?` (bool) | Attack roll: d20 + modifier + proficiency vs AC, auto-rolls damage on hit |
| `cast_spell` | **`caster`** (str), **`spell_name`** (str), `target?` (str), `level?` (int) | Cast an SRD spell, consumes spell slot, applies effects |
| `heal` | **`healer`** (str), **`target`** (str), `amount?` (int), `spell?` (str) | Heal by flat amount or healing spell |
| `take_damage` | **`character`** (str), **`damage`** (int), `damage_type?` (str=bludgeoning) | Apply damage, triggers death saves at 0 HP |
| `death_save` | **`character`** (str) | Death saving throw: 10+ success, <10 failure, nat 20 = regain 1 HP |
| `combat_action` | **`character`** (str), **`action`** (str) | Non-attack action: dodge, dash, disengage, help, hide |

### Phase 4: Inventory & Items (6 tools)

| Tool | Parameters | Description |
|------|-----------|-------------|
| `create_item` | **`name`** (str), **`item_type`** (str), `description?` (str), `weight?` (num), `value_gp?` (int), `properties?` (str/JSON), `rarity?` (str) | Create an item template (weapon, armor, consumable, quest, scroll, misc) |
| `give_item` | **`character`** (str), **`item_name`** (str), `quantity?` (int=1) | Add item to a character's inventory |
| `equip_item` | **`character`** (str), **`item_name`** (str) | Equip an item (updates AC for armor) |
| `unequip_item` | **`character`** (str), **`item_name`** (str) | Unequip an item (resets AC if armor) |
| `get_inventory` | **`character`** (str) | View full inventory: items, weight, capacity, equipped |
| `transfer_item` | **`from_character`** (str), **`to_character`** (str), **`item_name`** (str), `quantity?` (int=1) | Move items between characters |

### Phase 5: World & Spatial (5 tools)

| Tool | Parameters | Description |
|------|-----------|-------------|
| `create_location` | **`name`** (str), `description?` (str), `biome?` (str) | Create a location (town, forest, dungeon, cave, mountain, etc.) |
| `connect_locations` | **`location1`** (str), **`location2`** (str), **`direction`** (str) | Link two locations bidirectionally (north/south, east/west, up/down) |
| `move_to` | **`character`** (str), `direction?` (str), `location_name?` (str) | Move character by direction or to a named location |
| `look_around` | *(none)* | Describe current location: exits, characters, NPCs, environment |
| `set_environment` | `time_of_day?` (str), `weather?` (str), `season?` (str) | Update world conditions |

**Environment options:**
- **Time of day:** dawn, morning, noon, afternoon, dusk, evening, night, midnight
- **Weather:** clear, cloudy, rain, storm, snow, fog, wind
- **Season:** spring, summer, autumn, winter

### Phase 6: NPC System (4 tools)

| Tool | Parameters | Description |
|------|-----------|-------------|
| `create_npc` | **`name`** (str), `description?` (str), `location?` (str), `disposition?` (str=neutral) | Create NPC with personality and location |
| `talk_to_npc` | **`npc_name`** (str), `topic?` (str) | Start conversation — returns context, memories, RP guidance |
| `update_npc_relationship` | **`npc_name`** (str), `character?` (str), `disposition_change?` (str), `familiarity_change?` (str) | Shift NPC attitude or familiarity |
| `npc_remember` | **`npc_name`** (str), **`event`** (str) | Record an event in NPC's memory for future interactions |

**Disposition scale:** hostile → unfriendly → neutral → friendly → helpful

**Familiarity scale:** stranger → acquaintance → friend → close_friend

### Phase 7: Quest System (4 tools)

| Tool | Parameters | Description |
|------|-----------|-------------|
| `create_quest` | **`title`** (str), `description?` (str), `objectives?` (str/JSON), `rewards?` (str/JSON) | Create quest with objectives and rewards |
| `update_quest_objective` | **`quest_title`** (str), **`objective_index`** (int), `completed?` (bool=true) | Mark objective complete/incomplete by index |
| `complete_quest` | **`quest_title`** (str) | Complete quest, distribute XP and gold to all PCs |
| `get_quest_journal` | *(none)* | View all quests: active, completed, and failed |

### Phase 8: Rest & Recovery (2 tools)

| Tool | Parameters | Description |
|------|-----------|-------------|
| `short_rest` | **`character`** (str), `hit_dice_to_spend?` (int=1) | Spend hit dice to heal (roll hit die + CON modifier per die) |
| `long_rest` | **`character`** (str) | Full HP restore, recover spell slots, reset death saves, remove unconscious |

### Phase 9: Session Management (2 tools)

| Tool | Parameters | Description |
|------|-----------|-------------|
| `init_game_session` | `world_name?` (str="The Realm") | Initialize or resume an RPG session for this conversation |
| `get_game_state` | *(none)* | Full snapshot: characters, location, quests, NPCs, combat, environment |

> **Bold** parameters are required. Parameters with `?` are optional (defaults shown after `=`).

---

## Dice Notation

The `roll_dice` tool supports full D&D dice notation. Here's the complete syntax:

### Basic Rolls

| Notation | Meaning | Example |
|----------|---------|---------|
| `XdY` | Roll X dice with Y sides | `2d6` → roll two six-sided dice |
| `XdY+N` | Roll + flat modifier | `1d20+5` → d20 plus 5 |
| `XdY-N` | Roll - flat modifier | `2d8-1` → 2d8 minus 1 |

### Keep & Drop

| Notation | Meaning | Example |
|----------|---------|---------|
| `khN` | Keep highest N dice | `4d6kh3` → roll 4d6, keep best 3 (ability score generation) |
| `klN` | Keep lowest N dice | `2d20kl1` → disadvantage (keep the lower roll) |
| `dhN` | Drop highest N dice | `4d6dh1` → roll 4d6, drop the highest |
| `dlN` | Drop lowest N dice | `4d6dl1` → roll 4d6, drop the lowest |

### Special Mechanics

| Notation | Meaning | Example |
|----------|---------|---------|
| `!` | Exploding dice (reroll on max, keep adding) | `2d6!` → on a 6, roll again and add |
| `r<N` | Reroll values below N (once) | `2d6r<2` → reroll any 1s (Great Weapon Fighting) |

### Common D&D Rolls

| Roll | Notation | When to Use |
|------|----------|-------------|
| Ability check | `1d20+3` | Skill check with +3 modifier |
| Advantage | `2d20kh1` | Roll 2d20, take the higher |
| Disadvantage | `2d20kl1` | Roll 2d20, take the lower |
| Ability scores | `4d6kh3` | Roll 4d6, drop lowest (x6 for all abilities) |
| Longsword damage | `1d8+3` | Weapon die + Strength modifier |
| Sneak Attack (L3) | `1d8+2d6+3` | Weapon + sneak attack dice + modifier |
| Fireball | `8d6` | Level 3 Fireball damage |
| Great Weapon Fighting | `2d6r<2+4` | Greatsword, reroll 1s and 2s |
| Healing Potion | `2d4+2` | Standard healing potion |

---

## D&D 5e Quick Reference

### Ability Scores

| Ability | Abbreviation | Used For |
|---------|-------------|----------|
| Strength | STR | Melee attacks, athletics, carrying capacity |
| Dexterity | DEX | Ranged attacks, AC, initiative, stealth, acrobatics |
| Constitution | CON | Hit points, concentration saves |
| Intelligence | INT | Wizard spells, investigation, arcana, history |
| Wisdom | WIS | Cleric/ranger spells, perception, insight, survival |
| Charisma | CHA | Warlock/bard/sorcerer spells, persuasion, deception |

**Ability Modifier Formula:** `(score - 10) / 2` (rounded down)

| Score | Modifier | Score | Modifier |
|-------|----------|-------|----------|
| 1 | -5 | 12-13 | +1 |
| 2-3 | -4 | 14-15 | +2 |
| 4-5 | -3 | 16-17 | +3 |
| 6-7 | -2 | 18-19 | +4 |
| 8-9 | -1 | 20 | +5 |
| 10-11 | +0 | | |

### Classes & Hit Dice

| Class | Hit Die | Primary Ability |
|-------|---------|----------------|
| Barbarian | d12 | Strength |
| Fighter | d10 | Strength or Dexterity |
| Paladin | d10 | Strength + Charisma |
| Ranger | d10 | Dexterity + Wisdom |
| Bard | d8 | Charisma |
| Cleric | d8 | Wisdom |
| Druid | d8 | Wisdom |
| Monk | d8 | Dexterity + Wisdom |
| Rogue | d8 | Dexterity |
| Warlock | d8 | Charisma |
| Sorcerer | d6 | Charisma |
| Wizard | d6 | Intelligence |

**HP Calculation:** Level 1 = max hit die + CON modifier. Subsequent levels = average hit die (rounded up) + CON modifier per level.

### Proficiency Bonus by Level

| Levels | Bonus |
|--------|-------|
| 1–4 | +2 |
| 5–8 | +3 |
| 9–12 | +4 |
| 13–16 | +5 |
| 17–20 | +6 |

### XP Thresholds

| Level | Total XP | Level | Total XP |
|-------|----------|-------|----------|
| 1 | 0 | 11 | 85,000 |
| 2 | 300 | 12 | 100,000 |
| 3 | 900 | 13 | 120,000 |
| 4 | 2,700 | 14 | 140,000 |
| 5 | 6,500 | 15 | 165,000 |
| 6 | 14,000 | 16 | 195,000 |
| 7 | 23,000 | 17 | 225,000 |
| 8 | 34,000 | 18 | 265,000 |
| 9 | 48,000 | 19 | 305,000 |
| 10 | 64,000 | 20 | 355,000 |

### Conditions

The engine tracks these standard D&D 5e conditions:

| Condition | Effect |
|-----------|--------|
| **Blinded** | Can't see; auto-fail sight checks; attacks have disadvantage; attacks against have advantage |
| **Charmed** | Can't attack the charmer; charmer has advantage on social checks |
| **Deafened** | Can't hear; auto-fail hearing checks |
| **Exhaustion** | Cumulative penalties (disadvantage → speed halved → ... → death) |
| **Frightened** | Disadvantage on checks/attacks while source is in sight; can't move closer |
| **Grappled** | Speed becomes 0 |
| **Incapacitated** | Can't take actions or reactions |
| **Invisible** | Heavily obscured; attacks have advantage; attacks against have disadvantage |
| **Paralyzed** | Incapacitated + can't move/speak; auto-fail STR/DEX saves; attacks have advantage; hits within 5ft are crits |
| **Petrified** | Transformed to stone; weight x10; incapacitated; resistance to all damage |
| **Poisoned** | Disadvantage on attack rolls and ability checks |
| **Prone** | Disadvantage on attacks; melee attacks against have advantage; ranged against have disadvantage |
| **Restrained** | Speed 0; attacks have disadvantage; DEX saves have disadvantage; attacks against have advantage |
| **Stunned** | Incapacitated; can't move; auto-fail STR/DEX saves; attacks against have advantage |
| **Unconscious** | Incapacitated; can't move/speak; unaware; drop held items; fall prone; auto-fail STR/DEX saves; attacks have advantage; hits within 5ft are crits |

### Spells (20 SRD Spells)

#### Cantrips (Level 0) — No spell slot required

| Spell | School | Ability | Effect |
|-------|--------|---------|--------|
| **Fire Bolt** | Evocation | INT | Ranged spell attack, 1d10 fire damage |
| **Sacred Flame** | Evocation | WIS | DEX save or 1d8 radiant damage |
| **Eldritch Blast** | Evocation | CHA | Ranged spell attack, 1d10 force damage |
| **Ray of Frost** | Evocation | INT | Ranged spell attack, 1d8 cold damage + reduce speed 10ft |

#### Level 1

| Spell | School | Ability | Effect |
|-------|--------|---------|--------|
| **Magic Missile** | Evocation | INT | Auto-hit, 3d4+3 force damage (3 darts) |
| **Cure Wounds** | Evocation | WIS | Touch, heal 1d8 + modifier |
| **Healing Word** | Evocation | WIS | Bonus action, heal 1d4 + modifier (ranged) |
| **Shield** | Abjuration | INT | Reaction, +5 AC until next turn |
| **Thunderwave** | Evocation | INT | 15ft cube, CON save, 2d8 thunder damage |
| **Burning Hands** | Evocation | INT | 15ft cone, DEX save, 3d6 fire damage |
| **Guiding Bolt** | Evocation | WIS | Ranged spell attack, 4d6 radiant + next attack has advantage |
| **Inflict Wounds** | Necromancy | WIS | Melee spell attack, 3d10 necrotic damage |

#### Level 2

| Spell | School | Ability | Effect |
|-------|--------|---------|--------|
| **Scorching Ray** | Evocation | INT | 3 rays, ranged spell attack each, 2d6 fire per ray |
| **Hold Person** | Enchantment | WIS | WIS save or target is paralyzed |
| **Spiritual Weapon** | Evocation | WIS | Melee spell attack, 1d8 force damage |

#### Level 3

| Spell | School | Ability | Effect |
|-------|--------|---------|--------|
| **Fireball** | Evocation | INT | 20ft radius, DEX save, 8d6 fire damage |
| **Lightning Bolt** | Evocation | INT | 100ft line, DEX save, 8d6 lightning damage |
| **Counterspell** | Abjuration | INT | Counter spells of 3rd level or lower automatically |
| **Revivify** | Necromancy | WIS | Touch a creature dead <1 minute, return with 1 HP |

#### Level 4

| Spell | School | Ability | Effect |
|-------|--------|---------|--------|
| **Polymorph** | Transmutation | INT | WIS save (unwilling), transform creature into a new form |

---

## UI Guide

### RPG Dashboard Panel

Click the castle icon in the sidebar to open the **RPG Dashboard** — a real-time panel that displays:

- **World** — The game world name, time of day, and weather
- **Location** — Current location with biome icon (forest, dungeon, tavern, etc.)
- **Combat Indicator** — Red banner when combat is active
- **Party** — All characters with HP bars (color-coded: green > yellow > red)
- **Quests** — Active quest titles
- **NPCs** — Known NPCs with their disposition tags

The dashboard updates automatically after every game action. Use `get_game_state` (or just ask "what's the game status?") to refresh it.

### Tool Result Renderers

When the AI uses RPG tools, the results appear as rich UI cards in the chat:

| Renderer | Shows |
|----------|-------|
| **Dice Roll** | Animated dice with individual results, kept/dropped indicators, totals |
| **Character Sheet** | Full stat block with abilities, HP, AC, conditions |
| **Character List** | Grid of all party members and NPCs |
| **Check/Save Result** | Roll breakdown, DC, success/failure with nat 20/1 highlights |
| **Attack Result** | Attack roll vs AC, hit/miss, damage on hit, critical hits |
| **Spell Cast** | Spell name, slot used, damage/healing, save DC |
| **Damage Result** | Damage applied, remaining HP, damage type |
| **Heal Result** | HP restored, current/max HP |
| **Death Save** | Success/failure tracking, stabilized/dead outcomes |
| **Combat Action** | Action type and mechanical effect |
| **Initiative Order** | Turn order with HP and current-turn indicator |
| **Inventory** | Item list with weight, equipped status, total capacity |
| **Location** | Location name, biome, exits, who's present |
| **NPC** | Name, disposition, familiarity, memories |
| **Quest Journal** | Active/completed quests with objective checklists |
| **Rest Result** | HP recovered, hit dice spent, spell slots restored |
| **Game State** | Full world snapshot (same data as the dashboard) |

---

## Tips & Tricks

### Getting the Best Gameplay

1. **Be descriptive, not mechanical.** Say *"I try to sneak past the guards"* instead of *"roll stealth."* The AI will choose the right check and set an appropriate DC.

2. **Name your characters distinctly.** The engine matches characters by name (case-insensitive), so avoid similar names like "Guard 1" and "Guard 2" — use "Grimjaw" and "Ironhelm" instead.

3. **Let the AI set DCs.** Instead of specifying *"DC 15 perception check,"* say *"I search the room carefully."* The AI will pick a DC based on the narrative difficulty.

4. **Use the game state command.** If you lose track, just say *"What's the current game status?"* to get a full snapshot.

5. **The AI remembers NPCs.** After talking to an NPC, the engine stores the interaction in that NPC's memory. Bring up past events — the NPC will recall them.

6. **Create items before giving them.** The engine needs items to exist as templates first. Say *"Create a +1 longsword that does 1d8+1 slashing damage, then give it to Kael."*

7. **Use short rests strategically.** Short rests let you spend hit dice to heal without a full reset. Long rests restore everything but should be narratively appropriate.

8. **Ask for the quest journal.** If you forget your objectives, say *"Show me the quest journal"* — it tracks active, completed, and failed quests.

### Combat Tips

- **Advantage/disadvantage matters.** Describe situational factors: *"I attack from hiding"* (advantage) or *"I'm blinded by the flash"* (disadvantage).
- **Use combat actions.** Dodge, Dash, Disengage, Help, and Hide are powerful tactical options beyond just attacking.
- **Watch HP bars.** The dashboard shows real-time HP for all combatants. Plan your heals accordingly.
- **Death saves are automatic.** At 0 HP, the engine tracks successes and failures. A nat 20 brings you back with 1 HP.

### World Building Tips

- **Connect locations with directions.** Build a map by linking locations: *"Connect the tavern to the town square going east."*
- **Set the mood with environment.** *"Set the weather to storm and time to midnight"* changes the atmosphere for the whole session.
- **NPCs have relationship tracking.** Build trust over time — disposition shifts from hostile to helpful based on your interactions.
- **Quests can have multiple objectives.** Create complex quests with JSON objectives and rewards that auto-distribute on completion.

### Advanced Usage

- **Roll ability scores the classic way:** Ask the AI to *"Roll 4d6 drop lowest, six times, for my ability scores."*
- **Upcast spells:** *"Cast Cure Wounds at 2nd level on Thalion"* — the AI will use a higher spell slot for more healing.
- **Multiclass characters:** Create a character with one class, then narratively track your multiclass progression with the AI.
- **Run multiple combatants:** The AI can control NPC and monster turns automatically during combat — just focus on your own character's actions.
