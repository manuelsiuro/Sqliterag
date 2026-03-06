"""Combat system tools (Phase 3)."""

from __future__ import annotations

from app.config import settings
from app.services.builtin_tools._common import (
    AsyncSession,
    calculate_encounter_difficulty,
    calculate_modifier,
    calculate_proficiency,
    estimate_cr_from_hp,
    get_character_by_name,
    get_or_create_session,
    json,
    parse_and_roll,
    random,
    roll_simple,
)


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

    # Encounter difficulty injection (Phase 5.4)
    encounter_difficulty = None
    if settings.encounter_balancing_enabled and settings.encounter_auto_difficulty:
        party_levels = []
        enemy_crs = []
        for name in combatant_names:
            char = await get_character_by_name(session, gs.id, name)
            if char and char.is_player:
                party_levels.append(char.level)
            elif char and not char.is_player:
                enemy_crs.append(estimate_cr_from_hp(char.max_hp))
        if party_levels and enemy_crs:
            diff = calculate_encounter_difficulty(party_levels, enemy_crs)
            encounter_difficulty = {
                "difficulty": diff["difficulty"],
                "adjusted_xp": diff["adjusted_xp"],
                "multiplier": diff["multiplier"],
            }
            combat_state["encounter_difficulty"] = encounter_difficulty

    gs.combat_state = json.dumps(combat_state)
    await session.flush()

    result = {
        "type": "initiative_order",
        "round": 1,
        "current_turn": initiative_order[0]["name"],
        "order": initiative_order,
    }
    if encounter_difficulty:
        result["encounter_difficulty"] = encounter_difficulty
    return json.dumps(result)


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
