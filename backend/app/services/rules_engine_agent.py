"""RulesEngineAgent -- strict mechanical agent for D&D 5e combat resolution.

Phase 4.3: Handles all combat mechanics (attack rolls, damage, death saves,
initiative) so the DM can't fudge dice.  Only runs during COMBAT phase.
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

_RULES_ENGINE_TOOLS: frozenset[str] = frozenset({
    # Combat
    "start_combat", "get_combat_status", "next_turn", "end_combat",
    "attack", "cast_spell", "heal", "take_damage", "death_save", "combat_action",
    # Dice
    "roll_d20", "roll_dice", "roll_check", "roll_save",
    # Characters (read + update, NOT create)
    "get_character", "update_character", "list_characters",
    # Inventory (equip in combat)
    "equip_item", "unequip_item", "get_inventory",
    # Rest
    "short_rest", "long_rest",
})


class RulesEngineAgent(SingleAgent):
    """Strict mechanical agent -- resolves combat via tools, never narrates."""

    @property
    def name(self) -> str:
        return "rules_engine"

    @property
    def allowed_tool_names(self) -> frozenset[str] | None:
        return _RULES_ENGINE_TOOLS

    def should_run(self, ctx: AgentContext) -> bool:
        return ctx.phase == GamePhase.COMBAT

    def build_system_prompt(self, ctx: AgentContext) -> str | None:
        return None  # Sync path -- signals orchestrator to try async

    async def build_system_prompt_async(self, ctx: AgentContext) -> str | None:
        return await _build_rules_engine_prompt(ctx)


# ---------------------------------------------------------------------------
# Rules Engine prompt layers
# ---------------------------------------------------------------------------

def _build_rules_engine_layer1() -> str:
    return (
        "/nothink\n"
        "You are the Rules Engine for a D&D 5e game. You handle ALL mechanical resolution.\n\n"
        "ROLE:\n"
        "- Resolve combat turns strictly following initiative order.\n"
        "- Execute attack rolls, damage, saving throws, spell effects via tools.\n"
        "- Track HP, conditions, death saves through tools.\n"
        "- Follow D&D 5e RAW (Rules As Written). Never skip steps.\n\n"
        "ABSOLUTE RULES:\n"
        "- ALWAYS use tools. Never describe outcomes without tool calls.\n"
        "- Use get_combat_status to check whose turn it is before acting.\n"
        "- Use next_turn to advance initiative. Never skip combatants.\n"
        "- Use attack for weapon attacks. Use cast_spell for spells.\n"
        "- Apply damage immediately via take_damage after each hit.\n"
        "- At 0 HP: use death_save tool to track death saving throws.\n"
        "- End combat with end_combat when all enemies are defeated or fled.\n"
        "- If the player request is non-mechanical (dialogue, exploration), "
        "respond with a single brief sentence. The Narrator handles storytelling.\n"
    )


def _build_rules_engine_layer4() -> str:
    return (
        "FORMAT:\n"
        "- Report results concisely. List rolls and outcomes.\n"
        "- Do NOT narrate dramatically. The Narrator handles storytelling.\n"
        '- Example: "Arin attacks Goblin: d20+5=18 vs AC 15, HIT. 1d8+3=7 slashing."\n'
    )


async def _build_rules_engine_prompt(ctx: AgentContext) -> str:
    layer1 = _build_rules_engine_layer1()

    try:
        game_session = await get_or_create_session(ctx.session, ctx.conversation_id)
        phase = ctx.phase or GamePhase.COMBAT
        layer2 = _build_layer2_jit_rules(phase)
        layer3 = await _build_layer3_state(ctx.session, game_session)
    except Exception:
        logger.warning("Rules Engine prompt: failed to build layers 2-3, using layer1 only", exc_info=True)
        layer2 = ""
        layer3 = ""

    layer4 = _build_rules_engine_layer4()

    return f"{layer1}\n{layer2}\n{layer3}\n{layer4}"
