"""World and spatial system tools (Phase 5)."""

from __future__ import annotations

from app.services.builtin_tools._common import (
    AsyncSession,
    get_location_by_name,
    get_or_create_session,
    json,
    select,
)


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
