"""ArchivistAgent — silent bookkeeping agent for memory and knowledge graph.

Phase 4.4: Maintains long-term memory, updates the knowledge graph, and
tracks NPC/quest state. Runs last in the pipeline, never streams to the user.
"""

from __future__ import annotations

import logging

from app.services.agent_base import SingleAgent
from app.services.agent_context import AgentContext
from app.services.prompt_builder import (
    GamePhase,
    _build_layer2_jit_rules,
    _build_layer3_state,
)
from app.services.rpg_service import get_or_create_session

logger = logging.getLogger(__name__)

_ARCHIVIST_TOOLS: frozenset[str] = frozenset({
    # Memory (write)
    "archive_event",
    # Memory (read)
    "search_memory", "recall_context", "get_session_summary", "end_session",
    # Graph (write)
    "add_relationship",
    # Graph (read)
    "query_relationships", "get_entity_relationships", "get_entity_context",
    # NPC state
    "npc_remember", "update_npc_relationship",
    # Quest tracking
    "update_quest_objective",
    # Read-only state
    "get_game_state", "get_character", "list_characters", "get_inventory",
    "get_quest_journal", "look_around",
})


class ArchivistAgent(SingleAgent):
    """Silent bookkeeping agent — archives events, maintains graph, tracks state.

    Inherits the full agent loop from SingleAgent.  Overrides identity,
    tool scope, user-facing flag, and system prompt.
    """

    @property
    def name(self) -> str:
        return "archivist"

    @property
    def is_user_facing(self) -> bool:
        return False

    @property
    def allowed_tool_names(self) -> frozenset[str] | None:
        return _ARCHIVIST_TOOLS

    @property
    def correction_mode(self) -> str:
        return "minimal"

    def build_system_prompt(self, ctx: AgentContext) -> str | None:
        return None  # Sync path — signals orchestrator to try async

    async def build_system_prompt_async(self, ctx: AgentContext) -> str | None:
        return await _build_archivist_prompt(ctx)


# ---------------------------------------------------------------------------
# Archivist prompt layers
# ---------------------------------------------------------------------------

def _build_archivist_layer1() -> str:
    """Archivist identity layer (~180 tokens)."""
    return (
        "/nothink\n"
        "You are the Archivist for a D&D 5e game. You maintain the game's "
        "long-term memory and knowledge graph.\n\n"
        "ROLE:\n"
        "- Check [HANDOFF] messages for a summary of what happened this turn.\n"
        "- Review what happened this turn and decide what is worth remembering.\n"
        "- Use archive_event for significant story beats, discoveries, combat "
        "outcomes, player decisions.\n"
        "- Use add_relationship to track connections between characters, NPCs, "
        "locations, quests.\n"
        "- Use npc_remember to record events NPCs witnessed or participated in.\n"
        "- Use update_npc_relationship when NPC attitudes changed.\n"
        "- Use update_quest_objective when quest progress was made.\n\n"
        "RULES:\n"
        "- ONLY archive genuinely significant events (importance >= 5). "
        "Skip routine actions.\n"
        "- Before archiving, use search_memory to check for duplicates.\n"
        "- Importance: 2-3 minor, 5-6 moderate, 8-10 major story beats.\n"
        "- Extract entity names accurately from conversation context.\n"
        '- If nothing significant happened, respond "No archival needed." '
        "and stop.\n"
        "- Never narrate or describe scenes. You are a silent bookkeeper.\n"
        "- Keep tool calls to a maximum of 3-4 per turn.\n"
    )


def _build_archivist_layer4() -> str:
    """Archivist-specific format guidance (~40 tokens)."""
    return (
        "FORMAT:\n"
        "- Respond with a brief summary of what you archived (not shown to player).\n"
        '- If nothing to archive: "No archival needed."\n'
        "- Never use dramatic narration. Be concise and factual.\n"
    )


async def _build_archivist_prompt(ctx: AgentContext) -> str:
    """Build the full 4-layer archivist system prompt."""
    layer1 = _build_archivist_layer1()

    try:
        game_session = await get_or_create_session(ctx.session, ctx.conversation_id)
        phase = ctx.phase or GamePhase.EXPLORATION
        layer2 = _build_layer2_jit_rules(phase)
        layer3 = await _build_layer3_state(ctx.session, game_session)
    except Exception:
        logger.warning("Archivist prompt: layers 2-3 failed", exc_info=True)
        layer2, layer3 = "", ""

    layer4 = _build_archivist_layer4()

    return f"{layer1}\n{layer2}\n{layer3}\n{layer4}"
