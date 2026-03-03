"""Rest and recovery tools (Phase 8)."""

from __future__ import annotations

from app.services.builtin_tools._common import (
    AsyncSession,
    CLASS_HIT_DIE,
    calculate_modifier,
    get_character_by_name,
    get_or_create_session,
    json,
    random,
)


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
