"""Central RPG game-logic service — D&D 5e rules engine."""

from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rpg import Character, GameSession, Location

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# D&D 5e Constants
# ---------------------------------------------------------------------------

# XP thresholds for levels 1–20 (cumulative XP needed to reach each level)
XP_THRESHOLDS: dict[int, int] = {
    1: 0, 2: 300, 3: 900, 4: 2_700, 5: 6_500,
    6: 14_000, 7: 23_000, 8: 34_000, 9: 48_000, 10: 64_000,
    11: 85_000, 12: 100_000, 13: 120_000, 14: 140_000, 15: 165_000,
    16: 195_000, 17: 225_000, 18: 265_000, 19: 305_000, 20: 355_000,
}

# Hit die per class
CLASS_HIT_DIE: dict[str, int] = {
    "barbarian": 12,
    "fighter": 10, "paladin": 10, "ranger": 10,
    "bard": 8, "cleric": 8, "druid": 8, "monk": 8, "rogue": 8, "warlock": 8,
    "sorcerer": 6, "wizard": 6,
}

# Proficiency bonus by level
PROFICIENCY_BY_LEVEL: dict[int, int] = {
    1: 2, 2: 2, 3: 2, 4: 2,
    5: 3, 6: 3, 7: 3, 8: 3,
    9: 4, 10: 4, 11: 4, 12: 4,
    13: 5, 14: 5, 15: 5, 16: 5,
    17: 6, 18: 6, 19: 6, 20: 6,
}

# Standard D&D conditions
CONDITIONS = [
    "blinded", "charmed", "deafened", "exhaustion", "frightened",
    "grappled", "incapacitated", "invisible", "paralyzed", "petrified",
    "poisoned", "prone", "restrained", "stunned", "unconscious",
]

ABILITY_NAMES = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]


# ---------------------------------------------------------------------------
# Pure math helpers (no DB access)
# ---------------------------------------------------------------------------

def calculate_modifier(score: int) -> int:
    """Standard D&D 5e ability modifier: (score - 10) // 2."""
    return (score - 10) // 2


def calculate_proficiency(level: int) -> int:
    return PROFICIENCY_BY_LEVEL.get(min(max(level, 1), 20), 2)


def calculate_hp(char_class: str, level: int, con_mod: int) -> int:
    """Max HP at a given level: max hit die at L1, average rounded up for subsequent levels."""
    hit_die = CLASS_HIT_DIE.get(char_class.lower(), 8)
    if level <= 0:
        return hit_die + con_mod
    hp = hit_die + con_mod  # Level 1: max die + CON
    avg_roll = hit_die // 2 + 1  # average rounded up
    hp += (level - 1) * (avg_roll + con_mod)
    return max(hp, 1)


def level_for_xp(xp: int) -> int:
    """Return the level a character should be at given total XP."""
    lvl = 1
    for l, threshold in sorted(XP_THRESHOLDS.items()):
        if xp >= threshold:
            lvl = l
    return lvl


def character_to_dict(char: Character) -> dict:
    """Serialize a Character ORM object to a rich JSON-friendly dict."""
    con_mod = calculate_modifier(char.constitution)
    return {
        "name": char.name,
        "race": char.race,
        "class": char.char_class,
        "level": char.level,
        "xp": char.xp,
        "xp_next_level": XP_THRESHOLDS.get(min(char.level + 1, 20), None),
        "proficiency_bonus": calculate_proficiency(char.level),
        "abilities": {
            a: {"score": getattr(char, a), "modifier": calculate_modifier(getattr(char, a))}
            for a in ABILITY_NAMES
        },
        "max_hp": char.max_hp,
        "current_hp": char.current_hp,
        "temp_hp": char.temp_hp,
        "armor_class": char.armor_class,
        "speed": char.speed,
        "conditions": json.loads(char.conditions),
        "spell_slots": json.loads(char.spell_slots),
        "death_saves": json.loads(char.death_saves),
        "is_player": char.is_player,
        "is_alive": char.is_alive,
        "hit_die": f"d{CLASS_HIT_DIE.get(char.char_class.lower(), 8)}",
    }


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

async def get_or_create_session(db: AsyncSession, conversation_id: str) -> GameSession:
    """Return the GameSession for this conversation, creating one if needed."""
    result = await db.execute(
        select(GameSession).where(GameSession.conversation_id == conversation_id)
    )
    gs = result.scalars().first()
    if gs is None:
        gs = GameSession(conversation_id=conversation_id)
        db.add(gs)
        await db.flush()
    return gs


async def get_character_by_name(db: AsyncSession, session_id: str, name: str) -> Character | None:
    result = await db.execute(
        select(Character).where(
            Character.session_id == session_id,
            Character.name.ilike(name),
        )
    )
    return result.scalars().first()


async def get_location_by_name(db: AsyncSession, session_id: str, name: str) -> Location | None:
    result = await db.execute(
        select(Location).where(
            Location.session_id == session_id,
            Location.name.ilike(name),
        )
    )
    return result.scalars().first()
