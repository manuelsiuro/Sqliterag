"""Auto-extract relationship edges from tool results (Phase 3.3).

Post-hook that runs after builtin tool execution. Maps tool names to
extractor functions that create/update/remove knowledge-graph edges
without modifying individual tool modules.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Callable, Coroutine

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.rpg import Character, Relationship
from app.services.rpg_service import (
    get_or_create_session,
    resolve_entity,
)

logger = logging.getLogger(__name__)

# Type alias for extractor functions
Extractor = Callable[
    [AsyncSession, str, dict, dict],
    Coroutine[None, None, None],
]

_ENTITY_TYPES = {"character", "npc", "location", "quest", "item"}

_FAMILIARITY_STRENGTH = {
    "stranger": 20,
    "acquaintance": 40,
    "friend": 70,
    "close_friend": 90,
}


def _normalize_relationship(rel: str) -> str:
    """Normalize relationship string to lowercase with underscores."""
    return re.sub(r"[^a-z0-9]+", "_", rel.strip().lower()).strip("_")


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

async def _upsert_edge(
    session: AsyncSession,
    session_id: str,
    source_type: str,
    source_id: str,
    target_type: str,
    target_id: str,
    relationship: str,
    strength: int = 50,
    detail: str = "{}",
) -> None:
    """Create or update a relationship edge."""
    result = await session.execute(
        select(Relationship).where(
            Relationship.session_id == session_id,
            Relationship.source_type == source_type,
            Relationship.source_id == source_id,
            Relationship.target_type == target_type,
            Relationship.target_id == target_id,
            Relationship.relationship == relationship,
        )
    )
    existing = result.scalars().first()

    if existing:
        existing.strength = max(0, min(100, strength))
        existing.detail = detail
        existing.updated_at = datetime.now(timezone.utc)
    else:
        session.add(Relationship(
            session_id=session_id,
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            relationship=relationship,
            strength=max(0, min(100, strength)),
            detail=detail,
        ))
    await session.flush()


async def _remove_edge(
    session: AsyncSession,
    session_id: str,
    source_type: str,
    source_id: str,
    target_type: str,
    target_id: str,
    relationship: str,
) -> None:
    """Delete a specific relationship edge if it exists."""
    await session.execute(
        delete(Relationship).where(
            Relationship.session_id == session_id,
            Relationship.source_type == source_type,
            Relationship.source_id == source_id,
            Relationship.target_type == target_type,
            Relationship.target_id == target_id,
            Relationship.relationship == relationship,
        )
    )
    await session.flush()


async def _replace_located_at(
    session: AsyncSession,
    session_id: str,
    source_type: str,
    source_id: str,
    new_target_id: str,
    strength: int = 100,
) -> None:
    """Replace ALL existing located_at edges for a source with a single new one."""
    await session.execute(
        delete(Relationship).where(
            Relationship.session_id == session_id,
            Relationship.source_type == source_type,
            Relationship.source_id == source_id,
            Relationship.relationship == "located_at",
        )
    )
    session.add(Relationship(
        session_id=session_id,
        source_type=source_type,
        source_id=source_id,
        target_type="location",
        target_id=new_target_id,
        relationship="located_at",
        strength=strength,
    ))
    await session.flush()


async def _auto_detect_type(
    session: AsyncSession,
    session_id: str,
    name: str,
) -> tuple[str, str | None]:
    """Try each entity type in order until we find a match."""
    for etype in ("character", "npc", "location", "quest", "item"):
        _, eid = await resolve_entity(session, session_id, etype, name)
        if eid:
            return (etype, eid)
    return ("unknown", None)


# ---------------------------------------------------------------------------
# Per-tool extractors
# ---------------------------------------------------------------------------

async def _extract_create_npc(
    session: AsyncSession, session_id: str, args: dict, data: dict,
) -> None:
    """create_npc -> npc --located_at--> location."""
    location_name = data.get("location", "")
    if not location_name or location_name.lower() == "unknown":
        return
    npc_name = data.get("name", "")
    if not npc_name:
        return
    _, npc_id = await resolve_entity(session, session_id, "npc", npc_name)
    _, loc_id = await resolve_entity(session, session_id, "location", location_name)
    if npc_id and loc_id:
        await _upsert_edge(session, session_id, "npc", npc_id, "location", loc_id, "located_at", 80)


async def _extract_connect_locations(
    session: AsyncSession, session_id: str, args: dict, data: dict,
) -> None:
    """connect_locations -> bidirectional connected_to edges."""
    loc1_name = data.get("location1", "")
    loc2_name = data.get("location2", "")
    direction = data.get("direction", "")
    reverse = data.get("reverse_direction", "")
    if not loc1_name or not loc2_name:
        return
    _, loc1_id = await resolve_entity(session, session_id, "location", loc1_name)
    _, loc2_id = await resolve_entity(session, session_id, "location", loc2_name)
    if loc1_id and loc2_id:
        await _upsert_edge(
            session, session_id, "location", loc1_id, "location", loc2_id,
            "connected_to", 100, json.dumps({"direction": direction}),
        )
        await _upsert_edge(
            session, session_id, "location", loc2_id, "location", loc1_id,
            "connected_to", 100, json.dumps({"direction": reverse}),
        )


async def _extract_move_to(
    session: AsyncSession, session_id: str, args: dict, data: dict,
) -> None:
    """move_to -> char --located_at--> location (replaces old)."""
    char_name = data.get("moved_by", "")
    loc_name = data.get("name", "")
    if not char_name or not loc_name:
        return
    _, char_id = await resolve_entity(session, session_id, "character", char_name)
    _, loc_id = await resolve_entity(session, session_id, "location", loc_name)
    if char_id and loc_id:
        await _replace_located_at(session, session_id, "character", char_id, loc_id, 100)


async def _extract_give_item(
    session: AsyncSession, session_id: str, args: dict, data: dict,
) -> None:
    """give_item -> char --owns--> item. Extract from args (result is inventory type)."""
    char_name = args.get("character", "")
    item_name = args.get("item_name", "")
    if not char_name or not item_name:
        return
    char_type, char_id = await _auto_detect_type(session, session_id, char_name)
    _, item_id = await resolve_entity(session, session_id, "item", item_name)
    if char_id and item_id:
        await _upsert_edge(session, session_id, char_type, char_id, "item", item_id, "owns", 70)


async def _extract_equip_item(
    session: AsyncSession, session_id: str, args: dict, data: dict,
) -> None:
    """equip_item -> char --equipped--> item."""
    char_name = args.get("character", "")
    item_name = args.get("item_name", "")
    if not char_name or not item_name:
        return
    char_type, char_id = await _auto_detect_type(session, session_id, char_name)
    _, item_id = await resolve_entity(session, session_id, "item", item_name)
    if char_id and item_id:
        await _upsert_edge(session, session_id, char_type, char_id, "item", item_id, "equipped", 90)


async def _extract_unequip_item(
    session: AsyncSession, session_id: str, args: dict, data: dict,
) -> None:
    """unequip_item -> remove equipped, ensure owns."""
    char_name = args.get("character", "")
    item_name = args.get("item_name", "")
    if not char_name or not item_name:
        return
    char_type, char_id = await _auto_detect_type(session, session_id, char_name)
    _, item_id = await resolve_entity(session, session_id, "item", item_name)
    if char_id and item_id:
        await _remove_edge(session, session_id, char_type, char_id, "item", item_id, "equipped")
        await _upsert_edge(session, session_id, char_type, char_id, "item", item_id, "owns", 70)


async def _extract_transfer_item(
    session: AsyncSession, session_id: str, args: dict, data: dict,
) -> None:
    """transfer_item -> move owns/equipped edges from source to target."""
    # Result uses "from"/"to" keys
    from_name = data.get("from", "") or args.get("from_character", "")
    to_name = data.get("to", "") or args.get("to_character", "")
    item_name = data.get("item", "") or args.get("item_name", "")
    if not from_name or not to_name or not item_name:
        return
    from_type, from_id = await _auto_detect_type(session, session_id, from_name)
    to_type, to_id = await _auto_detect_type(session, session_id, to_name)
    _, item_id = await resolve_entity(session, session_id, "item", item_name)
    if from_id and to_id and item_id:
        await _remove_edge(session, session_id, from_type, from_id, "item", item_id, "owns")
        await _remove_edge(session, session_id, from_type, from_id, "item", item_id, "equipped")
        await _upsert_edge(session, session_id, to_type, to_id, "item", item_id, "owns", 70)


async def _extract_update_npc_relationship(
    session: AsyncSession, session_id: str, args: dict, data: dict,
) -> None:
    """update_npc_relationship -> npc --knows--> character."""
    npc_name = data.get("name", "") or args.get("npc_name", "")
    char_name = args.get("character", "")
    familiarity = data.get("familiarity", "")
    if not npc_name or not char_name:
        return
    _, npc_id = await resolve_entity(session, session_id, "npc", npc_name)
    _, char_id = await resolve_entity(session, session_id, "character", char_name)
    if npc_id and char_id:
        strength = _FAMILIARITY_STRENGTH.get(familiarity, 40)
        await _upsert_edge(session, session_id, "npc", npc_id, "character", char_id, "knows", strength)


async def _extract_complete_quest(
    session: AsyncSession, session_id: str, args: dict, data: dict,
) -> None:
    """complete_quest -> char --completed--> quest for each PC."""
    quest_title = data.get("title", "")
    distributed = data.get("distributed_to", [])
    if not quest_title or not distributed:
        return
    _, quest_id = await resolve_entity(session, session_id, "quest", quest_title)
    if not quest_id:
        return
    for entry in distributed:
        char_name = entry.get("name", "") if isinstance(entry, dict) else str(entry)
        if not char_name:
            continue
        _, char_id = await resolve_entity(session, session_id, "character", char_name)
        if char_id:
            await _upsert_edge(session, session_id, "character", char_id, "quest", quest_id, "completed", 100)


async def _extract_start_combat(
    session: AsyncSession, session_id: str, args: dict, data: dict,
) -> None:
    """start_combat -> pairwise fighting edges between all combatants."""
    order = data.get("order", [])
    if len(order) < 2:
        return
    # Resolve all combatants
    resolved: list[tuple[str, str]] = []
    for entry in order:
        name = entry.get("name", "") if isinstance(entry, dict) else str(entry)
        if not name:
            continue
        etype, eid = await _auto_detect_type(session, session_id, name)
        if eid:
            resolved.append((etype, eid))
    # Pairwise edges
    for i, (t1, id1) in enumerate(resolved):
        for t2, id2 in resolved[i + 1:]:
            await _upsert_edge(session, session_id, t1, id1, t2, id2, "fighting", 60)


async def _extract_attack(
    session: AsyncSession, session_id: str, args: dict, data: dict,
) -> None:
    """attack -> attacker --attacked--> target with damage-scaled strength."""
    attacker_name = data.get("attacker", "")
    target_name = data.get("target", "")
    damage = data.get("damage", 0) or 0
    if not attacker_name or not target_name:
        return
    at_type, at_id = await _auto_detect_type(session, session_id, attacker_name)
    tg_type, tg_id = await _auto_detect_type(session, session_id, target_name)
    if at_id and tg_id:
        strength = min(90, 40 + int(damage) * 3)
        await _upsert_edge(session, session_id, at_type, at_id, tg_type, tg_id, "attacked", strength)


async def _extract_create_character(
    session: AsyncSession, session_id: str, args: dict, data: dict,
) -> None:
    """create_character -> bidirectional party_member edges with existing PCs."""
    # Only for player characters
    is_player = args.get("is_player", True)
    if not is_player:
        return
    char_name = data.get("name", "")
    if not char_name:
        return
    _, new_id = await resolve_entity(session, session_id, "character", char_name)
    if not new_id:
        return
    # Find existing player characters in this session
    result = await session.execute(
        select(Character).where(
            Character.session_id == session_id,
            Character.is_player.is_(True),
            Character.id != new_id,
        )
    )
    existing_pcs = result.scalars().all()
    for pc in existing_pcs:
        await _upsert_edge(session, session_id, "character", new_id, "character", pc.id, "party_member", 100)
        await _upsert_edge(session, session_id, "character", pc.id, "character", new_id, "party_member", 100)


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_EXTRACTORS: dict[str, Extractor] = {
    "create_npc": _extract_create_npc,
    "connect_locations": _extract_connect_locations,
    "move_to": _extract_move_to,
    "give_item": _extract_give_item,
    "equip_item": _extract_equip_item,
    "unequip_item": _extract_unequip_item,
    "transfer_item": _extract_transfer_item,
    "update_npc_relationship": _extract_update_npc_relationship,
    "complete_quest": _extract_complete_quest,
    "start_combat": _extract_start_combat,
    "attack": _extract_attack,
    "create_character": _extract_create_character,
}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def extract_relationships(
    func_name: str,
    arguments: dict,
    result: str,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> None:
    """Post-hook: extract relationship edges from a tool execution result.

    Silent on all errors — never breaks tool execution.
    """
    if not settings.auto_extract_relationships:
        return

    extractor = _EXTRACTORS.get(func_name)
    if extractor is None:
        return

    try:
        data = json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return

    if data.get("error"):
        return

    try:
        gs = await get_or_create_session(session, conversation_id)
        session_id = gs.id
    except Exception:
        logger.debug("Failed to resolve session for relationship extraction", exc_info=True)
        return

    # Clean injected dependencies from arguments copy
    clean_args = {
        k: v for k, v in arguments.items()
        if k not in ("session", "conversation_id", "embedding_service", "llm_service")
    }

    try:
        await extractor(session, session_id, clean_args, data)
    except Exception:
        logger.warning("Relationship extraction failed for %s", func_name, exc_info=True)
