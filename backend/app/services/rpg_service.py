"""Central RPG game-logic service — D&D 5e rules engine."""

from __future__ import annotations

import json
import logging
import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rpg import Character, GameSession, Item, Location, NPC, Quest

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
# D&D 5e Encounter Balancing Constants (Phase 5.4)
# ---------------------------------------------------------------------------

# Per-level XP budgets for Easy/Medium/Hard/Deadly (DMG Chapter 3)
ENCOUNTER_XP_THRESHOLDS: dict[int, dict[str, int]] = {
    1: {"easy": 25, "medium": 50, "hard": 75, "deadly": 100},
    2: {"easy": 50, "medium": 100, "hard": 150, "deadly": 200},
    3: {"easy": 75, "medium": 150, "hard": 225, "deadly": 400},
    4: {"easy": 125, "medium": 250, "hard": 375, "deadly": 500},
    5: {"easy": 250, "medium": 500, "hard": 750, "deadly": 1100},
    6: {"easy": 300, "medium": 600, "hard": 900, "deadly": 1400},
    7: {"easy": 350, "medium": 750, "hard": 1100, "deadly": 1700},
    8: {"easy": 450, "medium": 900, "hard": 1400, "deadly": 2100},
    9: {"easy": 550, "medium": 1100, "hard": 1600, "deadly": 2400},
    10: {"easy": 600, "medium": 1200, "hard": 1900, "deadly": 2800},
    11: {"easy": 800, "medium": 1600, "hard": 2400, "deadly": 3600},
    12: {"easy": 1000, "medium": 2000, "hard": 3000, "deadly": 4500},
    13: {"easy": 1100, "medium": 2200, "hard": 3400, "deadly": 5100},
    14: {"easy": 1250, "medium": 2500, "hard": 3800, "deadly": 5700},
    15: {"easy": 1400, "medium": 2800, "hard": 4300, "deadly": 6400},
    16: {"easy": 1600, "medium": 3200, "hard": 4800, "deadly": 7200},
    17: {"easy": 2000, "medium": 3900, "hard": 5900, "deadly": 8800},
    18: {"easy": 2100, "medium": 4200, "hard": 6300, "deadly": 9500},
    19: {"easy": 2400, "medium": 4900, "hard": 7300, "deadly": 10900},
    20: {"easy": 2800, "medium": 5700, "hard": 8500, "deadly": 12700},
}

# CR string -> XP value (SRD)
CR_TO_XP: dict[str, int] = {
    "0": 10, "1/8": 25, "1/4": 50, "1/2": 100,
    "1": 200, "2": 450, "3": 700, "4": 1100, "5": 1800,
    "6": 2300, "7": 2900, "8": 3900, "9": 5000, "10": 5900,
    "11": 7200, "12": 8400, "13": 10000, "14": 11500, "15": 13000,
    "16": 15000, "17": 18000, "18": 20000, "19": 22000, "20": 25000,
}

# Monster count -> encounter multiplier (DMG)
ENCOUNTER_MULTIPLIERS: list[tuple[int, float]] = [
    (1, 1.0), (2, 1.5), (3, 2.0), (7, 2.5), (11, 3.0), (15, 4.0),
]

# CR -> quick monster stats (DMG)
MONSTER_STATS_BY_CR: dict[str, dict] = {
    "0":   {"ac": 10, "hp_min": 1,   "hp_max": 6,   "atk_bonus": 2, "dmg_min": 0, "dmg_max": 1,  "save_dc": 10},
    "1/8": {"ac": 11, "hp_min": 7,   "hp_max": 14,  "atk_bonus": 3, "dmg_min": 2, "dmg_max": 3,  "save_dc": 11},
    "1/4": {"ac": 11, "hp_min": 15,  "hp_max": 24,  "atk_bonus": 3, "dmg_min": 4, "dmg_max": 5,  "save_dc": 11},
    "1/2": {"ac": 12, "hp_min": 25,  "hp_max": 38,  "atk_bonus": 3, "dmg_min": 6, "dmg_max": 8,  "save_dc": 12},
    "1":   {"ac": 13, "hp_min": 39,  "hp_max": 55,  "atk_bonus": 3, "dmg_min": 9, "dmg_max": 14, "save_dc": 13},
    "2":   {"ac": 13, "hp_min": 56,  "hp_max": 70,  "atk_bonus": 3, "dmg_min": 15, "dmg_max": 20, "save_dc": 13},
    "3":   {"ac": 13, "hp_min": 71,  "hp_max": 85,  "atk_bonus": 4, "dmg_min": 21, "dmg_max": 26, "save_dc": 13},
    "4":   {"ac": 14, "hp_min": 86,  "hp_max": 100, "atk_bonus": 5, "dmg_min": 27, "dmg_max": 32, "save_dc": 14},
    "5":   {"ac": 15, "hp_min": 101, "hp_max": 115, "atk_bonus": 6, "dmg_min": 33, "dmg_max": 38, "save_dc": 15},
    "6":   {"ac": 15, "hp_min": 116, "hp_max": 130, "atk_bonus": 6, "dmg_min": 39, "dmg_max": 44, "save_dc": 15},
    "7":   {"ac": 15, "hp_min": 131, "hp_max": 145, "atk_bonus": 6, "dmg_min": 45, "dmg_max": 50, "save_dc": 15},
    "8":   {"ac": 16, "hp_min": 146, "hp_max": 160, "atk_bonus": 7, "dmg_min": 51, "dmg_max": 56, "save_dc": 16},
    "9":   {"ac": 16, "hp_min": 161, "hp_max": 175, "atk_bonus": 7, "dmg_min": 57, "dmg_max": 62, "save_dc": 16},
    "10":  {"ac": 17, "hp_min": 176, "hp_max": 190, "atk_bonus": 7, "dmg_min": 63, "dmg_max": 68, "save_dc": 17},
    "11":  {"ac": 17, "hp_min": 191, "hp_max": 205, "atk_bonus": 8, "dmg_min": 69, "dmg_max": 74, "save_dc": 17},
    "12":  {"ac": 17, "hp_min": 206, "hp_max": 220, "atk_bonus": 8, "dmg_min": 75, "dmg_max": 80, "save_dc": 17},
    "13":  {"ac": 18, "hp_min": 221, "hp_max": 235, "atk_bonus": 8, "dmg_min": 81, "dmg_max": 86, "save_dc": 18},
    "14":  {"ac": 18, "hp_min": 236, "hp_max": 250, "atk_bonus": 8, "dmg_min": 87, "dmg_max": 92, "save_dc": 18},
    "15":  {"ac": 18, "hp_min": 251, "hp_max": 265, "atk_bonus": 8, "dmg_min": 93, "dmg_max": 98, "save_dc": 18},
    "16":  {"ac": 18, "hp_min": 266, "hp_max": 280, "atk_bonus": 9, "dmg_min": 99, "dmg_max": 104, "save_dc": 18},
    "17":  {"ac": 19, "hp_min": 281, "hp_max": 295, "atk_bonus": 10, "dmg_min": 105, "dmg_max": 110, "save_dc": 19},
    "18":  {"ac": 19, "hp_min": 296, "hp_max": 310, "atk_bonus": 10, "dmg_min": 111, "dmg_max": 116, "save_dc": 19},
    "19":  {"ac": 19, "hp_min": 311, "hp_max": 325, "atk_bonus": 10, "dmg_min": 117, "dmg_max": 122, "save_dc": 19},
    "20":  {"ac": 19, "hp_min": 326, "hp_max": 340, "atk_bonus": 10, "dmg_min": 123, "dmg_max": 140, "save_dc": 19},
}

# Creature type -> base ability scores
CREATURE_TYPE_TEMPLATES: dict[str, dict[str, int]] = {
    "beast":        {"strength": 14, "dexterity": 12, "constitution": 14, "intelligence": 3,  "wisdom": 12, "charisma": 6},
    "humanoid":     {"strength": 12, "dexterity": 12, "constitution": 12, "intelligence": 10, "wisdom": 10, "charisma": 10},
    "undead":       {"strength": 14, "dexterity": 8,  "constitution": 16, "intelligence": 6,  "wisdom": 8,  "charisma": 5},
    "fiend":        {"strength": 16, "dexterity": 12, "constitution": 16, "intelligence": 12, "wisdom": 12, "charisma": 14},
    "dragon":       {"strength": 18, "dexterity": 10, "constitution": 18, "intelligence": 14, "wisdom": 12, "charisma": 16},
    "construct":    {"strength": 16, "dexterity": 8,  "constitution": 18, "intelligence": 3,  "wisdom": 10, "charisma": 1},
    "aberration":   {"strength": 14, "dexterity": 10, "constitution": 14, "intelligence": 16, "wisdom": 14, "charisma": 10},
    "elemental":    {"strength": 16, "dexterity": 14, "constitution": 16, "intelligence": 6,  "wisdom": 10, "charisma": 8},
    "monstrosity":  {"strength": 16, "dexterity": 12, "constitution": 14, "intelligence": 6,  "wisdom": 12, "charisma": 8},
    "giant":        {"strength": 20, "dexterity": 8,  "constitution": 18, "intelligence": 8,  "wisdom": 10, "charisma": 8},
    "fey":          {"strength": 10, "dexterity": 16, "constitution": 10, "intelligence": 14, "wisdom": 14, "charisma": 16},
    "celestial":    {"strength": 16, "dexterity": 14, "constitution": 16, "intelligence": 14, "wisdom": 16, "charisma": 18},
    "plant":        {"strength": 14, "dexterity": 6,  "constitution": 16, "intelligence": 3,  "wisdom": 10, "charisma": 3},
    "ooze":         {"strength": 14, "dexterity": 6,  "constitution": 16, "intelligence": 1,  "wisdom": 6,  "charisma": 1},
}


# ---------------------------------------------------------------------------
# Fantasy Name Generation
# ---------------------------------------------------------------------------

WORLD_PREFIXES = [
    "Storm", "Shadow", "Iron", "Myth", "Silver", "Thunder", "Ember", "Frost",
    "Dragon", "Raven", "Crystal", "Obsidian", "Golden", "Ashen", "Thorn",
    "Star", "Moon", "Sun", "Blood", "Stone", "Dusk", "Dawn", "Wyrd",
    "Crimson", "Elder", "Hollow", "Mist", "Night", "Rune", "Wild",
]

WORLD_SUFFIXES = [
    "hold", "vale", "reach", "march", "fell", "keep", "spire", "haven",
    "moor", "dale", "heim", "gate", "crest", "forge", "watch", "peak",
    "mere", "hollow", "shire", "wind", "gard", "run", "thorn", "bane",
    "wood", "barrow", "deep", "crown", "stone", "port",
]

FANTASY_FIRST_NAMES = [
    "Aldric", "Brynn", "Cedric", "Dahlia", "Elara", "Fenris", "Gwen",
    "Halon", "Isolde", "Jareth", "Kael", "Lyra", "Maren", "Nyx",
    "Orin", "Petra", "Quinn", "Rowan", "Sera", "Thane", "Una",
    "Vex", "Wren", "Xara", "Yorick", "Zara", "Ashwin", "Bram",
    "Cira", "Dorin", "Eira", "Finn", "Greta", "Holt", "Iris",
    "Jace", "Kira", "Lox", "Mira", "Nolan", "Ophelia", "Pike",
]

FANTASY_SURNAMES = [
    "Ashford", "Blackthorn", "Cindervane", "Duskwalker", "Emberheart",
    "Frostbane", "Greymane", "Holloway", "Ironhand", "Jadecrest",
    "Keenblade", "Lightweaver", "Moonwhisper", "Nightbloom", "Oakenshield",
    "Proudstone", "Quicksilver", "Ravenscar", "Stormwind", "Thornfield",
    "Underhill", "Voidgazer", "Windrunner", "Yarrow", "Zephyrblade",
    "Brightforge", "Darkhollow", "Farrow", "Grimshaw", "Hawkstone",
]

_GENERIC_NAMES = {
    "new adventurer", "adventurer", "player", "unnamed", "character",
    "hero", "protagonist", "new character", "test", "player character",
    "my character", "default", "unknown",
}


def generate_world_name() -> str:
    """Generate a fantasy world name by combining a prefix and suffix."""
    return random.choice(WORLD_PREFIXES) + random.choice(WORLD_SUFFIXES)


def generate_character_name() -> str:
    """Generate a fantasy character name."""
    return f"{random.choice(FANTASY_FIRST_NAMES)} {random.choice(FANTASY_SURNAMES)}"


def is_generic_name(name: str) -> bool:
    """Check if a name is a placeholder/generic name that should be replaced."""
    return name.strip().lower() in _GENERIC_NAMES


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


# ---------------------------------------------------------------------------
# Encounter Balancing Math (Phase 5.4)
# ---------------------------------------------------------------------------

def _cr_to_float(cr: str) -> float:
    """Convert CR string to float ('1/4' -> 0.25)."""
    if "/" in cr:
        num, den = cr.split("/")
        return int(num) / int(den)
    return float(cr)


def normalize_cr(cr_input) -> str:
    """Normalize CR input to string key (0.25 -> '1/4', 1 -> '1')."""
    _FLOAT_TO_FRAC = {0.125: "1/8", 0.25: "1/4", 0.5: "1/2"}
    if isinstance(cr_input, str):
        cr_input = cr_input.strip()
        if cr_input in CR_TO_XP:
            return cr_input
        try:
            val = float(cr_input)
        except ValueError:
            return "1"
    else:
        val = float(cr_input)
    if val in _FLOAT_TO_FRAC:
        return _FLOAT_TO_FRAC[val]
    int_val = int(val)
    key = str(int_val)
    return key if key in CR_TO_XP else "1"


def get_encounter_multiplier(num_monsters: int) -> float:
    """DMG encounter multiplier based on monster count."""
    mult = 1.0
    for threshold, m in ENCOUNTER_MULTIPLIERS:
        if num_monsters >= threshold:
            mult = m
    return mult


def get_party_xp_thresholds(levels: list[int]) -> dict[str, int]:
    """Sum Easy/Medium/Hard/Deadly XP thresholds for a party."""
    totals = {"easy": 0, "medium": 0, "hard": 0, "deadly": 0}
    for lvl in levels:
        clamped = min(max(lvl, 1), 20)
        for diff in totals:
            totals[diff] += ENCOUNTER_XP_THRESHOLDS[clamped][diff]
    return totals


def calculate_encounter_difficulty(
    party_levels: list[int],
    enemy_crs: list[str],
) -> dict:
    """Full DMG encounter difficulty assessment."""
    raw_xp = sum(CR_TO_XP.get(cr, 200) for cr in enemy_crs)
    multiplier = get_encounter_multiplier(len(enemy_crs))
    adjusted_xp = int(raw_xp * multiplier)
    thresholds = get_party_xp_thresholds(party_levels)

    if adjusted_xp >= thresholds["deadly"]:
        difficulty = "deadly"
    elif adjusted_xp >= thresholds["hard"]:
        difficulty = "hard"
    elif adjusted_xp >= thresholds["medium"]:
        difficulty = "medium"
    else:
        difficulty = "easy"

    return {
        "difficulty": difficulty,
        "adjusted_xp": adjusted_xp,
        "raw_xp": raw_xp,
        "multiplier": multiplier,
        "thresholds": thresholds,
        "num_enemies": len(enemy_crs),
        "num_players": len(party_levels),
    }


def generate_monster_stats(cr: str, creature_type: str = "humanoid") -> dict:
    """Generate D&D 5e monster stats from CR + creature type template."""
    cr = normalize_cr(cr)
    stats = MONSTER_STATS_BY_CR.get(cr, MONSTER_STATS_BY_CR["1"])
    template = CREATURE_TYPE_TEMPLATES.get(creature_type.lower(), CREATURE_TYPE_TEMPLATES["humanoid"])
    hp = random.randint(stats["hp_min"], stats["hp_max"])
    cr_float = _cr_to_float(cr)
    level = max(1, int(cr_float)) if cr_float >= 1 else 1

    return {
        "cr": cr,
        "xp": CR_TO_XP.get(cr, 200),
        "creature_type": creature_type.lower(),
        "armor_class": stats["ac"],
        "max_hp": hp,
        "attack_bonus": stats["atk_bonus"],
        "damage_per_round": f"{stats['dmg_min']}-{stats['dmg_max']}",
        "save_dc": stats["save_dc"],
        "level": level,
        "abilities": dict(template),
        "char_class": creature_type.capitalize(),
    }


def estimate_cr_from_hp(max_hp: int) -> str:
    """Reverse lookup: find CR whose hp range contains max_hp."""
    best_cr = "1"
    best_dist = float("inf")
    for cr, stats in MONSTER_STATS_BY_CR.items():
        mid = (stats["hp_min"] + stats["hp_max"]) / 2
        dist = abs(max_hp - mid)
        if stats["hp_min"] <= max_hp <= stats["hp_max"]:
            return cr
        if dist < best_dist:
            best_dist = dist
            best_cr = cr
    return best_cr


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
        gs = GameSession(conversation_id=conversation_id, world_name=generate_world_name())
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


async def get_npc_by_name(db: AsyncSession, session_id: str, name: str) -> NPC | None:
    result = await db.execute(
        select(NPC).where(NPC.session_id == session_id, NPC.name.ilike(name))
    )
    return result.scalars().first()


async def get_quest_by_title(db: AsyncSession, session_id: str, title: str) -> Quest | None:
    result = await db.execute(
        select(Quest).where(Quest.session_id == session_id, Quest.title.ilike(title))
    )
    return result.scalars().first()


async def resolve_entity(db: AsyncSession, session_id: str, entity_type: str, name: str) -> tuple[str, str | None]:
    """Resolve entity name -> (type, id). Returns (type, None) if not found."""
    if entity_type == "character":
        e = await get_character_by_name(db, session_id, name)
    elif entity_type == "npc":
        e = await get_npc_by_name(db, session_id, name)
    elif entity_type == "location":
        e = await get_location_by_name(db, session_id, name)
    elif entity_type == "quest":
        e = await get_quest_by_title(db, session_id, name)
    elif entity_type == "item":
        result = await db.execute(select(Item).where(Item.name.ilike(name)))
        e = result.scalars().first()
    else:
        return (entity_type, None)
    return (entity_type, e.id if e else None)


async def resolve_entity_name(db: AsyncSession, entity_type: str, entity_id: str) -> str:
    """Reverse lookup: entity ID -> display name."""
    model_map = {
        "character": (Character, "name"),
        "npc": (NPC, "name"),
        "location": (Location, "name"),
        "quest": (Quest, "title"),
        "item": (Item, "name"),
    }
    entry = model_map.get(entity_type)
    if not entry:
        return entity_id
    model_cls, name_col = entry
    result = await db.execute(select(getattr(model_cls, name_col)).where(model_cls.id == entity_id))
    return result.scalar() or entity_id
