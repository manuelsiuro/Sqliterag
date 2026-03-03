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
    XP_THRESHOLDS,
    calculate_hp,
    calculate_modifier,
    calculate_proficiency,
    character_to_dict,
    generate_character_name,
    generate_world_name,
    get_character_by_name,
    get_location_by_name,
    get_or_create_session,
    is_generic_name,
    level_for_xp,
)
