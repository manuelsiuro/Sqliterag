"""Full dice notation parser and roller for D&D 5e.

Supports:
  XdY       — roll X dice with Y sides
  +/-N      — flat modifiers
  kh/kl N   — keep highest/lowest N
  dh/dl N   — drop highest/lowest N
  r<N       — reroll results below N (once)
  !         — exploding dice (roll again on max)

Examples:
  "2d6+3"       → roll 2d6, add 3
  "4d6kh3"      → roll 4d6, keep highest 3
  "8d6kh3dl1"   → roll 8d6, keep highest 3 then drop lowest 1
  "1d20+5"      → standard d20 check
  "2d8!"        → exploding 2d8
  "1d20r<2"     → reroll 1s (once)
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field


@dataclass
class DieRoll:
    """Single die result with metadata."""
    value: int
    kept: bool = True
    exploded: bool = False
    rerolled: bool = False
    original: int | None = None  # value before reroll


@dataclass
class DiceResult:
    """Full parsed + rolled dice expression result."""
    notation: str
    groups: list[DiceGroup] = field(default_factory=list)
    flat_modifier: int = 0
    total: int = 0
    label: str = ""

    def to_dict(self) -> dict:
        return {
            "notation": self.notation,
            "label": self.label,
            "groups": [g.to_dict() for g in self.groups],
            "flat_modifier": self.flat_modifier,
            "total": self.total,
        }


@dataclass
class DiceGroup:
    """One XdY group within a larger expression."""
    count: int
    sides: int
    rolls: list[DieRoll] = field(default_factory=list)
    keep_highest: int | None = None
    keep_lowest: int | None = None
    drop_highest: int | None = None
    drop_lowest: int | None = None
    reroll_below: int | None = None
    exploding: bool = False
    subtotal: int = 0

    def to_dict(self) -> dict:
        return {
            "dice": f"{self.count}d{self.sides}",
            "rolls": [
                {
                    "value": r.value,
                    "kept": r.kept,
                    "exploded": r.exploded,
                    "rerolled": r.rerolled,
                    **({"original": r.original} if r.original is not None else {}),
                }
                for r in self.rolls
            ],
            "subtotal": self.subtotal,
        }


# Regex for a single dice group: 4d6kh3dl1r<2!
_DICE_GROUP = re.compile(
    r"(\d+)d(\d+)"          # XdY
    r"(kh\d+|kl\d+)?"       # keep highest/lowest
    r"(dh\d+|dl\d+)?"       # drop highest/lowest
    r"(r<\d+)?"             # reroll below
    r"(!)?",                 # exploding
    re.IGNORECASE,
)

# Full expression: groups joined by +/- with optional flat modifier
_FLAT_MOD = re.compile(r"([+-]\s*\d+)(?!d)")


def parse_and_roll(notation: str, label: str = "") -> DiceResult:
    """Parse a dice notation string and roll all dice. Returns a DiceResult."""
    notation = notation.strip()
    result = DiceResult(notation=notation, label=label)

    # Extract flat modifiers (not followed by 'd')
    flat_total = 0
    cleaned = notation
    for match in _FLAT_MOD.finditer(notation):
        mod_str = match.group(1).replace(" ", "")
        # Only count if it's not part of a dice group
        start = match.start()
        # Check we're not inside XdY
        before = notation[:start]
        if before and before[-1].isdigit() and "d" in notation[start:start+5]:
            continue
        flat_total += int(mod_str)

    result.flat_modifier = flat_total

    # Find and roll each dice group
    for m in _DICE_GROUP.finditer(notation):
        count = int(m.group(1))
        sides = int(m.group(2))

        group = DiceGroup(count=count, sides=sides)

        # Parse modifiers
        if m.group(3):
            token = m.group(3).lower()
            n = int(token[2:])
            if token.startswith("kh"):
                group.keep_highest = n
            else:
                group.keep_lowest = n

        if m.group(4):
            token = m.group(4).lower()
            n = int(token[2:])
            if token.startswith("dh"):
                group.drop_highest = n
            else:
                group.drop_lowest = n

        if m.group(5):
            group.reroll_below = int(m.group(5)[2:])

        if m.group(6):
            group.exploding = True

        _roll_group(group)
        result.groups.append(group)

    result.total = sum(g.subtotal for g in result.groups) + result.flat_modifier
    return result


def _roll_group(group: DiceGroup) -> None:
    """Roll dice for a single group, applying reroll/exploding, then keep/drop."""
    rolls: list[DieRoll] = []

    for _ in range(group.count):
        value = random.randint(1, group.sides)
        die = DieRoll(value=value)

        # Reroll below threshold (once)
        if group.reroll_below and value < group.reroll_below:
            die.original = value
            die.rerolled = True
            die.value = random.randint(1, group.sides)

        rolls.append(die)

        # Exploding: on max, keep rolling
        if group.exploding and die.value == group.sides:
            extra = random.randint(1, group.sides)
            rolls.append(DieRoll(value=extra, exploded=True))
            while extra == group.sides:
                extra = random.randint(1, group.sides)
                rolls.append(DieRoll(value=extra, exploded=True))

    # Sort for keep/drop operations
    sorted_indices = sorted(range(len(rolls)), key=lambda i: rolls[i].value)

    # Keep highest
    if group.keep_highest is not None:
        keep_n = group.keep_highest
        top_indices = set(sorted_indices[-keep_n:])
        for i, r in enumerate(rolls):
            if i not in top_indices:
                r.kept = False

    # Keep lowest
    if group.keep_lowest is not None:
        keep_n = group.keep_lowest
        bottom_indices = set(sorted_indices[:keep_n])
        for i, r in enumerate(rolls):
            if i not in bottom_indices:
                r.kept = False

    # Drop highest
    if group.drop_highest is not None:
        drop_n = group.drop_highest
        top_indices = set(sorted_indices[-drop_n:])
        for i in top_indices:
            rolls[i].kept = False

    # Drop lowest
    if group.drop_lowest is not None:
        drop_n = group.drop_lowest
        bottom_indices = set(sorted_indices[:drop_n])
        for i in bottom_indices:
            rolls[i].kept = False

    group.rolls = rolls
    group.subtotal = sum(r.value for r in rolls if r.kept)


def roll_simple(sides: int, count: int = 1) -> list[int]:
    """Quick roll without notation parsing."""
    return [random.randint(1, sides) for _ in range(count)]
