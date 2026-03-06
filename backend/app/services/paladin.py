"""PALADIN self-correction — retry when LLM narrates without calling tools.

Phase 4.7: Detects when the LLM describes mechanical game actions in prose
instead of calling the appropriate tools, and builds a correction message
to prompt a retry.
"""

from __future__ import annotations

import re

CORRECTION_MARKER = "[SELF-CORRECTION REQUIRED]"

# Patterns that indicate the LLM narrated mechanical actions without tools
_MECHANICAL_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\b(?:attacks?|strikes?|swings?)\b.*\b(?:hits?|misses?|deals?\s+\d+|damage)\b",
        r"\b(?:rolls?\s+(?:a\s+)?d\d+)\b",
        r"\btakes?\s+\d+\s+(?:damage|points?\s+of)\b",
        r"\b(?:heals?|recovers?)\s+\d+\s+(?:hit\s+points?|hp)\b",
        r"\bcasts?\s+\w+\s+(?:spell|on)\b",
        r"\bmakes?\s+a\s+\w+\s+(?:check|save|saving\s+throw)\b",
        r"\brolls?\s+initiative\b",
        r"\bdeath\s+sav(?:e|ing)\b",
    ]
]


def should_self_correct(
    agent_name: str,
    correction_mode: str,
    phase: object | None,
    content: str,
    user_message: str,
) -> bool:
    """Decide whether the agent's text-only response needs a tool-call retry.

    Correction modes:
    - "minimal": Never correct (Archivist — text-only is legitimate).
    - "aggressive": Always correct if non-empty content during a game phase,
      unless it's a short pass-through (<50 chars).
    - "moderate": Correct only if content contains mechanical action keywords.
    """
    if correction_mode == "minimal":
        return False

    if phase is None:
        return False

    if not content or not content.strip():
        return False

    if correction_mode == "aggressive":
        # Short pass-through responses are OK
        return len(content.strip()) >= 50

    # "moderate" mode — check for mechanical action patterns
    return any(pat.search(content) for pat in _MECHANICAL_PATTERNS)


def build_correction_message(content: str, attempt: int, phase: object | None) -> dict:
    """Build an ephemeral system message prompting the LLM to retry with tools."""
    msg = (
        f"{CORRECTION_MARKER}\n"
        "Your previous response described mechanical game actions without calling tools.\n"
        f'Your response was: "{content[:300]}"\n\n'
        "You MUST use tool calls for attacks, damage, ability checks, spells, dice, and movement.\n"
        "Retry now. Call the appropriate tool(s)."
    )

    if attempt >= 2:
        msg += "\nThis is your FINAL attempt. You MUST call at least one tool."

    return {"role": "system", "content": msg}
