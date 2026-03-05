"""Knowledge graph relationship tools (Phase 3.1)."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from app.services.builtin_tools._common import (
    AsyncSession,
    get_or_create_session,
    json,
    resolve_entity,
    resolve_entity_name,
    select,
)

_ENTITY_TYPES = {"character", "npc", "location", "quest", "item"}

_ENTITY_SEARCH_ORDER = ["character", "npc", "location", "quest", "item"]


def _normalize_relationship(rel: str) -> str:
    """Normalize relationship string to lowercase with underscores."""
    return re.sub(r"[^a-z0-9]+", "_", rel.strip().lower()).strip("_")


async def _auto_detect_entity(
    session: AsyncSession,
    session_id: str,
    name: str,
) -> tuple[str, str | None]:
    """Try each entity type in order until we find a match."""
    for etype in _ENTITY_SEARCH_ORDER:
        etype, eid = await resolve_entity(session, session_id, etype, name)
        if eid:
            return (etype, eid)
    return ("unknown", None)


async def add_relationship(
    source_name: str,
    source_type: str,
    target_name: str,
    target_type: str,
    relationship: str,
    strength: int = 50,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Create or update a relationship between two game entities."""
    from app.models.rpg import Relationship

    gs = await get_or_create_session(session, conversation_id)

    source_type = source_type.lower().strip()
    target_type = target_type.lower().strip()

    if source_type not in _ENTITY_TYPES:
        return json.dumps({"type": "relationship_added", "error": f"Invalid source_type '{source_type}'. Must be one of: {', '.join(sorted(_ENTITY_TYPES))}"})
    if target_type not in _ENTITY_TYPES:
        return json.dumps({"type": "relationship_added", "error": f"Invalid target_type '{target_type}'. Must be one of: {', '.join(sorted(_ENTITY_TYPES))}"})

    relationship = _normalize_relationship(relationship)
    if not relationship:
        return json.dumps({"type": "relationship_added", "error": "Relationship type is required."})

    strength = max(0, min(100, strength))

    # Resolve entities
    _, source_id = await resolve_entity(session, gs.id, source_type, source_name)
    if not source_id:
        return json.dumps({"type": "relationship_added", "error": f"{source_type.title()} '{source_name}' not found."})

    _, target_id = await resolve_entity(session, gs.id, target_type, target_name)
    if not target_id:
        return json.dumps({"type": "relationship_added", "error": f"{target_type.title()} '{target_name}' not found."})

    # Check for existing edge
    result = await session.execute(
        select(Relationship).where(
            Relationship.session_id == gs.id,
            Relationship.source_type == source_type,
            Relationship.source_id == source_id,
            Relationship.target_type == target_type,
            Relationship.target_id == target_id,
            Relationship.relationship == relationship,
        )
    )
    existing = result.scalars().first()

    if existing:
        existing.strength = strength
        existing.updated_at = datetime.now(timezone.utc)
        await session.flush()
        return json.dumps({
            "type": "relationship_added",
            "source": {"name": source_name, "type": source_type},
            "target": {"name": target_name, "type": target_type},
            "relationship": relationship,
            "strength": strength,
            "is_update": True,
        })

    rel = Relationship(
        session_id=gs.id,
        source_type=source_type,
        source_id=source_id,
        target_type=target_type,
        target_id=target_id,
        relationship=relationship,
        strength=strength,
    )
    session.add(rel)
    await session.flush()

    return json.dumps({
        "type": "relationship_added",
        "source": {"name": source_name, "type": source_type},
        "target": {"name": target_name, "type": target_type},
        "relationship": relationship,
        "strength": strength,
        "is_update": False,
    })


async def query_relationships(
    entity_name: str,
    entity_type: str = "",
    relationship_filter: str = "",
    depth: int = 1,
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Query the relationship graph for an entity."""
    from app.models.rpg import Relationship

    gs = await get_or_create_session(session, conversation_id)

    depth = max(1, min(2, depth))

    # Resolve entity
    if entity_type and entity_type.strip():
        entity_type = entity_type.lower().strip()
        _, entity_id = await resolve_entity(session, gs.id, entity_type, entity_name)
    else:
        entity_type, entity_id = await _auto_detect_entity(session, gs.id, entity_name)

    if not entity_id:
        return json.dumps({"type": "relationship_graph", "error": f"Entity '{entity_name}' not found."})

    # Depth-1: direct connections
    edges = []
    visited_edges: set[str] = set()

    async def _fetch_edges(etype: str, eid: str) -> list[dict]:
        """Fetch all edges where entity is source or target."""
        results = []

        # As source
        q = select(Relationship).where(
            Relationship.session_id == gs.id,
            Relationship.source_type == etype,
            Relationship.source_id == eid,
        )
        if relationship_filter:
            q = q.where(Relationship.relationship == _normalize_relationship(relationship_filter))
        rows = (await session.execute(q)).scalars().all()
        for r in rows:
            edge_key = f"{r.source_type}:{r.source_id}-{r.relationship}-{r.target_type}:{r.target_id}"
            if edge_key not in visited_edges:
                visited_edges.add(edge_key)
                target_name = await resolve_entity_name(session, r.target_type, r.target_id)
                results.append({
                    "source_name": entity_name if (r.source_type == etype and r.source_id == eid) else await resolve_entity_name(session, r.source_type, r.source_id),
                    "source_type": r.source_type,
                    "target_name": target_name,
                    "target_type": r.target_type,
                    "relationship": r.relationship,
                    "strength": r.strength,
                    "direction": "outgoing",
                })

        # As target
        q = select(Relationship).where(
            Relationship.session_id == gs.id,
            Relationship.target_type == etype,
            Relationship.target_id == eid,
        )
        if relationship_filter:
            q = q.where(Relationship.relationship == _normalize_relationship(relationship_filter))
        rows = (await session.execute(q)).scalars().all()
        for r in rows:
            edge_key = f"{r.source_type}:{r.source_id}-{r.relationship}-{r.target_type}:{r.target_id}"
            if edge_key not in visited_edges:
                visited_edges.add(edge_key)
                source_name = await resolve_entity_name(session, r.source_type, r.source_id)
                results.append({
                    "source_name": source_name,
                    "source_type": r.source_type,
                    "target_name": entity_name if (r.target_type == etype and r.target_id == eid) else await resolve_entity_name(session, r.target_type, r.target_id),
                    "target_type": r.target_type,
                    "relationship": r.relationship,
                    "strength": r.strength,
                    "direction": "incoming",
                })

        return results

    # Depth 1
    edges = await _fetch_edges(entity_type, entity_id)

    # Depth 2: traverse neighbors
    if depth >= 2:
        neighbor_ids: list[tuple[str, str]] = []
        for e in edges:
            if e["direction"] == "outgoing":
                neighbor_ids.append((e["target_type"], e["target_name"]))
            else:
                neighbor_ids.append((e["source_type"], e["source_name"]))

        for n_type, n_name in neighbor_ids:
            _, n_id = await resolve_entity(session, gs.id, n_type, n_name)
            if n_id and (n_type, n_id) != (entity_type, entity_id):
                hop2 = await _fetch_edges(n_type, n_id)
                edges.extend(hop2)

    return json.dumps({
        "type": "relationship_graph",
        "entity": {"name": entity_name, "type": entity_type},
        "relationships": edges,
        "depth": depth,
        "count": len(edges),
    })


async def get_entity_relationships(
    entity_name: str,
    entity_type: str = "",
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Get a compact summary of an entity's direct relationships."""
    return await query_relationships(
        entity_name=entity_name,
        entity_type=entity_type,
        relationship_filter="",
        depth=1,
        session=session,
        conversation_id=conversation_id,
    )
