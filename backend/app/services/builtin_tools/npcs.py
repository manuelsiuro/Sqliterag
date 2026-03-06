"""NPC interaction tools (Phase 6 + Phase 5.3 personality enrichment)."""

from __future__ import annotations

from app.services.builtin_tools._common import (
    AsyncSession,
    get_location_by_name,
    get_or_create_session,
    json,
    resolve_entity_name,
    select,
)


async def create_npc(
    name: str = "",
    npc_name: str = "",
    description: str = "",
    location: str = "",
    disposition: str = "neutral",
    personality: str = "",
    backstory: str = "",
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

    # Parse personality: JSON or comma-separated fallback
    personality_obj = {}
    if personality:
        try:
            personality_obj = json.loads(personality)
        except (json.JSONDecodeError, TypeError):
            personality_obj = {"traits": [t.strip() for t in personality.split(",") if t.strip()]}

    npc = NPC(
        session_id=gs.id,
        name=name,
        description=description,
        location_id=location_id,
        disposition=disposition,
        personality=json.dumps(personality_obj),
        backstory=backstory,
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
        "personality": personality_obj,
        "backstory": backstory or None,
    })


async def talk_to_npc(
    npc_name: str,
    topic: str = "",
    *,
    session: AsyncSession,
    conversation_id: str,
    embedding_service=None,
) -> str:
    """Get NPC context for roleplay. Returns personality, disposition, memory, relationships."""
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
    personality = {}
    try:
        personality = json.loads(npc.personality) if npc.personality else {}
    except (json.JSONDecodeError, TypeError):
        pass

    from app.config import settings
    if not settings.npc_personality_enabled:
        return json.dumps({
            "type": "npc_info", "name": npc.name, "description": npc.description,
            "disposition": npc.disposition, "familiarity": npc.familiarity,
            "topic": topic, "memory": memory,
            "roleplay_hint": f"Respond as {npc.name}. Disposition: {npc.disposition}. Familiarity: {npc.familiarity}.",
        })

    # === Build enriched roleplay_hint ===
    hint_parts = [f"You are {npc.name}."]

    # Section 1: Identity
    if npc.description:
        hint_parts.append(f"Appearance: {npc.description}")
    if npc.backstory:
        hint_parts.append(f"Background: {npc.backstory[:150]}")

    # Section 2: Personality
    traits = personality.get("traits", [])
    if traits:
        hint_parts.append(f"Personality: {', '.join(traits[:5])}")
    if personality.get("voice"):
        hint_parts.append(f"Voice/Speech: {personality['voice']}")
    if personality.get("motivation"):
        hint_parts.append(f"Motivation: {personality['motivation']}")
    secrets = personality.get("secrets", [])
    if secrets:
        hint_parts.append(f"Secrets (reveal only if trust is high): {'; '.join(secrets[:2])}")

    # Section 3: Disposition behavior
    _DISP_BEHAVIOR = {
        "hostile": "Hostile — refuse cooperation, threaten.",
        "unfriendly": "Unfriendly — terse, reluctant, demand favors.",
        "neutral": "Neutral — businesslike, direct, no warmth.",
        "friendly": "Friendly — warm, offer help, share gossip.",
        "helpful": "Helpful — eager to assist, share secrets.",
    }
    _FAM_BEHAVIOR = {
        "stranger": "First meeting — cautious, ask who they are.",
        "acquaintance": "Met before — recall previous encounters.",
        "friend": "Trusted — share freely, offer guidance.",
        "close_friend": "Deep bond — speak openly, offer personal favors.",
    }
    disp_hint = _DISP_BEHAVIOR.get(npc.disposition, "")
    if disp_hint:
        hint_parts.append(disp_hint)
    fam_hint = _FAM_BEHAVIOR.get(npc.familiarity, "")
    if fam_hint:
        hint_parts.append(fam_hint)

    # Section 4: Memories (NPC.memory + GameMemory search)
    max_local = settings.npc_max_local_memories
    relevant_memories = list(memory[-max_local:])

    if embedding_service and topic:
        try:
            from app.services.memory_service import search_with_stanford_scoring, get_memories_by_ids
            results = await search_with_stanford_scoring(
                session, f"{npc.name} {topic}",
                embedding_service=embedding_service,
                session_id=gs.id,
                top_k=settings.npc_memory_search_top_k,
            )
            if results:
                mems = await get_memories_by_ids(session, [mid for mid, _ in results])
                for m in mems:
                    relevant_memories.append(m.content[:100])
        except Exception:
            pass  # Memory search is supplementary

    if relevant_memories:
        cap = max_local + settings.npc_memory_search_top_k
        hint_parts.append(f"You remember: {'; '.join(relevant_memories[:cap])}")

    # Section 5: Relationships from graph
    relationship_hints = []
    try:
        from app.models.rpg import Relationship
        from sqlalchemy import or_
        rel_result = await session.execute(
            select(Relationship).where(
                Relationship.session_id == gs.id,
                or_(
                    (Relationship.source_type == "npc") & (Relationship.source_id == npc.id),
                    (Relationship.target_type == "npc") & (Relationship.target_id == npc.id),
                ),
            ).order_by(Relationship.strength.desc()).limit(settings.npc_max_relationship_hints)
        )
        rels = rel_result.scalars().all()
        for r in rels:
            if r.source_id == npc.id:
                other = await resolve_entity_name(session, r.target_type, r.target_id)
                relationship_hints.append(f"{r.relationship.replace('_', ' ')} {other}")
            else:
                other = await resolve_entity_name(session, r.source_type, r.source_id)
                relationship_hints.append(f"{other} {r.relationship.replace('_', ' ')} you")
    except Exception:
        pass  # Relationship context is supplementary

    if relationship_hints:
        hint_parts.append(f"Relationships: {', '.join(relationship_hints)}")

    if topic:
        hint_parts.append(f"The adventurer asks about: {topic}")

    roleplay_hint = "\n".join(p for p in hint_parts if p)

    return json.dumps({
        "type": "npc_info",
        "name": npc.name, "description": npc.description,
        "disposition": npc.disposition, "familiarity": npc.familiarity,
        "topic": topic, "memory": memory,
        "personality": personality,
        "backstory": npc.backstory or None,
        "relationships": relationship_hints,
        "roleplay_hint": roleplay_hint,
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
