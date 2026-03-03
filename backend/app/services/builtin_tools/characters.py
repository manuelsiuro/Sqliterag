"""Character management tools (Phase 2)."""

from __future__ import annotations

from app.services.builtin_tools._common import (
    AsyncSession,
    XP_THRESHOLDS,
    calculate_hp,
    calculate_modifier,
    character_to_dict,
    generate_character_name,
    get_character_by_name,
    get_or_create_session,
    is_generic_name,
    json,
    level_for_xp,
    select,
)


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

    if is_generic_name(name):
        name = generate_character_name()

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
