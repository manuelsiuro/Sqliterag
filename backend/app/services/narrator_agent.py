"""NarratorAgent — storytelling agent with narrative-focused system prompt.

Phase 4.2: First specialized agent in the multi-agent pipeline.
Extends SingleAgent to reuse the full agent loop (tool calling,
history summarization, MemGPT eviction, validation).
"""

from __future__ import annotations

import logging

from app.config import settings
from app.services.agent_base import SingleAgent
from app.services.agent_context import AgentContext
from app.services.prompt_builder import (
    GamePhase,
    _build_layer2_jit_rules,
    _build_layer3_state,
)
from app.services.rpg_service import get_or_create_session

logger = logging.getLogger(__name__)

# Tools that move exclusively to the Archivist when multi-agent is enabled
_ARCHIVIST_EXCLUSIVE_TOOLS: frozenset[str] = frozenset({
    "archive_event", "add_relationship",
    "npc_remember", "update_npc_relationship",
    "update_quest_objective",
})

_NARRATOR_FINAL_TOOLS: frozenset[str] = frozenset({
    # World & Exploration
    "look_around", "move_to", "create_location", "connect_locations", "set_environment",
    # NPCs & Social
    "create_npc", "talk_to_npc", "update_npc_relationship", "npc_remember",
    # Session & State
    "init_game_session", "get_game_state",
    # Quests
    "create_quest", "update_quest_objective", "complete_quest", "get_quest_journal",
    # Memory
    "archive_event", "search_memory",
    # Dice (exploration skill checks)
    "roll_d20", "roll_dice", "roll_check", "roll_save",
    # Characters (full lifecycle outside combat)
    "create_character", "get_character", "update_character", "list_characters",
    # Inventory (exploration: create items, trade)
    "create_item", "give_item", "get_inventory", "transfer_item",
    # Combat entry (Narrator starts combat, Rules Engine takes over next turn)
    "start_combat",
    # Knowledge graph
    "query_relationships", "get_entity_relationships", "get_entity_context",
    "find_connections", "add_relationship",
})


class NarratorAgent(SingleAgent):
    """Storytelling agent — narration, dialogue, scene description.

    Inherits the full agent loop from SingleAgent.  Only overrides
    identity (name), tool scope (allowed_tool_names), and system
    prompt (build_system_prompt / build_system_prompt_async).
    """

    @property
    def name(self) -> str:
        return "narrator"

    @property
    def allowed_tool_names(self) -> frozenset[str] | None:
        if settings.multi_agent_enabled:
            return _NARRATOR_FINAL_TOOLS - _ARCHIVIST_EXCLUSIVE_TOOLS
        return _NARRATOR_FINAL_TOOLS

    def build_system_prompt(self, ctx: AgentContext) -> str | None:
        return None  # Sync path — signals orchestrator to try async

    async def build_system_prompt_async(self, ctx: AgentContext) -> str | None:
        """Async version — queries DB for live game state (Layer 3)."""
        return await _build_narrator_prompt(ctx)


# ---------------------------------------------------------------------------
# Narrator prompt layers
# ---------------------------------------------------------------------------

def _build_narrator_layer1() -> str:
    """Narrator identity layer (~200 tokens)."""
    return (
        "/nothink\n"
        "You are a Dungeon Master running a D&D 5e game. "
        "You have RPG tools that enforce all game rules.\n"
        "ABSOLUTE RULES:\n"
        "- ALWAYS use tools to modify game state. Never narrate mechanical changes without tool calls.\n"
        "- Use init_game_session when starting a new game.\n"
        "- Use create_character before referencing a character in other tools.\n"
        "- Use create_npc to create NPCs. Use talk_to_npc to talk to them.\n"
        "- Use roll_check/roll_save for ability checks and saves — never invent results.\n"
        "- Use the attack tool for combat — never narrate hit/miss without rolling.\n"
        "- Use start_combat when combat begins. Track HP and conditions through tools.\n"
        "- Use archive_event to record significant story moments.\n"
        "- Give characters evocative fantasy names. Give worlds distinctive fantasy names.\n\n"
        "NARRATION STYLE:\n"
        "- Describe scenes with sensory detail: sights, sounds, smells, textures.\n"
        "- Voice NPCs with distinct personalities. Use dialogue, not summaries.\n"
        "- After tool results, narrate them dramatically in 2nd person.\n"
    )


def _build_narrator_layer4() -> str:
    """Narrator-specific format guidance (~50 tokens)."""
    return (
        "RESPONSE FORMAT:\n"
        "- Narrate in 2nd person. Describe tool outcomes with dramatic flair.\n"
        "- Use short paragraphs. Break up exposition with action and dialogue.\n"
        "- After acting, suggest 2-3 possible next actions for the player.\n"
        "- Keep responses under 200 words.\n"
    )


async def _build_narrator_prompt(ctx: AgentContext) -> str:
    """Build the full 4-layer narrator system prompt."""
    layer1 = _build_narrator_layer1()

    # Phase 4.3: Combat narration mode addendum
    if ctx.phase == GamePhase.COMBAT:
        if settings.multi_agent_enabled:
            bookkeeping_hint = "The Archivist handles memory and quest updates."
        else:
            bookkeeping_hint = "You may still call archive_event, quest tools, or NPC tools if appropriate."
        layer1 += (
            "COMBAT NARRATION MODE:\n"
            "- The Rules Engine has already resolved all combat mechanics.\n"
            "- Narrate the mechanical outcomes dramatically using the tool results above.\n"
            "- Do NOT call combat tools (attack, cast_spell, take_damage, etc.).\n"
            f"- {bookkeeping_hint}\n"
        )

    # Reuse existing layers 2-3 from prompt_builder
    try:
        game_session = await get_or_create_session(ctx.session, ctx.conversation_id)
        phase = ctx.phase or GamePhase.EXPLORATION
        layer2 = _build_layer2_jit_rules(phase)
        layer3 = await _build_layer3_state(ctx.session, game_session)
    except Exception:
        logger.warning("Narrator prompt: failed to build layers 2-3, using layer1 only", exc_info=True)
        layer2 = ""
        layer3 = ""

    layer4 = _build_narrator_layer4()

    return f"{layer1}\n{layer2}\n{layer3}\n{layer4}"
