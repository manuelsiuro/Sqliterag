"""Dynamic RPG system prompt builder — 4-layer architecture.

Replaces the static RPG_SYSTEM_PROMPT with a context-aware prompt that
injects game state, phase-specific rules, and formatting guidance so the
LLM can act without unnecessary get_game_state tool calls.
"""

from __future__ import annotations

import enum
import json
import logging
from typing import NamedTuple

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rpg import Character, GameSession, Location, NPC, Quest, Relationship
from app.services.rpg_service import get_or_create_session

logger = logging.getLogger(__name__)

# All builtin RPG tool names — used both for RPG detection and phase filtering
RPG_TOOL_NAMES = {
    # Dice & Rolls
    "roll_d20", "roll_dice", "roll_check", "roll_save",
    # Characters
    "create_character", "get_character", "update_character", "list_characters",
    # Combat
    "start_combat", "get_combat_status", "next_turn", "end_combat",
    "attack", "cast_spell", "heal", "take_damage", "death_save", "combat_action",
    # Inventory & Items
    "create_item", "give_item", "equip_item", "unequip_item", "get_inventory", "transfer_item",
    # World & Exploration
    "create_location", "connect_locations", "move_to", "look_around", "set_environment",
    # NPCs
    "create_npc", "talk_to_npc", "update_npc_relationship", "npc_remember",
    # Quests
    "create_quest", "update_quest_objective", "complete_quest", "get_quest_journal",
    # Rest & Recovery
    "short_rest", "long_rest",
    # Game Session
    "init_game_session", "get_game_state",
    # Memory
    "archive_event", "search_memory", "recall_context", "get_session_summary", "end_session",
    # Knowledge Graph
    "add_relationship", "query_relationships", "get_entity_relationships", "get_entity_context",
    "find_connections",
    # Campaign
    "start_campaign", "list_campaigns",
    # Encounter Balancing
    "balance_encounter", "generate_monster", "award_xp",
}

# Static fallback — identical to the old RPG_SYSTEM_PROMPT
_STATIC_FALLBACK = (
    "/nothink\n"
    "You are a Dungeon Master running a D&D 5e game. You have access to RPG tools that enforce game rules. "
    "IMPORTANT RULES:\n"
    "- Always use the tools to modify game state. Never just narrate mechanical changes.\n"
    "- Use create_character before referencing a character in other tools.\n"
    "- Use roll_check / roll_save for ability checks and saves — don't invent results.\n"
    "- Use the attack tool for combat attacks — don't narrate hit/miss without rolling.\n"
    "- Track HP, conditions, and spell slots through the tools.\n"
    "- Narrate results dramatically after receiving tool output.\n"
    "- When starting a new game, use init_game_session first.\n"
    "- When creating characters, give them evocative fantasy names. Never use generic names like 'Adventurer'.\n"
    "- When starting a game, give the world a distinctive fantasy name.\n"
)


# ---------------------------------------------------------------------------
# Game Phase
# ---------------------------------------------------------------------------

class GamePhase(enum.Enum):
    COMBAT = "combat"
    SOCIAL = "social"
    EXPLORATION = "exploration"


def detect_phase(
    combat_state: str | None,
    recent_tool_names: set[str],
) -> GamePhase:
    """Determine the current game phase from combat state and recent tools."""
    if combat_state is not None:
        return GamePhase.COMBAT
    if {"talk_to_npc", "update_npc_relationship"} & recent_tool_names:
        return GamePhase.SOCIAL
    return GamePhase.EXPLORATION


class PromptResult(NamedTuple):
    """Return type for build_rpg_system_prompt — prompt text + detected phase."""
    prompt: str
    phase: GamePhase


def extract_recent_tool_names(
    messages: list[dict],
    lookback: int = 5,
) -> set[str]:
    """Collect tool names from the last *lookback* tool-role messages."""
    names: set[str] = set()
    count = 0
    for msg in reversed(messages):
        if msg.get("role") == "tool" and msg.get("tool_name"):
            names.add(msg["tool_name"])
            count += 1
            if count >= lookback:
                break
    return names


# ---------------------------------------------------------------------------
# Phase → Tool Filtering (Phase 1.4)
# ---------------------------------------------------------------------------

_CORE_TOOLS: frozenset[str] = frozenset({
    # Dice
    "roll_d20", "roll_dice", "roll_check", "roll_save",
    # Characters
    "create_character", "get_character", "update_character", "list_characters",
    # Session
    "init_game_session", "get_game_state",
    # Quests
    "create_quest", "update_quest_objective", "complete_quest", "get_quest_journal",
    # Memory
    "archive_event", "search_memory", "recall_context", "get_session_summary", "end_session",
    # Knowledge Graph (read)
    "query_relationships", "get_entity_relationships", "get_entity_context", "find_connections",
    # Campaign
    "start_campaign", "list_campaigns",
})

_PHASE_TOOLS: dict[GamePhase, frozenset[str]] = {
    GamePhase.COMBAT: frozenset({
        "start_combat", "get_combat_status", "next_turn", "end_combat",
        "attack", "cast_spell", "heal", "take_damage", "death_save", "combat_action",
        "short_rest", "long_rest",
        "get_inventory", "equip_item", "unequip_item",
        "balance_encounter", "award_xp",
    }),
    GamePhase.EXPLORATION: frozenset({
        "create_location", "connect_locations", "move_to", "look_around", "set_environment",
        "create_npc", "talk_to_npc", "update_npc_relationship", "npc_remember",
        "create_item", "give_item", "equip_item", "unequip_item", "get_inventory", "transfer_item",
        "short_rest", "long_rest",
        "start_combat",
        "add_relationship",
        "balance_encounter", "generate_monster",
    }),
    GamePhase.SOCIAL: frozenset({
        "create_npc", "talk_to_npc", "update_npc_relationship", "npc_remember",
        "look_around", "move_to",
        "get_inventory", "give_item", "transfer_item",
        "start_combat",
        "add_relationship",
    }),
}


def get_phase_tool_names(phase: GamePhase) -> frozenset[str]:
    """Return all tool names allowed for a given game phase."""
    return _CORE_TOOLS | _PHASE_TOOLS[phase]


def filter_tools_by_phase(tools: list, phase: GamePhase) -> list:
    """Filter a tool list by game phase.

    Non-RPG tools (custom/HTTP) are always kept — only tools whose names
    appear in RPG_TOOL_NAMES are subject to phase filtering.
    """
    allowed = get_phase_tool_names(phase)
    return [
        t for t in tools
        if t.name not in RPG_TOOL_NAMES or t.name in allowed
    ]


# ---------------------------------------------------------------------------
# Layer 1 — Identity (~150 tokens)
# ---------------------------------------------------------------------------

def _build_layer1_identity() -> str:
    return (
        "/nothink\n"
        "You are a Dungeon Master running a D&D 5e game. "
        "You have RPG tools that enforce all game rules.\n"
        "ABSOLUTE RULES:\n"
        "- ALWAYS use tools to modify game state. Never narrate mechanical changes without tool calls.\n"
        "- Use create_character before referencing a character in other tools.\n"
        "- Use roll_check/roll_save for ability checks and saves — never invent results.\n"
        "- Use the attack tool for combat — never narrate hit/miss without rolling.\n"
        "- Track HP, conditions, and spell slots exclusively through tools.\n"
        "- When starting a new game, use init_game_session first.\n"
        "- Give characters evocative fantasy names. Never use generic names like 'Adventurer'.\n"
        "- Give worlds distinctive fantasy names.\n"
        "- Use archive_event to record significant story moments for long-term memory.\n"
    )


# ---------------------------------------------------------------------------
# Layer 2 — Phase-specific JIT rules (0-100 tokens)
# ---------------------------------------------------------------------------

_COMBAT_RULES = (
    "COMBAT PHASE:\n"
    "- Follow initiative order. Use attack/cast_spell for each combatant's turn.\n"
    "- Apply damage via take_damage. Track death saves with death_save.\n"
    "- Call end_combat when combat concludes.\n"
    "- After combat ends, use award_xp to distribute XP rewards.\n"
)

_SOCIAL_RULES = (
    "SOCIAL PHASE:\n"
    "- Use talk_to_npc for dialogue — it returns a detailed roleplay_hint with personality, memories, and relationships.\n"
    "- Follow the roleplay_hint closely: match the NPC's voice, traits, and disposition in dialogue.\n"
    "- Reference NPC memories when relevant to the conversation topic.\n"
    "- Use update_npc_relationship when disposition changes.\n"
)

_EXPLORATION_RULES = (
    "EXPLORATION PHASE:\n"
    "- Use look_around to describe the current location.\n"
    "- Use move_to for travel between locations.\n"
    "- Use roll_check for skill-based actions (perception, investigation, athletics, etc.).\n"
    "- Use generate_monster to create enemies and balance_encounter to check difficulty before combat.\n"
)

_PHASE_RULES = {
    GamePhase.COMBAT: _COMBAT_RULES,
    GamePhase.SOCIAL: _SOCIAL_RULES,
    GamePhase.EXPLORATION: _EXPLORATION_RULES,
}


def _build_layer2_jit_rules(phase: GamePhase) -> str:
    return _PHASE_RULES[phase]


# ---------------------------------------------------------------------------
# Layer 3 — Live game state (~200 tokens)
# ---------------------------------------------------------------------------

_MAX_STATE_CHARS = 800


async def _compile_graph_context(
    session: AsyncSession,
    session_id: str,
    entity_names: dict[tuple[str, str], str],
) -> str:
    """Compile a compact relationship summary for scene entities.

    Single batch query. Returns empty string if disabled or no results.
    """
    from app.config import settings
    if not settings.graph_context_enabled or not entity_names:
        return ""

    entity_list = list(entity_names.keys())
    source_conds = [
        (Relationship.source_type == etype) & (Relationship.source_id == eid)
        for etype, eid in entity_list
    ]
    target_conds = [
        (Relationship.target_type == etype) & (Relationship.target_id == eid)
        for etype, eid in entity_list
    ]

    q = (
        select(Relationship)
        .where(
            Relationship.session_id == session_id,
            Relationship.strength >= settings.graph_context_strength_threshold,
            or_(*source_conds),
            or_(*target_conds),
        )
        .order_by(Relationship.strength.desc())
        .limit(settings.graph_context_max_relations)
    )
    result = await session.execute(q)
    rels = result.scalars().all()
    if not rels:
        return ""

    parts: list[str] = []
    for r in rels:
        src = entity_names.get((r.source_type, r.source_id))
        tgt = entity_names.get((r.target_type, r.target_id))
        if not src or not tgt:
            continue
        parts.append(f"{src} {r.relationship}({r.strength}) {tgt}")

    return "Relations: " + " | ".join(parts) if parts else ""


async def _build_layer3_state(
    session: AsyncSession,
    game_session: GameSession,
) -> str:
    """Query DB and build compact state summary."""
    parts: list[str] = []

    # Campaign recap ("Previously on...")
    if game_session.campaign_id and game_session.session_number > 1:
        try:
            from app.services import campaign_service
            from app.models.rpg import Campaign
            camp_result = await session.execute(
                select(Campaign).where(Campaign.id == game_session.campaign_id)
            )
            camp = camp_result.scalars().first()
            if camp:
                parts.append(f"CAMPAIGN: {camp.name} | Session #{game_session.session_number}")
                summaries = await campaign_service.get_previous_summaries(
                    session, game_session.campaign_id, limit=3,
                )
                if summaries:
                    lines = []
                    for s in summaries:
                        text = s["summary"]
                        if len(text) > 120:
                            text = text[:117] + "..."
                        lines.append(f"- Session {s['session_number']}: {text}")
                    parts.append("PREVIOUSLY:\n" + "\n".join(lines))
        except Exception:
            pass  # Campaign context is supplementary — never breaks prompt

    parts.append("CURRENT STATE:")
    entity_names: dict[tuple[str, str], str] = {}

    # World + Location
    loc_str = "unknown"
    exits_str = ""
    if game_session.current_location_id:
        result = await session.execute(
            select(Location).where(Location.id == game_session.current_location_id)
        )
        loc = result.scalars().first()
        if loc:
            loc_str = f"{loc.name} ({loc.biome})"
            entity_names[("location", loc.id)] = loc.name
            exits = json.loads(loc.exits) if loc.exits else {}
            if exits:
                # exits is {direction: location_id} — resolve names
                loc_ids = list(exits.values())
                if loc_ids:
                    result = await session.execute(
                        select(Location).where(Location.id.in_(loc_ids))
                    )
                    id_to_name = {l.id: l.name for l in result.scalars().all()}
                    for lid, lname in id_to_name.items():
                        entity_names[("location", lid)] = lname
                    exit_parts = []
                    for direction, lid in exits.items():
                        name = id_to_name.get(lid, "?")
                        exit_parts.append(f"{direction}->{name}")
                    exits_str = " | Exits: " + ", ".join(exit_parts)

    parts.append(
        f"World: {game_session.world_name} | Location: {loc_str}{exits_str}"
    )

    # Party (limit 6)
    result = await session.execute(
        select(Character)
        .where(Character.session_id == game_session.id)
        .order_by(Character.created_at)
        .limit(6)
    )
    chars = result.scalars().all()
    if chars:
        char_strs = []
        for c in chars:
            entity_names[("character", c.id)] = c.name
            conditions = json.loads(c.conditions) if c.conditions else []
            cond_str = f" [{','.join(conditions)}]" if conditions else ""
            char_strs.append(
                f"{c.name} L{c.level} {c.char_class} HP:{c.current_hp}/{c.max_hp} AC:{c.armor_class}{cond_str}"
            )
        parts.append("Party: " + ", ".join(char_strs))
    else:
        parts.append("Party: (none)")

    # NPCs at current location (limit 4)
    npcs_text = "(none)"
    if game_session.current_location_id:
        result = await session.execute(
            select(NPC)
            .where(
                NPC.session_id == game_session.id,
                NPC.location_id == game_session.current_location_id,
            )
            .limit(4)
        )
        npcs = result.scalars().all()
        if npcs:
            npc_parts = []
            for n in npcs:
                entity_names[("npc", n.id)] = n.name
                traits_str = ""
                try:
                    p = json.loads(n.personality) if n.personality else {}
                    traits = p.get("traits", [])[:2]
                    if traits:
                        traits_str = f", {'/'.join(traits)}"
                except (json.JSONDecodeError, TypeError, AttributeError):
                    pass
                npc_parts.append(f"{n.name} ({n.disposition}{traits_str})")
            npcs_text = ", ".join(npc_parts)
    parts.append(f"NPCs here: {npcs_text}")

    # Environment + Combat
    env = json.loads(game_session.environment) if game_session.environment else {}
    env_str = ", ".join(
        str(env.get(k, "?"))
        for k in ("time_of_day", "weather", "season")
        if env.get(k)
    )
    combat_str = "none"
    if game_session.combat_state:
        combat_str = "active"
        try:
            cs = json.loads(game_session.combat_state)
            ed = cs.get("encounter_difficulty")
            if ed:
                combat_str = f"active ({ed['difficulty']})"
        except (json.JSONDecodeError, KeyError):
            pass
    parts.append(f"Environment: {env_str} | Combat: {combat_str}")

    # Active quests (limit 3)
    result = await session.execute(
        select(Quest)
        .where(Quest.session_id == game_session.id, Quest.status == "active")
        .limit(3)
    )
    quests = result.scalars().all()
    quests_text = ", ".join(q.title for q in quests) if quests else "(none)"
    parts.append(f"Active quests: {quests_text}")

    # Graph relationships (Phase 3.4)
    try:
        relations_line = await _compile_graph_context(
            session, game_session.id, entity_names,
        )
        if relations_line:
            parts.append(relations_line)
    except Exception:
        pass  # Graph context is supplementary — never breaks prompt

    state_text = "\n".join(parts)

    # Truncation cascade: relations → quests → NPCs → hard cut
    if len(state_text) > _MAX_STATE_CHARS:
        parts = [p for p in parts if not p.startswith("Relations:")]
        state_text = "\n".join(parts)

    if len(state_text) > _MAX_STATE_CHARS:
        parts = [p for p in parts if not p.startswith("Active quests:")]
        state_text = "\n".join(parts)

    if len(state_text) > _MAX_STATE_CHARS:
        parts = [p for p in parts if not p.startswith("NPCs here:")]
        state_text = "\n".join(parts)

    if len(state_text) > _MAX_STATE_CHARS:
        state_text = state_text[:_MAX_STATE_CHARS]

    return state_text


# ---------------------------------------------------------------------------
# Layer 4 — Format guidance (~50 tokens)
# ---------------------------------------------------------------------------

def _build_layer4_format() -> str:
    return (
        "RESPONSE FORMAT:\n"
        "- Narrate in 2nd person. Describe tool outcomes vividly.\n"
        "- After acting, suggest 2-3 possible next actions for the player.\n"
        "- Keep responses under 200 words.\n"
    )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

async def build_rpg_system_prompt(
    session: AsyncSession,
    conversation_id: str,
    recent_tool_names: set[str],
) -> PromptResult:
    """Build a dynamic 4-layer RPG system prompt.

    Returns a PromptResult with the prompt text and detected game phase.
    On any exception, falls back to the static prompt with EXPLORATION phase.
    """
    try:
        game_session = await get_or_create_session(session, conversation_id)

        phase = detect_phase(game_session.combat_state, recent_tool_names)

        layer1 = _build_layer1_identity()
        layer2 = _build_layer2_jit_rules(phase)
        layer3 = await _build_layer3_state(session, game_session)
        layer4 = _build_layer4_format()

        return PromptResult(f"{layer1}\n{layer2}\n{layer3}\n{layer4}", phase)
    except Exception:
        logger.warning("Dynamic prompt build failed, using static fallback", exc_info=True)
        return PromptResult(_STATIC_FALLBACK, GamePhase.EXPLORATION)
