"""Shared imports for builtin tool modules."""

from __future__ import annotations

import json
import random

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.rpg.dice import parse_and_roll, roll_simple
from app.services.rpg_service import (
    ABILITY_NAMES,
    CLASS_HIT_DIE,
    CONDITIONS,
    CR_TO_XP,
    CREATURE_TYPE_TEMPLATES,
    MONSTER_STATS_BY_CR,
    XP_THRESHOLDS,
    calculate_encounter_difficulty,
    calculate_hp,
    calculate_modifier,
    calculate_proficiency,
    character_to_dict,
    estimate_cr_from_hp,
    generate_character_name,
    generate_monster_stats,
    generate_world_name,
    get_character_by_name,
    get_location_by_name,
    get_npc_by_name,
    get_or_create_session,
    get_party_xp_thresholds,
    get_quest_by_title,
    is_generic_name,
    level_for_xp,
    normalize_cr,
    resolve_entity,
    resolve_entity_name,
)
