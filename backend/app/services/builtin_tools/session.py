"""Game session management tools (Phase 9)."""

from __future__ import annotations

from app.services.builtin_tools._common import (
    AsyncSession,
    character_to_dict,
    generate_world_name,
    get_or_create_session,
    json,
    select,
)


async def init_game_session(
    world_name: str = "",
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Initialize or resume an RPG game session."""
    gs = await get_or_create_session(session, conversation_id)
    if not world_name.strip():
        world_name = generate_world_name()
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
    from app.models.rpg import Character, InventoryItem, Item, Location, NPC, Quest

    gs = await get_or_create_session(session, conversation_id)

    # Characters with inventory
    result = await session.execute(select(Character).where(Character.session_id == gs.id))
    chars = []
    for c in result.scalars().all():
        cd = character_to_dict(c)
        inv_result = await session.execute(
            select(InventoryItem, Item)
            .join(Item, InventoryItem.item_id == Item.id)
            .where(InventoryItem.character_id == c.id)
        )
        cd["inventory"] = [
            {
                "name": item.name,
                "item_type": item.item_type,
                "quantity": inv.quantity,
                "is_equipped": inv.is_equipped,
                "rarity": item.rarity,
                "weight": float(item.weight),
                "value_gp": float(item.value_gp),
            }
            for inv, item in inv_result.all()
        ]
        chars.append(cd)

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
