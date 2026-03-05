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

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rpg import Character, GameSession, Location, NPC, Quest
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
    "archive_event", "search_memory", "get_session_summary",
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
    "archive_event", "search_memory", "get_session_summary",
})

_PHASE_TOOLS: dict[GamePhase, frozenset[str]] = {
    GamePhase.COMBAT: frozenset({
        "start_combat", "get_combat_status", "next_turn", "end_combat",
        "attack", "cast_spell", "heal", "take_damage", "death_save", "combat_action",
        "short_rest", "long_rest",
        "get_inventory", "equip_item", "unequip_item",
    }),
    GamePhase.EXPLORATION: frozenset({
        "create_location", "connect_locations", "move_to", "look_around", "set_environment",
        "create_npc", "talk_to_npc", "update_npc_relationship", "npc_remember",
        "create_item", "give_item", "equip_item", "unequip_item", "get_inventory", "transfer_item",
        "short_rest", "long_rest",
        "start_combat",
    }),
    GamePhase.SOCIAL: frozenset({
        "create_npc", "talk_to_npc", "update_npc_relationship", "npc_remember",
        "look_around", "move_to",
        "get_inventory", "give_item", "transfer_item",
        "start_combat",
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
)

_SOCIAL_RULES = (
    "SOCIAL PHASE:\n"
    "- Use talk_to_npc for NPC dialogue. Respect NPC disposition and familiarity.\n"
    "- Use update_npc_relationship to track changes in NPC attitudes.\n"
    "- Role-play NPC personalities consistently.\n"
)

_EXPLORATION_RULES = (
    "EXPLORATION PHASE:\n"
    "- Use look_around to describe the current location.\n"
    "- Use move_to for travel between locations.\n"
    "- Use roll_check for skill-based actions (perception, investigation, athletics, etc.).\n"
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


async def _build_layer3_state(
    session: AsyncSession,
    game_session: GameSession,
) -> str:
    """Query DB and build compact state summary."""
    parts: list[str] = ["CURRENT STATE:"]

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
            exits = json.loads(loc.exits) if loc.exits else {}
            if exits:
                # exits is {direction: location_id} — resolve names
                loc_ids = list(exits.values())
                if loc_ids:
                    result = await session.execute(
                        select(Location).where(Location.id.in_(loc_ids))
                    )
                    id_to_name = {l.id: l.name for l in result.scalars().all()}
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
            npcs_text = ", ".join(f"{n.name} ({n.disposition})" for n in npcs)
    parts.append(f"NPCs here: {npcs_text}")

    # Environment + Combat
    env = json.loads(game_session.environment) if game_session.environment else {}
    env_str = ", ".join(
        str(env.get(k, "?"))
        for k in ("time_of_day", "weather", "season")
        if env.get(k)
    )
    combat_str = "active" if game_session.combat_state else "none"
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

    state_text = "\n".join(parts)

    # Truncation: drop quests, then NPCs, then older party members
    if len(state_text) > _MAX_STATE_CHARS:
        # Drop quests line
        parts = [p for p in parts if not p.startswith("Active quests:")]
        state_text = "\n".join(parts)

    if len(state_text) > _MAX_STATE_CHARS:
        # Drop NPCs line
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
