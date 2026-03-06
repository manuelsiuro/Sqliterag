"""Handoff summaries — structured inter-agent communication.

Phase 4.6: Summarizes tool results into compact one-liners so downstream
agents can quickly understand what happened without parsing raw JSON.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Type-specific summarizers (each returns a compact one-liner)
# ---------------------------------------------------------------------------

def _summarize_attack(d: dict[str, Any]) -> str:
    attacker = d.get("attacker", "?")
    target = d.get("target", "?")
    weapon = d.get("weapon", "weapon")
    rolls = d.get("attack_rolls", [])
    roll_str = f"d20={rolls[0]}" if rolls else "d20=?"
    hit = "HIT" if d.get("hit") else "MISS"
    dmg = d.get("damage", "?")
    return f"{attacker} attacks {target} ({weapon}): {roll_str}, {hit}. {dmg} damage."


def _summarize_spell(d: dict[str, Any]) -> str:
    caster = d.get("caster", d.get("character", "?"))
    spell = d.get("spell_name", d.get("spell", "spell"))
    damage = d.get("damage", d.get("total_damage", ""))
    target = d.get("target", "")
    parts = [f"{caster} casts {spell}"]
    if target:
        parts.append(f" on {target}")
    if damage:
        parts.append(f": {damage} damage")
    return "".join(parts) + "."


def _summarize_check(d: dict[str, Any]) -> str:
    char = d.get("character", "?")
    ability = d.get("ability", d.get("check_type", "?"))
    total = d.get("total", "?")
    dc = d.get("dc", "?")
    success = "SUCCESS" if d.get("success") else "FAILURE"
    return f"{char} {ability}: total {total} vs DC {dc}, {success}."


def _summarize_damage(d: dict[str, Any]) -> str:
    target = d.get("target", d.get("character", "?"))
    amount = d.get("amount", d.get("damage", "?"))
    hp = d.get("hp", d.get("current_hp", "?"))
    max_hp = d.get("max_hp", "")
    hp_str = f"HP {hp}/{max_hp}" if max_hp else f"HP {hp}"
    return f"{target} takes {amount} damage. {hp_str}."


def _summarize_heal(d: dict[str, Any]) -> str:
    target = d.get("target", d.get("character", "?"))
    amount = d.get("amount", d.get("healed", "?"))
    hp = d.get("hp", d.get("current_hp", "?"))
    max_hp = d.get("max_hp", "")
    hp_str = f"HP {hp}/{max_hp}" if max_hp else f"HP {hp}"
    return f"{target} heals {amount}. {hp_str}."


def _summarize_death_save(d: dict[str, Any]) -> str:
    char = d.get("character", "?")
    result = "SUCCESS" if d.get("success") else "FAILURE"
    successes = d.get("successes", "?")
    failures = d.get("failures", "?")
    return f"{char} death save: {result} ({successes} successes, {failures} failures)."


def _summarize_initiative(d: dict[str, Any]) -> str:
    order = d.get("order", d.get("initiative_order", []))
    if isinstance(order, list):
        entries = ", ".join(
            f"{e.get('name', '?')}({e.get('initiative', '?')})"
            for e in order[:6]
        )
        return f"Initiative: {entries}."
    return "Initiative order set."


def _summarize_location(d: dict[str, Any]) -> str:
    name = d.get("name", "?")
    exits = d.get("exits", {})
    exit_str = ", ".join(f"{k}->{v}" for k, v in exits.items()) if isinstance(exits, dict) else ""
    moved_by = d.get("moved_by", "")
    prefix = f"{moved_by} moved to" if moved_by else "At"
    result = f"{prefix} {name}."
    if exit_str:
        result += f" Exits: {exit_str}."
    return result


def _summarize_npc(d: dict[str, Any]) -> str:
    name = d.get("name", "?")
    disposition = d.get("disposition", "")
    return f"NPC: {name}" + (f" ({disposition})" if disposition else "") + "."


def _summarize_quest(d: dict[str, Any]) -> str:
    title = d.get("title", d.get("name", "?"))
    status = d.get("status", "active")
    return f"Quest: {title} ({status})."


def _summarize_memory(d: dict[str, Any]) -> str:
    event = d.get("event", d.get("content", ""))
    if event and len(event) > 60:
        event = event[:57] + "..."
    return f"Archived: {event}" if event else "Memory archived."


_SUMMARIZERS: dict[str, Callable[[dict[str, Any]], str]] = {
    "attack_result": _summarize_attack,
    "spell_cast": _summarize_spell,
    "check_result": _summarize_check,
    "damage_result": _summarize_damage,
    "heal_result": _summarize_heal,
    "death_save": _summarize_death_save,
    "initiative_order": _summarize_initiative,
    "location": _summarize_location,
    "npc_info": _summarize_npc,
    "quest_info": _summarize_quest,
    "memory_archived": _summarize_memory,
}


def summarize_tool_result(tool_name: str, result_json: str) -> str:
    """Parse a tool result JSON and produce a compact one-liner summary."""
    try:
        data = json.loads(result_json)
    except (json.JSONDecodeError, TypeError):
        return f"{tool_name}: completed."

    if not isinstance(data, dict):
        return f"{tool_name}: completed."

    result_type = data.get("type", "")
    summarizer = _SUMMARIZERS.get(result_type)
    if summarizer:
        try:
            return summarizer(data)
        except Exception:
            logger.debug("Summarizer failed for type=%s", result_type, exc_info=True)
    return f"{tool_name}: completed."


def build_handoff_summary(
    agent_name: str,
    messages: list[dict],
    start_index: int,
) -> str | None:
    """Scan messages[start_index:] for tool results, summarize each.

    Returns a formatted [HANDOFF] block or None if no tool results found.
    """
    summaries: list[str] = []

    for msg in messages[start_index:]:
        if msg.get("role") != "tool":
            continue
        tool_name = msg.get("tool_name", "unknown")
        content = msg.get("content", "")
        summary = summarize_tool_result(tool_name, content)
        summaries.append(f"- {summary}")

    if not summaries:
        return None

    lines = "\n".join(summaries)
    return f"[HANDOFF from {agent_name}]\n{lines}\n[/HANDOFF]"
