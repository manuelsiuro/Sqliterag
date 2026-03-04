"""NPC interaction tools (Phase 6)."""

from __future__ import annotations

from app.services.builtin_tools._common import (
    AsyncSession,
    get_location_by_name,
    get_or_create_session,
    json,
    select,
)


async def create_npc(
    name: str = "",
    npc_name: str = "",
    description: str = "",
    location: str = "",
    disposition: str = "neutral",
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Create a new NPC."""
    from app.models.rpg import NPC

    # Accept either 'name' or 'npc_name' for consistency with other NPC tools
    name = name or npc_name
    if not name:
        return json.dumps({"type": "npc_info", "error": "NPC name is required."})

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
    from app.models.rpg import Character, NPC

    gs = await get_or_create_session(session, conversation_id)
    result = await session.execute(
        select(NPC).where(NPC.session_id == gs.id, NPC.name.ilike(npc_name))
    )
    npc = result.scalars().first()
    if not npc:
        # Fallback: check if name matches a Character (party member)
        char_result = await session.execute(
            select(Character).where(
                Character.session_id == gs.id, Character.name.ilike(npc_name)
            )
        )
        char = char_result.scalars().first()
        if char:
            return json.dumps({
                "type": "npc_info",
                "name": char.name,
                "description": f"Level {char.level} {char.race} {char.char_class}",
                "disposition": "friendly",
                "familiarity": "friend",
                "topic": topic,
                "memory": [],
                "is_party_member": True,
                "roleplay_hint": f"Respond as {char.name}, a level {char.level} {char.race} {char.char_class} party member.",
            })
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
