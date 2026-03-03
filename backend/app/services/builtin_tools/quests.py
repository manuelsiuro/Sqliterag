"""Quest system tools (Phase 7)."""

from __future__ import annotations

from app.services.builtin_tools._common import (
    AsyncSession,
    calculate_hp,
    calculate_modifier,
    get_or_create_session,
    json,
    level_for_xp,
    select,
)


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
