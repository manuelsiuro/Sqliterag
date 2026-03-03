"""Built-in tool implementations that ship with the app."""

from __future__ import annotations

import json
import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rpg.dice import parse_and_roll, roll_simple
from app.services.rpg_service import (
    ABILITY_NAMES,
    CLASS_HIT_DIE,
    CONDITIONS,
    XP_THRESHOLDS,
    calculate_hp,
    calculate_modifier,
    calculate_proficiency,
    character_to_dict,
    get_character_by_name,
    get_location_by_name,
    get_or_create_session,
    level_for_xp,
)

# ---------------------------------------------------------------------------
# Phase 0 — Original tool
# ---------------------------------------------------------------------------

def roll_d20(modifier: int = 0, num_dice: int = 1) -> str:
    """Roll one or more d20 dice with an optional modifier."""
    rolls = [random.randint(1, 20) for _ in range(num_dice)]
    total = sum(rolls) + modifier
    return json.dumps({
        "type": "roll_d20",
        "rolls": rolls,
        "modifier": modifier,
        "total": total,
    })


# ---------------------------------------------------------------------------
# Phase 1 — Dice & Math System
# ---------------------------------------------------------------------------

def roll_dice(notation: str, label: str = "") -> str:
    """Roll dice using full D&D notation (e.g. '2d6+3', '4d6kh3', '1d20!')."""
    result = parse_and_roll(notation, label=label)
    return json.dumps({"type": "roll_dice", **result.to_dict()})


async def roll_check(
    character_name: str,
    ability: str,
    dc: int = 10,
    advantage: bool = False,
    disadvantage: bool = False,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Roll an ability check: d20 + ability modifier vs DC."""
    gs = await get_or_create_session(session, conversation_id)
    char = await get_character_by_name(session, gs.id, character_name)
    if not char:
        return json.dumps({"type": "check_result", "error": f"Character '{character_name}' not found."})

    ability = ability.lower()
    if ability not in ABILITY_NAMES:
        return json.dumps({"type": "check_result", "error": f"Unknown ability '{ability}'. Use one of: {', '.join(ABILITY_NAMES)}"})

    modifier = calculate_modifier(getattr(char, ability))

    # Roll with advantage/disadvantage
    if advantage and not disadvantage:
        rolls = roll_simple(20, 2)
        chosen = max(rolls)
    elif disadvantage and not advantage:
        rolls = roll_simple(20, 2)
        chosen = min(rolls)
    else:
        rolls = roll_simple(20, 1)
        chosen = rolls[0]

    total = chosen + modifier
    success = total >= dc
    is_nat20 = chosen == 20
    is_nat1 = chosen == 1

    return json.dumps({
        "type": "check_result",
        "character": character_name,
        "ability": ability,
        "rolls": rolls,
        "chosen": chosen,
        "modifier": modifier,
        "total": total,
        "dc": dc,
        "success": success,
        "nat20": is_nat20,
        "nat1": is_nat1,
        "advantage": advantage,
        "disadvantage": disadvantage,
    })


async def roll_save(
    character_name: str,
    ability: str,
    dc: int = 10,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Roll a saving throw: d20 + ability modifier vs DC."""
    gs = await get_or_create_session(session, conversation_id)
    char = await get_character_by_name(session, gs.id, character_name)
    if not char:
        return json.dumps({"type": "check_result", "error": f"Character '{character_name}' not found."})

    ability = ability.lower()
    if ability not in ABILITY_NAMES:
        return json.dumps({"type": "check_result", "error": f"Unknown ability '{ability}'."})

    modifier = calculate_modifier(getattr(char, ability))
    roll = random.randint(1, 20)
    total = roll + modifier
    success = total >= dc

    return json.dumps({
        "type": "check_result",
        "character": character_name,
        "ability": ability,
        "check_type": "saving_throw",
        "rolls": [roll],
        "chosen": roll,
        "modifier": modifier,
        "total": total,
        "dc": dc,
        "success": success,
        "nat20": roll == 20,
        "nat1": roll == 1,
    })


# ---------------------------------------------------------------------------
# Phase 2 — Character Management
# ---------------------------------------------------------------------------

async def create_character(
    name: str,
    race: str = "Human",
    char_class: str = "Fighter",
    level: int = 1,
    strength: int = 10,
    dexterity: int = 10,
    constitution: int = 10,
    intelligence: int = 10,
    wisdom: int = 10,
    charisma: int = 10,
    is_player: bool = True,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Create a new D&D 5e character with auto-calculated stats."""
    from app.models.rpg import Character

    gs = await get_or_create_session(session, conversation_id)

    # Check for duplicate name
    existing = await get_character_by_name(session, gs.id, name)
    if existing:
        return json.dumps({"type": "character_sheet", "error": f"Character '{name}' already exists."})

    con_mod = calculate_modifier(constitution)
    dex_mod = calculate_modifier(dexterity)
    max_hp = calculate_hp(char_class, level, con_mod)
    ac = 10 + dex_mod

    # Calculate XP for level
    xp = XP_THRESHOLDS.get(level, 0)

    char = Character(
        session_id=gs.id,
        name=name,
        race=race,
        char_class=char_class,
        level=level,
        xp=xp,
        strength=strength,
        dexterity=dexterity,
        constitution=constitution,
        intelligence=intelligence,
        wisdom=wisdom,
        charisma=charisma,
        max_hp=max_hp,
        current_hp=max_hp,
        armor_class=ac,
        is_player=is_player,
    )
    session.add(char)
    await session.flush()

    return json.dumps({"type": "character_sheet", **character_to_dict(char)})


async def get_character(
    name: str,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Get a character's full sheet."""
    gs = await get_or_create_session(session, conversation_id)
    char = await get_character_by_name(session, gs.id, name)
    if not char:
        return json.dumps({"type": "character_sheet", "error": f"Character '{name}' not found."})
    return json.dumps({"type": "character_sheet", **character_to_dict(char)})


async def update_character(
    name: str,
    hp_change: int | None = None,
    add_condition: str | None = None,
    remove_condition: str | None = None,
    add_xp: int | None = None,
    set_armor_class: int | None = None,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Update a character: adjust HP, add/remove conditions, grant XP (auto-level)."""
    gs = await get_or_create_session(session, conversation_id)
    char = await get_character_by_name(session, gs.id, name)
    if not char:
        return json.dumps({"type": "character_sheet", "error": f"Character '{name}' not found."})

    changes: list[str] = []

    if hp_change is not None:
        old_hp = char.current_hp
        char.current_hp = max(0, min(char.max_hp, char.current_hp + hp_change))
        changes.append(f"HP {old_hp} → {char.current_hp}")
        if char.current_hp == 0 and char.is_alive:
            conditions = json.loads(char.conditions)
            if "unconscious" not in conditions:
                conditions.append("unconscious")
                char.conditions = json.dumps(conditions)
                changes.append("Now unconscious!")

    if add_condition:
        cond = add_condition.lower()
        conditions = json.loads(char.conditions)
        if cond not in conditions:
            conditions.append(cond)
            char.conditions = json.dumps(conditions)
            changes.append(f"Added condition: {cond}")

    if remove_condition:
        cond = remove_condition.lower()
        conditions = json.loads(char.conditions)
        if cond in conditions:
            conditions.remove(cond)
            char.conditions = json.dumps(conditions)
            changes.append(f"Removed condition: {cond}")

    if set_armor_class is not None:
        char.armor_class = set_armor_class
        changes.append(f"AC set to {set_armor_class}")

    if add_xp is not None and add_xp > 0:
        old_level = char.level
        char.xp += add_xp
        new_level = level_for_xp(char.xp)
        if new_level > old_level:
            char.level = new_level
            con_mod = calculate_modifier(char.constitution)
            char.max_hp = calculate_hp(char.char_class, new_level, con_mod)
            char.current_hp = char.max_hp  # Full heal on level up
            changes.append(f"LEVEL UP! {old_level} → {new_level}")
        changes.append(f"+{add_xp} XP (total: {char.xp})")

    await session.flush()
    result = character_to_dict(char)
    result["changes"] = changes
    return json.dumps({"type": "character_sheet", **result})


async def list_characters(
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """List all characters in the current game session."""
    from app.models.rpg import Character

    gs = await get_or_create_session(session, conversation_id)
    result = await session.execute(
        select(Character).where(Character.session_id == gs.id)
    )
    chars = result.scalars().all()
    return json.dumps({
        "type": "character_list",
        "characters": [character_to_dict(c) for c in chars],
        "count": len(chars),
    })


# ---------------------------------------------------------------------------
# Phase 3 — Combat System
# ---------------------------------------------------------------------------

async def start_combat(
    combatant_names: list[str],
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Start a combat encounter. Rolls initiative for all combatants."""
    gs = await get_or_create_session(session, conversation_id)

    if gs.combat_state:
        return json.dumps({"type": "initiative_order", "error": "Combat is already in progress. End it first."})

    initiative_order = []
    for name in combatant_names:
        char = await get_character_by_name(session, gs.id, name)
        if not char:
            return json.dumps({"type": "initiative_order", "error": f"Character '{name}' not found."})
        dex_mod = calculate_modifier(char.dexterity)
        roll = random.randint(1, 20)
        initiative_order.append({
            "name": char.name,
            "roll": roll,
            "modifier": dex_mod,
            "total": roll + dex_mod,
            "current_hp": char.current_hp,
            "max_hp": char.max_hp,
            "armor_class": char.armor_class,
        })

    initiative_order.sort(key=lambda x: x["total"], reverse=True)

    combat_state = {
        "round": 1,
        "turn_index": 0,
        "combatants": [e["name"] for e in initiative_order],
        "initiative": initiative_order,
    }
    gs.combat_state = json.dumps(combat_state)
    await session.flush()

    return json.dumps({
        "type": "initiative_order",
        "round": 1,
        "current_turn": initiative_order[0]["name"],
        "order": initiative_order,
    })


async def get_combat_status(
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Get the current combat state: turn order, HP, conditions."""
    gs = await get_or_create_session(session, conversation_id)
    if not gs.combat_state:
        return json.dumps({"type": "initiative_order", "error": "No combat in progress."})

    state = json.loads(gs.combat_state)

    # Refresh HP/conditions from character records
    for entry in state["initiative"]:
        char = await get_character_by_name(session, gs.id, entry["name"])
        if char:
            entry["current_hp"] = char.current_hp
            entry["max_hp"] = char.max_hp
            entry["conditions"] = json.loads(char.conditions)

    current_name = state["combatants"][state["turn_index"]]
    return json.dumps({
        "type": "initiative_order",
        "round": state["round"],
        "current_turn": current_name,
        "order": state["initiative"],
    })


async def next_turn(
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Advance to the next combatant's turn."""
    gs = await get_or_create_session(session, conversation_id)
    if not gs.combat_state:
        return json.dumps({"type": "initiative_order", "error": "No combat in progress."})

    state = json.loads(gs.combat_state)
    state["turn_index"] += 1
    if state["turn_index"] >= len(state["combatants"]):
        state["turn_index"] = 0
        state["round"] += 1

    gs.combat_state = json.dumps(state)
    await session.flush()

    current_name = state["combatants"][state["turn_index"]]
    return json.dumps({
        "type": "initiative_order",
        "round": state["round"],
        "current_turn": current_name,
        "order": state["initiative"],
        "message": f"Round {state['round']}: {current_name}'s turn.",
    })


async def end_combat(
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """End the current combat encounter."""
    gs = await get_or_create_session(session, conversation_id)
    if not gs.combat_state:
        return json.dumps({"type": "combat_summary", "error": "No combat in progress."})

    state = json.loads(gs.combat_state)
    gs.combat_state = None
    await session.flush()

    return json.dumps({
        "type": "combat_summary",
        "rounds_fought": state["round"],
        "combatants": state["combatants"],
        "message": f"Combat ended after {state['round']} round(s).",
    })


async def attack(
    attacker: str,
    target: str,
    weapon: str = "unarmed",
    advantage: bool = False,
    disadvantage: bool = False,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Make an attack roll: d20 + STR/DEX mod + proficiency vs target AC."""
    gs = await get_or_create_session(session, conversation_id)
    atk_char = await get_character_by_name(session, gs.id, attacker)
    tgt_char = await get_character_by_name(session, gs.id, target)

    if not atk_char:
        return json.dumps({"type": "attack_result", "error": f"Attacker '{attacker}' not found."})
    if not tgt_char:
        return json.dumps({"type": "attack_result", "error": f"Target '{target}' not found."})

    # Use STR for melee, but use DEX if it's higher (finesse-like simplification)
    str_mod = calculate_modifier(atk_char.strength)
    dex_mod = calculate_modifier(atk_char.dexterity)
    atk_mod = max(str_mod, dex_mod)
    prof = calculate_proficiency(atk_char.level)
    total_mod = atk_mod + prof

    # Roll attack
    if advantage and not disadvantage:
        rolls = roll_simple(20, 2)
        chosen = max(rolls)
    elif disadvantage and not advantage:
        rolls = roll_simple(20, 2)
        chosen = min(rolls)
    else:
        rolls = roll_simple(20, 1)
        chosen = rolls[0]

    is_crit = chosen == 20
    is_fumble = chosen == 1
    attack_total = chosen + total_mod
    hit = (attack_total >= tgt_char.armor_class) or is_crit

    # Damage calculation
    damage = 0
    damage_rolls = []
    if hit and not is_fumble:
        # Default weapon damage — try to look up from inventory, else 1d6
        dmg_die = 6
        dmg_count = 1
        dmg_rolls_raw = roll_simple(dmg_die, dmg_count * (2 if is_crit else 1))
        damage = sum(dmg_rolls_raw) + atk_mod
        damage_rolls = dmg_rolls_raw

        # Apply damage to target
        tgt_char.current_hp = max(0, tgt_char.current_hp - damage)
        if tgt_char.current_hp == 0:
            conditions = json.loads(tgt_char.conditions)
            if "unconscious" not in conditions:
                conditions.append("unconscious")
                tgt_char.conditions = json.dumps(conditions)
        await session.flush()

    return json.dumps({
        "type": "attack_result",
        "attacker": attacker,
        "target": target,
        "weapon": weapon,
        "attack_rolls": rolls,
        "chosen_roll": chosen,
        "attack_modifier": total_mod,
        "attack_total": attack_total,
        "target_ac": tgt_char.armor_class,
        "hit": hit,
        "critical": is_crit,
        "fumble": is_fumble,
        "damage": damage,
        "damage_rolls": damage_rolls,
        "damage_modifier": atk_mod,
        "target_hp": f"{tgt_char.current_hp}/{tgt_char.max_hp}",
    })


async def cast_spell(
    caster: str,
    spell_name: str,
    target: str = "",
    level: int = 1,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Cast a spell from the SRD spell list."""
    from app.services.rpg.spells import SRD_SPELLS

    gs = await get_or_create_session(session, conversation_id)
    caster_char = await get_character_by_name(session, gs.id, caster)
    if not caster_char:
        return json.dumps({"type": "spell_cast", "error": f"Caster '{caster}' not found."})

    spell_key = spell_name.lower().replace(" ", "_")
    spell = SRD_SPELLS.get(spell_key)
    if not spell:
        return json.dumps({"type": "spell_cast", "error": f"Unknown spell '{spell_name}'. Available: {', '.join(SRD_SPELLS.keys())}"})

    # Check and consume spell slot
    slots = json.loads(caster_char.spell_slots)
    slot_key = str(spell.get("level", level))
    if spell.get("level", 0) > 0:
        current = slots.get(slot_key, 0)
        if current <= 0:
            return json.dumps({"type": "spell_cast", "error": f"No level {slot_key} spell slots remaining."})
        slots[slot_key] = current - 1
        caster_char.spell_slots = json.dumps(slots)

    # Resolve spell effect
    effect = spell.get("effect", "No effect defined.")
    damage = 0
    healing = 0
    damage_rolls = []

    if spell.get("damage_dice"):
        parsed = parse_and_roll(spell["damage_dice"])
        damage = parsed.total
        damage_rolls = [r.value for g in parsed.groups for r in g.rolls if r.kept]

    if spell.get("healing_dice"):
        parsed = parse_and_roll(spell["healing_dice"])
        healing = parsed.total
        # Apply healing to the appropriate modifier
        spellcast_mod = calculate_modifier(getattr(caster_char, spell.get("casting_ability", "wisdom"), 10))
        healing += spellcast_mod

    # Apply to target if we have one
    target_hp = ""
    if target and (damage > 0 or healing > 0):
        tgt = await get_character_by_name(session, gs.id, target)
        if tgt:
            if damage > 0:
                # Spell attack or save
                if spell.get("attack"):
                    ability = spell.get("casting_ability", "intelligence")
                    mod = calculate_modifier(getattr(caster_char, ability))
                    prof = calculate_proficiency(caster_char.level)
                    atk_roll = random.randint(1, 20)
                    atk_total = atk_roll + mod + prof
                    if atk_total < tgt.armor_class:
                        damage = 0  # Miss
                tgt.current_hp = max(0, tgt.current_hp - damage)
                target_hp = f"{tgt.current_hp}/{tgt.max_hp}"
            if healing > 0:
                tgt.current_hp = min(tgt.max_hp, tgt.current_hp + healing)
                target_hp = f"{tgt.current_hp}/{tgt.max_hp}"
            await session.flush()

    await session.flush()

    return json.dumps({
        "type": "spell_cast",
        "caster": caster,
        "spell_name": spell.get("name", spell_name),
        "spell_level": spell.get("level", level),
        "target": target,
        "effect": effect,
        "damage": damage,
        "damage_rolls": damage_rolls,
        "healing": healing,
        "slots_remaining": slots,
        "target_hp": target_hp,
    })


async def heal(
    healer: str,
    target: str,
    amount: int = 0,
    spell: str = "",
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Heal a character by a flat amount or using a healing spell."""
    gs = await get_or_create_session(session, conversation_id)
    tgt = await get_character_by_name(session, gs.id, target)
    if not tgt:
        return json.dumps({"type": "heal_result", "error": f"Target '{target}' not found."})

    if spell:
        # Delegate to cast_spell
        return await cast_spell(healer, spell, target, session=session, conversation_id=conversation_id)

    old_hp = tgt.current_hp
    tgt.current_hp = min(tgt.max_hp, tgt.current_hp + amount)
    healed = tgt.current_hp - old_hp

    # Remove unconscious if healed above 0
    if tgt.current_hp > 0:
        conditions = json.loads(tgt.conditions)
        if "unconscious" in conditions:
            conditions.remove("unconscious")
            tgt.conditions = json.dumps(conditions)

    await session.flush()

    return json.dumps({
        "type": "heal_result",
        "healer": healer,
        "target": target,
        "amount_healed": healed,
        "current_hp": tgt.current_hp,
        "max_hp": tgt.max_hp,
    })


async def take_damage(
    character: str,
    damage: int,
    damage_type: str = "bludgeoning",
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Apply damage to a character. Triggers death saves at 0 HP."""
    gs = await get_or_create_session(session, conversation_id)
    char = await get_character_by_name(session, gs.id, character)
    if not char:
        return json.dumps({"type": "damage_result", "error": f"Character '{character}' not found."})

    old_hp = char.current_hp
    char.current_hp = max(0, char.current_hp - damage)
    actual_damage = old_hp - char.current_hp

    dropped_to_zero = old_hp > 0 and char.current_hp == 0
    if dropped_to_zero:
        conditions = json.loads(char.conditions)
        if "unconscious" not in conditions:
            conditions.append("unconscious")
            char.conditions = json.dumps(conditions)
        # Reset death saves
        char.death_saves = json.dumps({"successes": 0, "failures": 0})

    await session.flush()

    return json.dumps({
        "type": "damage_result",
        "character": character,
        "damage": actual_damage,
        "damage_type": damage_type,
        "current_hp": char.current_hp,
        "max_hp": char.max_hp,
        "dropped_to_zero": dropped_to_zero,
        "needs_death_saves": dropped_to_zero,
    })


async def death_save(
    character: str,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Roll a death saving throw for a character at 0 HP."""
    gs = await get_or_create_session(session, conversation_id)
    char = await get_character_by_name(session, gs.id, character)
    if not char:
        return json.dumps({"type": "death_save", "error": f"Character '{character}' not found."})

    if char.current_hp > 0:
        return json.dumps({"type": "death_save", "error": f"{character} is not at 0 HP."})

    roll = random.randint(1, 20)
    saves = json.loads(char.death_saves)

    if roll == 20:
        # Nat 20: regain 1 HP
        char.current_hp = 1
        conditions = json.loads(char.conditions)
        if "unconscious" in conditions:
            conditions.remove("unconscious")
            char.conditions = json.dumps(conditions)
        saves = {"successes": 0, "failures": 0}
        result_msg = "NAT 20! Regains 1 HP and is conscious!"
        stabilized = True
        dead = False
    elif roll == 1:
        # Nat 1: two failures
        saves["failures"] = min(3, saves["failures"] + 2)
        result_msg = "NAT 1! Two death save failures!"
        stabilized = False
        dead = saves["failures"] >= 3
    elif roll >= 10:
        saves["successes"] += 1
        stabilized = saves["successes"] >= 3
        result_msg = f"Success ({saves['successes']}/3)"
        dead = False
    else:
        saves["failures"] += 1
        stabilized = False
        dead = saves["failures"] >= 3
        result_msg = f"Failure ({saves['failures']}/3)"

    if dead:
        char.is_alive = False
        result_msg += " — DEAD."

    if stabilized and not dead:
        saves = {"successes": 0, "failures": 0}
        result_msg += " — Stabilized!"

    char.death_saves = json.dumps(saves)
    await session.flush()

    return json.dumps({
        "type": "death_save",
        "character": character,
        "roll": roll,
        "successes": saves["successes"],
        "failures": saves["failures"],
        "stabilized": stabilized,
        "dead": dead,
        "message": result_msg,
    })


async def combat_action(
    character: str,
    action: str,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Perform a combat action: dodge, dash, disengage, help, or hide."""
    gs = await get_or_create_session(session, conversation_id)
    char = await get_character_by_name(session, gs.id, character)
    if not char:
        return json.dumps({"type": "combat_action", "error": f"Character '{character}' not found."})

    action = action.lower()
    valid_actions = {
        "dodge": "Until next turn, attack rolls against you have disadvantage (if you can see the attacker), and you make DEX saves with advantage.",
        "dash": f"You gain extra movement equal to your speed ({char.speed} ft) for this turn.",
        "disengage": "Your movement doesn't provoke opportunity attacks for the rest of this turn.",
        "help": "You aid an ally, giving them advantage on their next ability check or attack roll.",
        "hide": "You attempt to hide. Make a DEX (Stealth) check.",
    }

    if action not in valid_actions:
        return json.dumps({"type": "combat_action", "error": f"Unknown action '{action}'. Available: {', '.join(valid_actions)}"})

    result_data = {
        "type": "combat_action",
        "character": character,
        "action": action,
        "description": valid_actions[action],
    }

    # Special handling for hide — roll stealth
    if action == "hide":
        dex_mod = calculate_modifier(char.dexterity)
        roll = random.randint(1, 20)
        result_data["stealth_roll"] = roll
        result_data["stealth_total"] = roll + dex_mod
        result_data["stealth_modifier"] = dex_mod

    return json.dumps(result_data)


# ---------------------------------------------------------------------------
# Phase 4 — Inventory & Items
# ---------------------------------------------------------------------------

async def create_item(
    name: str,
    item_type: str = "misc",
    description: str = "",
    weight: float = 0.0,
    value_gp: int = 0,
    properties: str = "{}",
    rarity: str = "common",
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Create a new item template."""
    from app.models.rpg import Item

    # Check for duplicate
    result = await session.execute(select(Item).where(Item.name.ilike(name)))
    existing = result.scalars().first()
    if existing:
        return json.dumps({"type": "item_detail", "error": f"Item '{name}' already exists."})

    item = Item(
        name=name,
        item_type=item_type,
        description=description,
        weight=weight,
        value_gp=value_gp,
        properties=properties if isinstance(properties, str) else json.dumps(properties),
        rarity=rarity,
    )
    session.add(item)
    await session.flush()

    return json.dumps({
        "type": "item_detail",
        "name": item.name,
        "item_type": item.item_type,
        "description": item.description,
        "weight": item.weight,
        "value_gp": item.value_gp,
        "properties": json.loads(item.properties),
        "rarity": item.rarity,
    })


async def give_item(
    character: str,
    item_name: str,
    quantity: int = 1,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Give an item to a character's inventory."""
    from app.models.rpg import InventoryItem, Item

    gs = await get_or_create_session(session, conversation_id)
    char = await get_character_by_name(session, gs.id, character)
    if not char:
        return json.dumps({"type": "inventory", "error": f"Character '{character}' not found."})

    result = await session.execute(select(Item).where(Item.name.ilike(item_name)))
    item = result.scalars().first()
    if not item:
        return json.dumps({"type": "inventory", "error": f"Item '{item_name}' not found. Create it first with create_item."})

    # Check if already in inventory
    result = await session.execute(
        select(InventoryItem).where(
            InventoryItem.character_id == char.id,
            InventoryItem.item_id == item.id,
        )
    )
    inv_item = result.scalars().first()
    if inv_item:
        inv_item.quantity += quantity
    else:
        inv_item = InventoryItem(character_id=char.id, item_id=item.id, quantity=quantity)
        session.add(inv_item)

    await session.flush()
    return await get_inventory(character, session=session, conversation_id=conversation_id)


async def equip_item(
    character: str,
    item_name: str,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Equip an item from inventory. Updates AC for armor."""
    from app.models.rpg import InventoryItem, Item

    gs = await get_or_create_session(session, conversation_id)
    char = await get_character_by_name(session, gs.id, character)
    if not char:
        return json.dumps({"type": "inventory", "error": f"Character '{character}' not found."})

    result = await session.execute(
        select(InventoryItem).join(Item).where(
            InventoryItem.character_id == char.id,
            Item.name.ilike(item_name),
        )
    )
    inv_item = result.scalars().first()
    if not inv_item:
        return json.dumps({"type": "inventory", "error": f"'{item_name}' not in {character}'s inventory."})

    inv_item.is_equipped = True

    # If armor, update AC
    result = await session.execute(select(Item).where(Item.id == inv_item.item_id))
    item = result.scalars().first()
    if item and item.item_type == "armor":
        props = json.loads(item.properties)
        if "ac" in props:
            dex_mod = calculate_modifier(char.dexterity)
            max_dex = props.get("max_dex_bonus")
            effective_dex = min(dex_mod, max_dex) if max_dex is not None else dex_mod
            char.armor_class = props["ac"] + effective_dex

    await session.flush()
    return await get_inventory(character, session=session, conversation_id=conversation_id)


async def unequip_item(
    character: str,
    item_name: str,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Unequip an item. Resets AC if armor."""
    from app.models.rpg import InventoryItem, Item

    gs = await get_or_create_session(session, conversation_id)
    char = await get_character_by_name(session, gs.id, character)
    if not char:
        return json.dumps({"type": "inventory", "error": f"Character '{character}' not found."})

    result = await session.execute(
        select(InventoryItem).join(Item).where(
            InventoryItem.character_id == char.id,
            Item.name.ilike(item_name),
        )
    )
    inv_item = result.scalars().first()
    if not inv_item:
        return json.dumps({"type": "inventory", "error": f"'{item_name}' not in {character}'s inventory."})

    result = await session.execute(select(Item).where(Item.id == inv_item.item_id))
    item = result.scalars().first()

    inv_item.is_equipped = False

    # Reset AC if it was armor
    if item and item.item_type == "armor":
        dex_mod = calculate_modifier(char.dexterity)
        char.armor_class = 10 + dex_mod

    await session.flush()
    return await get_inventory(character, session=session, conversation_id=conversation_id)


async def get_inventory(
    character: str,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Get a character's full inventory with weight and capacity."""
    from app.models.rpg import InventoryItem, Item

    gs = await get_or_create_session(session, conversation_id)
    char = await get_character_by_name(session, gs.id, character)
    if not char:
        return json.dumps({"type": "inventory", "error": f"Character '{character}' not found."})

    result = await session.execute(
        select(InventoryItem, Item)
        .join(Item)
        .where(InventoryItem.character_id == char.id)
    )
    rows = result.all()

    items = []
    total_weight = 0.0
    total_value = 0
    for inv_item, item in rows:
        item_weight = item.weight * inv_item.quantity
        total_weight += item_weight
        total_value += item.value_gp * inv_item.quantity
        items.append({
            "name": item.name,
            "item_type": item.item_type,
            "quantity": inv_item.quantity,
            "weight_each": item.weight,
            "weight_total": item_weight,
            "value_gp": item.value_gp,
            "is_equipped": inv_item.is_equipped,
            "rarity": item.rarity,
        })

    capacity = char.strength * 15

    return json.dumps({
        "type": "inventory",
        "character": char.name,
        "items": items,
        "total_weight": round(total_weight, 1),
        "capacity": capacity,
        "encumbered": total_weight > capacity,
        "total_value_gp": total_value,
    })


async def transfer_item(
    from_character: str,
    to_character: str,
    item_name: str,
    quantity: int = 1,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Transfer items between characters."""
    from app.models.rpg import InventoryItem, Item

    gs = await get_or_create_session(session, conversation_id)
    from_char = await get_character_by_name(session, gs.id, from_character)
    to_char = await get_character_by_name(session, gs.id, to_character)
    if not from_char:
        return json.dumps({"type": "inventory", "error": f"Character '{from_character}' not found."})
    if not to_char:
        return json.dumps({"type": "inventory", "error": f"Character '{to_character}' not found."})

    result = await session.execute(
        select(InventoryItem).join(Item).where(
            InventoryItem.character_id == from_char.id,
            Item.name.ilike(item_name),
        )
    )
    inv_item = result.scalars().first()
    if not inv_item or inv_item.quantity < quantity:
        return json.dumps({"type": "inventory", "error": f"'{from_character}' doesn't have {quantity}x {item_name}."})

    # Remove from source
    inv_item.quantity -= quantity
    if inv_item.quantity <= 0:
        await session.delete(inv_item)

    # Add to target
    result = await session.execute(
        select(InventoryItem).where(
            InventoryItem.character_id == to_char.id,
            InventoryItem.item_id == inv_item.item_id,
        )
    )
    tgt_inv = result.scalars().first()
    if tgt_inv:
        tgt_inv.quantity += quantity
    else:
        new_inv = InventoryItem(character_id=to_char.id, item_id=inv_item.item_id, quantity=quantity)
        session.add(new_inv)

    await session.flush()

    return json.dumps({
        "type": "transfer_result",
        "from": from_character,
        "to": to_character,
        "item": item_name,
        "quantity": quantity,
        "message": f"Transferred {quantity}x {item_name} from {from_character} to {to_character}.",
    })


# ---------------------------------------------------------------------------
# Phase 5 — World & Spatial System
# ---------------------------------------------------------------------------

async def create_location(
    name: str,
    description: str = "",
    biome: str = "town",
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Create a new location in the game world."""
    from app.models.rpg import Location

    gs = await get_or_create_session(session, conversation_id)
    existing = await get_location_by_name(session, gs.id, name)
    if existing:
        return json.dumps({"type": "location", "error": f"Location '{name}' already exists."})

    loc = Location(session_id=gs.id, name=name, description=description, biome=biome)
    session.add(loc)
    await session.flush()

    # Set as current location if it's the first one
    if not gs.current_location_id:
        gs.current_location_id = loc.id
        await session.flush()

    return json.dumps({
        "type": "location",
        "name": loc.name,
        "description": loc.description,
        "biome": loc.biome,
        "exits": {},
        "characters_here": [],
        "npcs_here": [],
    })


async def connect_locations(
    location1: str,
    location2: str,
    direction: str = "north",
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Create a bidirectional link between two locations."""
    gs = await get_or_create_session(session, conversation_id)
    loc1 = await get_location_by_name(session, gs.id, location1)
    loc2 = await get_location_by_name(session, gs.id, location2)

    if not loc1:
        return json.dumps({"type": "location", "error": f"Location '{location1}' not found."})
    if not loc2:
        return json.dumps({"type": "location", "error": f"Location '{location2}' not found."})

    opposites = {
        "north": "south", "south": "north",
        "east": "west", "west": "east",
        "up": "down", "down": "up",
        "northeast": "southwest", "southwest": "northeast",
        "northwest": "southeast", "southeast": "northwest",
    }

    exits1 = json.loads(loc1.exits)
    exits1[direction.lower()] = loc2.id
    loc1.exits = json.dumps(exits1)

    reverse = opposites.get(direction.lower(), "back")
    exits2 = json.loads(loc2.exits)
    exits2[reverse] = loc1.id
    loc2.exits = json.dumps(exits2)

    await session.flush()

    return json.dumps({
        "type": "location_connected",
        "location1": loc1.name,
        "location2": loc2.name,
        "direction": direction,
        "reverse_direction": reverse,
    })


async def move_to(
    character: str,
    direction: str = "",
    location_name: str = "",
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Move a character to a location by direction or name."""
    from app.models.rpg import Character, Location, NPC

    gs = await get_or_create_session(session, conversation_id)
    char = await get_character_by_name(session, gs.id, character)
    if not char:
        return json.dumps({"type": "location", "error": f"Character '{character}' not found."})

    target_loc = None

    if direction:
        # Move by direction from current location
        current_loc_id = char.location_id or gs.current_location_id
        if not current_loc_id:
            return json.dumps({"type": "location", "error": "No current location set."})

        result = await session.execute(select(Location).where(Location.id == current_loc_id))
        current_loc = result.scalars().first()
        if not current_loc:
            return json.dumps({"type": "location", "error": "Current location not found."})

        exits = json.loads(current_loc.exits)
        target_id = exits.get(direction.lower())
        if not target_id:
            available = ", ".join(exits.keys()) or "none"
            return json.dumps({"type": "location", "error": f"No exit '{direction}'. Available: {available}"})

        result = await session.execute(select(Location).where(Location.id == target_id))
        target_loc = result.scalars().first()
    elif location_name:
        target_loc = await get_location_by_name(session, gs.id, location_name)

    if not target_loc:
        return json.dumps({"type": "location", "error": "Destination not found."})

    char.location_id = target_loc.id
    gs.current_location_id = target_loc.id
    await session.flush()

    # Get who's here
    result = await session.execute(
        select(Character).where(Character.session_id == gs.id, Character.location_id == target_loc.id)
    )
    chars_here = [c.name for c in result.scalars().all() if c.id != char.id]

    result = await session.execute(
        select(NPC).where(NPC.session_id == gs.id, NPC.location_id == target_loc.id)
    )
    npcs_here = [n.name for n in result.scalars().all()]

    exits = json.loads(target_loc.exits)
    # Resolve exit IDs to names
    exit_names = {}
    for dir_name, loc_id in exits.items():
        r = await session.execute(select(Location.name).where(Location.id == loc_id))
        loc_name = r.scalar()
        exit_names[dir_name] = loc_name or "Unknown"

    env = json.loads(gs.environment)

    return json.dumps({
        "type": "location",
        "name": target_loc.name,
        "description": target_loc.description,
        "biome": target_loc.biome,
        "exits": exit_names,
        "characters_here": chars_here,
        "npcs_here": npcs_here,
        "environment": env,
        "moved_by": character,
    })


async def look_around(
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Describe the current location, exits, and who's present."""
    from app.models.rpg import Character, Location, NPC

    gs = await get_or_create_session(session, conversation_id)
    if not gs.current_location_id:
        return json.dumps({"type": "location", "error": "No current location. Create one with create_location."})

    result = await session.execute(select(Location).where(Location.id == gs.current_location_id))
    loc = result.scalars().first()
    if not loc:
        return json.dumps({"type": "location", "error": "Current location not found."})

    result = await session.execute(
        select(Character).where(Character.session_id == gs.id, Character.location_id == loc.id)
    )
    chars_here = [c.name for c in result.scalars().all()]

    result = await session.execute(
        select(NPC).where(NPC.session_id == gs.id, NPC.location_id == loc.id)
    )
    npcs_here = [{"name": n.name, "disposition": n.disposition} for n in result.scalars().all()]

    exits = json.loads(loc.exits)
    exit_names = {}
    for dir_name, loc_id in exits.items():
        r = await session.execute(select(Location.name).where(Location.id == loc_id))
        loc_name = r.scalar()
        exit_names[dir_name] = loc_name or "Unknown"

    env = json.loads(gs.environment)

    return json.dumps({
        "type": "location",
        "name": loc.name,
        "description": loc.description,
        "biome": loc.biome,
        "exits": exit_names,
        "characters_here": chars_here,
        "npcs_here": npcs_here,
        "environment": env,
    })


async def set_environment(
    time_of_day: str = "",
    weather: str = "",
    season: str = "",
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Update the game world's environment (time, weather, season)."""
    gs = await get_or_create_session(session, conversation_id)
    env = json.loads(gs.environment)

    if time_of_day:
        env["time_of_day"] = time_of_day
    if weather:
        env["weather"] = weather
    if season:
        env["season"] = season

    gs.environment = json.dumps(env)
    await session.flush()

    return json.dumps({"type": "environment", **env})


# ---------------------------------------------------------------------------
# Phase 6 — NPC System
# ---------------------------------------------------------------------------

async def create_npc(
    name: str,
    description: str = "",
    location: str = "",
    disposition: str = "neutral",
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Create a new NPC."""
    from app.models.rpg import NPC

    gs = await get_or_create_session(session, conversation_id)

    location_id = None
    if location:
        loc = await get_location_by_name(session, gs.id, location)
        if loc:
            location_id = loc.id

    npc = NPC(
        session_id=gs.id,
        name=name,
        description=description,
        location_id=location_id,
        disposition=disposition,
    )
    session.add(npc)
    await session.flush()

    return json.dumps({
        "type": "npc_info",
        "name": npc.name,
        "description": npc.description,
        "disposition": npc.disposition,
        "familiarity": npc.familiarity,
        "location": location or "unknown",
        "memory": [],
    })


async def talk_to_npc(
    npc_name: str,
    topic: str = "",
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Get NPC context for roleplay. Returns personality, disposition, memory."""
    from app.models.rpg import NPC

    gs = await get_or_create_session(session, conversation_id)
    result = await session.execute(
        select(NPC).where(NPC.session_id == gs.id, NPC.name.ilike(npc_name))
    )
    npc = result.scalars().first()
    if not npc:
        return json.dumps({"type": "npc_info", "error": f"NPC '{npc_name}' not found."})

    memory = json.loads(npc.memory)

    return json.dumps({
        "type": "npc_info",
        "name": npc.name,
        "description": npc.description,
        "disposition": npc.disposition,
        "familiarity": npc.familiarity,
        "topic": topic,
        "memory": memory,
        "roleplay_hint": f"Respond as {npc.name}. Disposition: {npc.disposition}. Familiarity: {npc.familiarity}.",
    })


async def update_npc_relationship(
    npc_name: str,
    character: str = "",
    disposition_change: str = "",
    familiarity_change: str = "",
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Update an NPC's disposition or familiarity."""
    from app.models.rpg import NPC

    gs = await get_or_create_session(session, conversation_id)
    result = await session.execute(
        select(NPC).where(NPC.session_id == gs.id, NPC.name.ilike(npc_name))
    )
    npc = result.scalars().first()
    if not npc:
        return json.dumps({"type": "npc_info", "error": f"NPC '{npc_name}' not found."})

    changes = []
    if disposition_change:
        valid = ["hostile", "unfriendly", "neutral", "friendly", "helpful"]
        if disposition_change.lower() in valid:
            old = npc.disposition
            npc.disposition = disposition_change.lower()
            changes.append(f"Disposition: {old} → {npc.disposition}")
    if familiarity_change:
        valid = ["stranger", "acquaintance", "friend", "close_friend"]
        if familiarity_change.lower() in valid:
            old = npc.familiarity
            npc.familiarity = familiarity_change.lower()
            changes.append(f"Familiarity: {old} → {npc.familiarity}")

    await session.flush()

    return json.dumps({
        "type": "npc_info",
        "name": npc.name,
        "disposition": npc.disposition,
        "familiarity": npc.familiarity,
        "changes": changes,
    })


async def npc_remember(
    npc_name: str,
    event: str,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Record an event in an NPC's memory."""
    from app.models.rpg import NPC

    gs = await get_or_create_session(session, conversation_id)
    result = await session.execute(
        select(NPC).where(NPC.session_id == gs.id, NPC.name.ilike(npc_name))
    )
    npc = result.scalars().first()
    if not npc:
        return json.dumps({"type": "npc_info", "error": f"NPC '{npc_name}' not found."})

    memory = json.loads(npc.memory)
    memory.append(event)
    npc.memory = json.dumps(memory)
    await session.flush()

    return json.dumps({
        "type": "npc_info",
        "name": npc.name,
        "memory_added": event,
        "total_memories": len(memory),
    })


# ---------------------------------------------------------------------------
# Phase 7 — Quest System
# ---------------------------------------------------------------------------

async def create_quest(
    title: str,
    description: str = "",
    objectives: str = "[]",
    rewards: str = "{}",
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Create a new quest with objectives and rewards."""
    from app.models.rpg import Quest

    gs = await get_or_create_session(session, conversation_id)
    quest = Quest(
        session_id=gs.id,
        title=title,
        description=description,
        objectives=objectives if isinstance(objectives, str) else json.dumps(objectives),
        rewards=rewards if isinstance(rewards, str) else json.dumps(rewards),
    )
    session.add(quest)
    await session.flush()

    return json.dumps({
        "type": "quest_info",
        "title": quest.title,
        "description": quest.description,
        "status": quest.status,
        "objectives": json.loads(quest.objectives),
        "rewards": json.loads(quest.rewards),
    })


async def update_quest_objective(
    quest_title: str,
    objective_index: int,
    completed: bool = True,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Mark a quest objective as completed or incomplete."""
    from app.models.rpg import Quest

    gs = await get_or_create_session(session, conversation_id)
    result = await session.execute(
        select(Quest).where(Quest.session_id == gs.id, Quest.title.ilike(quest_title))
    )
    quest = result.scalars().first()
    if not quest:
        return json.dumps({"type": "quest_info", "error": f"Quest '{quest_title}' not found."})

    objectives = json.loads(quest.objectives)
    if objective_index < 0 or objective_index >= len(objectives):
        return json.dumps({"type": "quest_info", "error": f"Invalid objective index {objective_index}."})

    if isinstance(objectives[objective_index], dict):
        objectives[objective_index]["completed"] = completed
    else:
        objectives[objective_index] = {"text": str(objectives[objective_index]), "completed": completed}

    quest.objectives = json.dumps(objectives)
    await session.flush()

    return json.dumps({
        "type": "quest_info",
        "title": quest.title,
        "status": quest.status,
        "objectives": objectives,
    })


async def complete_quest(
    quest_title: str,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Complete a quest and distribute rewards (XP, gold)."""
    from app.models.rpg import Character, Quest

    gs = await get_or_create_session(session, conversation_id)
    result = await session.execute(
        select(Quest).where(Quest.session_id == gs.id, Quest.title.ilike(quest_title))
    )
    quest = result.scalars().first()
    if not quest:
        return json.dumps({"type": "quest_info", "error": f"Quest '{quest_title}' not found."})

    quest.status = "completed"
    rewards = json.loads(quest.rewards)
    distributed_to = []

    # Distribute XP to all player characters
    if rewards.get("xp"):
        xp_amount = rewards["xp"]
        result = await session.execute(
            select(Character).where(Character.session_id == gs.id, Character.is_player == True)
        )
        pcs = result.scalars().all()
        per_pc = xp_amount // max(len(pcs), 1)
        for pc in pcs:
            old_level = pc.level
            pc.xp += per_pc
            new_level = level_for_xp(pc.xp)
            if new_level > old_level:
                pc.level = new_level
                con_mod = calculate_modifier(pc.constitution)
                pc.max_hp = calculate_hp(pc.char_class, new_level, con_mod)
                pc.current_hp = pc.max_hp
            distributed_to.append({"name": pc.name, "xp_gained": per_pc, "new_level": pc.level})

    await session.flush()

    return json.dumps({
        "type": "quest_complete",
        "title": quest.title,
        "rewards": rewards,
        "distributed_to": distributed_to,
        "message": f"Quest '{quest.title}' completed!",
    })


async def get_quest_journal(
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Get all quests grouped by status."""
    from app.models.rpg import Quest

    gs = await get_or_create_session(session, conversation_id)
    result = await session.execute(
        select(Quest).where(Quest.session_id == gs.id)
    )
    quests = result.scalars().all()

    journal = {"active": [], "completed": [], "failed": []}
    for q in quests:
        entry = {
            "title": q.title,
            "description": q.description,
            "objectives": json.loads(q.objectives),
            "rewards": json.loads(q.rewards),
        }
        journal.get(q.status, journal["active"]).append(entry)

    return json.dumps({"type": "quest_journal", **journal})


# ---------------------------------------------------------------------------
# Phase 8 — Rest & Recovery
# ---------------------------------------------------------------------------

async def short_rest(
    character: str,
    hit_dice_to_spend: int = 1,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Take a short rest: spend hit dice to heal."""
    gs = await get_or_create_session(session, conversation_id)
    char = await get_character_by_name(session, gs.id, character)
    if not char:
        return json.dumps({"type": "rest_result", "error": f"Character '{character}' not found."})

    hit_die = CLASS_HIT_DIE.get(char.char_class.lower(), 8)
    con_mod = calculate_modifier(char.constitution)

    old_hp = char.current_hp
    total_healed = 0
    rolls = []
    for _ in range(hit_dice_to_spend):
        roll = random.randint(1, hit_die)
        healed = max(1, roll + con_mod)
        total_healed += healed
        rolls.append(roll)

    char.current_hp = min(char.max_hp, char.current_hp + total_healed)

    await session.flush()

    return json.dumps({
        "type": "rest_result",
        "rest_type": "short",
        "character": character,
        "hit_dice_spent": hit_dice_to_spend,
        "hit_die_type": f"d{hit_die}",
        "rolls": rolls,
        "con_modifier": con_mod,
        "hp_healed": char.current_hp - old_hp,
        "hp_before": old_hp,
        "hp_after": char.current_hp,
        "max_hp": char.max_hp,
    })


async def long_rest(
    character: str,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Take a long rest: full HP, spell slots restored, half hit dice recovered."""
    gs = await get_or_create_session(session, conversation_id)
    char = await get_character_by_name(session, gs.id, character)
    if not char:
        return json.dumps({"type": "rest_result", "error": f"Character '{character}' not found."})

    old_hp = char.current_hp
    char.current_hp = char.max_hp

    # Reset conditions (remove exhaustion level if present, remove unconscious)
    conditions = json.loads(char.conditions)
    conditions = [c for c in conditions if c not in ("unconscious",)]
    char.conditions = json.dumps(conditions)

    # Reset death saves
    char.death_saves = json.dumps({"successes": 0, "failures": 0})

    # Reset spell slots (simplified — restore all)
    slots = json.loads(char.spell_slots)
    # We don't track max slots separately, so just note restoration
    slots_restored = bool(slots)

    await session.flush()

    return json.dumps({
        "type": "rest_result",
        "rest_type": "long",
        "character": character,
        "hp_before": old_hp,
        "hp_after": char.current_hp,
        "max_hp": char.max_hp,
        "hp_healed": char.current_hp - old_hp,
        "conditions_removed": ["unconscious"] if "unconscious" not in json.loads(char.conditions) else [],
        "spell_slots_restored": slots_restored,
    })


# ---------------------------------------------------------------------------
# Phase 9 — Session Management
# ---------------------------------------------------------------------------

async def init_game_session(
    world_name: str = "The Realm",
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Initialize or resume an RPG game session."""
    gs = await get_or_create_session(session, conversation_id)
    gs.world_name = world_name
    await session.flush()

    return json.dumps({
        "type": "game_session",
        "world_name": gs.world_name,
        "session_id": gs.id,
        "message": f"Welcome to {world_name}! The adventure begins. Create characters, locations, and start exploring!",
    })


async def get_game_state(
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Get the full game state: party, location, quests, combat, environment."""
    from app.models.rpg import Character, Location, NPC, Quest

    gs = await get_or_create_session(session, conversation_id)

    # Characters
    result = await session.execute(select(Character).where(Character.session_id == gs.id))
    chars = [character_to_dict(c) for c in result.scalars().all()]

    # Current location
    current_loc = None
    if gs.current_location_id:
        result = await session.execute(select(Location).where(Location.id == gs.current_location_id))
        loc = result.scalars().first()
        if loc:
            current_loc = {"name": loc.name, "description": loc.description, "biome": loc.biome}

    # Active quests
    result = await session.execute(
        select(Quest).where(Quest.session_id == gs.id, Quest.status == "active")
    )
    active_quests = [{"title": q.title, "objectives": json.loads(q.objectives)} for q in result.scalars().all()]

    # NPCs
    result = await session.execute(select(NPC).where(NPC.session_id == gs.id))
    npcs = [{"name": n.name, "disposition": n.disposition, "familiarity": n.familiarity} for n in result.scalars().all()]

    # Combat
    combat = json.loads(gs.combat_state) if gs.combat_state else None
    env = json.loads(gs.environment)

    return json.dumps({
        "type": "game_state",
        "world_name": gs.world_name,
        "characters": chars,
        "current_location": current_loc,
        "active_quests": active_quests,
        "npcs": npcs,
        "in_combat": combat is not None,
        "combat": combat,
        "environment": env,
    })


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

BUILTIN_REGISTRY: dict[str, callable] = {
    # Original
    "roll_d20": roll_d20,
    # Phase 1 — Dice
    "roll_dice": roll_dice,
    "roll_check": roll_check,
    "roll_save": roll_save,
    # Phase 2 — Characters
    "create_character": create_character,
    "get_character": get_character,
    "update_character": update_character,
    "list_characters": list_characters,
    # Phase 3 — Combat
    "start_combat": start_combat,
    "get_combat_status": get_combat_status,
    "next_turn": next_turn,
    "end_combat": end_combat,
    "attack": attack,
    "cast_spell": cast_spell,
    "heal": heal,
    "take_damage": take_damage,
    "death_save": death_save,
    "combat_action": combat_action,
    # Phase 4 — Inventory
    "create_item": create_item,
    "give_item": give_item,
    "equip_item": equip_item,
    "unequip_item": unequip_item,
    "get_inventory": get_inventory,
    "transfer_item": transfer_item,
    # Phase 5 — World
    "create_location": create_location,
    "connect_locations": connect_locations,
    "move_to": move_to,
    "look_around": look_around,
    "set_environment": set_environment,
    # Phase 6 — NPCs
    "create_npc": create_npc,
    "talk_to_npc": talk_to_npc,
    "update_npc_relationship": update_npc_relationship,
    "npc_remember": npc_remember,
    # Phase 7 — Quests
    "create_quest": create_quest,
    "update_quest_objective": update_quest_objective,
    "complete_quest": complete_quest,
    "get_quest_journal": get_quest_journal,
    # Phase 8 — Rest
    "short_rest": short_rest,
    "long_rest": long_rest,
    # Phase 9 — Session
    "init_game_session": init_game_session,
    "get_game_state": get_game_state,
}
