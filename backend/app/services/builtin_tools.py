"""Built-in tool implementations that ship with the app."""

from __future__ import annotations

import json
import random


def roll_d20(modifier: int = 0, num_dice: int = 1) -> str:
    """Roll one or more d20 dice with an optional modifier."""
    rolls = [random.randint(1, 20) for _ in range(num_dice)]
    total = sum(rolls) + modifier

    return json.dumps({
        "type": "roll_d20",
        "rolls": rolls,
        "modifier": modifier,
        "total": total,
    })


BUILTIN_REGISTRY: dict[str, callable] = {
    "roll_d20": roll_d20,
}
