"""Dice rolling and ability check tools (Phase 0 + Phase 1)."""

from __future__ import annotations

from app.services.builtin_tools._common import (
    ABILITY_NAMES,
    AsyncSession,
    calculate_modifier,
    get_character_by_name,
    get_or_create_session,
    json,
    parse_and_roll,
    random,
    roll_simple,
)


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
