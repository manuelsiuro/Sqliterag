"""Encounter balancing tools (Phase 5.4)."""

from __future__ import annotations

from app.config import settings
from app.models.rpg import Character
from app.services.builtin_tools._common import (
    AsyncSession,
    CR_TO_XP,
    calculate_encounter_difficulty,
    calculate_hp,
    calculate_modifier,
    character_to_dict,
    estimate_cr_from_hp,
    generate_monster_stats,
    get_character_by_name,
    get_or_create_session,
    json,
    level_for_xp,
    normalize_cr,
    select,
)


async def balance_encounter(
    enemy_crs: str,
    desired_difficulty: str = "",
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Assess encounter difficulty using D&D 5e DMG XP budget rules."""
    if not settings.encounter_balancing_enabled:
        return json.dumps({"type": "encounter_balance", "error": "Encounter balancing is disabled."})

    gs = await get_or_create_session(session, conversation_id)

    # Get player characters
    result = await session.execute(
        select(Character).where(
            Character.session_id == gs.id,
            Character.is_player == True,  # noqa: E712
        )
    )
    players = result.scalars().all()
    if not players:
        return json.dumps({"type": "encounter_balance", "error": "No player characters found. Create characters first."})

    # Parse enemy CRs
    raw_crs = [s.strip() for s in enemy_crs.split(",") if s.strip()]
    if not raw_crs:
        return json.dumps({"type": "encounter_balance", "error": "No enemy CRs provided. Use comma-separated values like '2, 1/4, 1/4'."})

    parsed_crs = [normalize_cr(cr) for cr in raw_crs]
    party_levels = [c.level for c in players]
    diff = calculate_encounter_difficulty(party_levels, parsed_crs)

    # Per-enemy breakdown
    enemies = []
    for cr in parsed_crs:
        enemies.append({"cr": cr, "xp": CR_TO_XP.get(cr, 200)})

    # Recommendation
    recommendation = ""
    if desired_difficulty:
        desired = desired_difficulty.lower()
        if desired in diff["thresholds"]:
            target_xp = diff["thresholds"][desired]
            if diff["adjusted_xp"] > target_xp * 1.2:
                recommendation = f"This encounter is tougher than {desired}. Consider removing enemies or lowering CRs."
            elif diff["adjusted_xp"] < target_xp * 0.8:
                recommendation = f"This encounter is easier than {desired}. Consider adding enemies or raising CRs."
            else:
                recommendation = f"This encounter is well-balanced for {desired} difficulty."

    return json.dumps({
        "type": "encounter_balance",
        "difficulty": diff["difficulty"],
        "adjusted_xp": diff["adjusted_xp"],
        "raw_xp": diff["raw_xp"],
        "multiplier": diff["multiplier"],
        "thresholds": diff["thresholds"],
        "enemies": enemies,
        "party_levels": party_levels,
        "recommendation": recommendation,
    })


async def generate_monster(
    name: str,
    cr: str = "1",
    creature_type: str = "humanoid",
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Generate a monster with CR-appropriate stats and add it as a non-player character."""
    if not settings.encounter_balancing_enabled:
        return json.dumps({"type": "monster_generated", "error": "Encounter balancing is disabled."})

    gs = await get_or_create_session(session, conversation_id)

    stats = generate_monster_stats(cr, creature_type)

    # Check for duplicate name
    existing = await get_character_by_name(session, gs.id, name)
    if existing:
        name = f"{name} (CR {stats['cr']})"
        existing = await get_character_by_name(session, gs.id, name)
        if existing:
            return json.dumps({"type": "monster_generated", "error": f"Character '{name}' already exists."})

    abilities = stats["abilities"]
    char = Character(
        session_id=gs.id,
        name=name,
        race=stats["creature_type"],
        char_class=stats["char_class"],
        level=stats["level"],
        xp=0,
        max_hp=stats["max_hp"],
        current_hp=stats["max_hp"],
        temp_hp=0,
        armor_class=stats["armor_class"],
        speed=30,
        strength=abilities["strength"],
        dexterity=abilities["dexterity"],
        constitution=abilities["constitution"],
        intelligence=abilities["intelligence"],
        wisdom=abilities["wisdom"],
        charisma=abilities["charisma"],
        conditions="[]",
        spell_slots="{}",
        death_saves='{"successes": 0, "failures": 0}',
        is_player=False,
        is_alive=True,
    )
    session.add(char)
    await session.flush()

    result = character_to_dict(char)
    result["type"] = "monster_generated"
    result["cr"] = stats["cr"]
    result["xp_value"] = stats["xp"]
    result["creature_type"] = stats["creature_type"]
    result["attack_bonus"] = stats["attack_bonus"]
    result["damage_per_round"] = stats["damage_per_round"]
    result["save_dc"] = stats["save_dc"]
    return json.dumps(result)


async def award_xp(
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Distribute XP from defeated enemies to player characters."""
    if not settings.encounter_balancing_enabled:
        return json.dumps({"type": "xp_reward", "error": "Encounter balancing is disabled."})

    gs = await get_or_create_session(session, conversation_id)

    # Find defeated enemies (non-player, dead or 0 HP)
    result = await session.execute(
        select(Character).where(
            Character.session_id == gs.id,
            Character.is_player == False,  # noqa: E712
        )
    )
    enemies = result.scalars().all()
    defeated = [e for e in enemies if not e.is_alive or e.current_hp <= 0]

    if not defeated:
        return json.dumps({"type": "xp_reward", "error": "No defeated enemies found."})

    # Find player characters
    result = await session.execute(
        select(Character).where(
            Character.session_id == gs.id,
            Character.is_player == True,  # noqa: E712
        )
    )
    players = result.scalars().all()
    if not players:
        return json.dumps({"type": "xp_reward", "error": "No player characters found."})

    # Calculate total XP
    enemy_details = []
    total_xp = 0
    for e in defeated:
        cr = estimate_cr_from_hp(e.max_hp)
        xp = CR_TO_XP.get(cr, 200)
        total_xp += xp
        enemy_details.append({"name": e.name, "cr": cr, "xp": xp})

    xp_per_char = total_xp // len(players)

    # Apply XP and check level-ups
    char_results = []
    for p in players:
        old_level = p.level
        old_xp = p.xp
        p.xp += xp_per_char
        new_level = level_for_xp(p.xp)
        leveled_up = new_level > old_level
        if leveled_up:
            p.level = new_level
            con_mod = calculate_modifier(p.constitution)
            p.max_hp = calculate_hp(p.char_class, new_level, con_mod)
            p.current_hp = min(p.current_hp + (p.max_hp - calculate_hp(p.char_class, old_level, con_mod)), p.max_hp)

        char_results.append({
            "name": p.name,
            "xp_gained": xp_per_char,
            "total_xp": p.xp,
            "level": p.level,
            "leveled_up": leveled_up,
            "old_level": old_level if leveled_up else None,
        })

    await session.flush()

    return json.dumps({
        "type": "xp_reward",
        "total_xp": total_xp,
        "xp_per_character": xp_per_char,
        "characters": char_results,
        "defeated_enemies": enemy_details,
    })
