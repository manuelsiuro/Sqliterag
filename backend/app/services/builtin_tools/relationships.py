"""Knowledge graph relationship tools (Phase 3.1 + 3.5 CTE traversal)."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import text

from app.services.builtin_tools._common import (
    AsyncSession,
    character_to_dict,
    get_character_by_name,
    get_location_by_name,
    get_npc_by_name,
    get_or_create_session,
    get_quest_by_title,
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


async def _resolve_names_batch(
    session: AsyncSession,
    entity_pairs: set[tuple[str, str]],
) -> dict[tuple[str, str], str]:
    """Resolve multiple entity IDs to display names in batch."""
    result: dict[tuple[str, str], str] = {}
    for etype, eid in entity_pairs:
        name = await resolve_entity_name(session, etype, eid)
        result[(etype, eid)] = name or f"unknown-{eid[:8]}"
    return result


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
    """Query the relationship graph for an entity using recursive CTE."""
    from app.config import settings

    gs = await get_or_create_session(session, conversation_id)

    depth = max(1, min(settings.graph_max_traversal_depth, depth))

    # Resolve entity
    if entity_type and entity_type.strip():
        entity_type = entity_type.lower().strip()
        _, entity_id = await resolve_entity(session, gs.id, entity_type, entity_name)
    else:
        entity_type, entity_id = await _auto_detect_entity(session, gs.id, entity_name)

    if not entity_id:
        return json.dumps({"type": "relationship_graph", "error": f"Entity '{entity_name}' not found."})

    root_key = f"{entity_type}:{entity_id}"
    rel_filter = _normalize_relationship(relationship_filter) if relationship_filter else ""

    # Build CTE — relationship_filter only applies to base cases
    base_out_filter = "\n      AND r.relationship = :rel_filter" if rel_filter else ""
    base_in_filter = "\n      AND r.relationship = :rel_filter" if rel_filter else ""

    cte_sql = f"""
    WITH RECURSIVE graph(
        entity_type, entity_id, depth,
        path,
        edge_src_type, edge_src_id,
        edge_tgt_type, edge_tgt_id,
        rel, strength, direction
    ) AS (
        -- Base: outgoing from root
        SELECT r.target_type, r.target_id, 1,
               :root_key || '|' || r.target_type || ':' || r.target_id,
               r.source_type, r.source_id,
               r.target_type, r.target_id,
               r.relationship, r.strength, 'outgoing'
        FROM rpg_relationships r
        WHERE r.session_id = :sid
          AND r.source_type = :rt AND r.source_id = :ri{base_out_filter}
        UNION ALL
        -- Base: incoming to root
        SELECT r.source_type, r.source_id, 1,
               :root_key || '|' || r.source_type || ':' || r.source_id,
               r.source_type, r.source_id,
               r.target_type, r.target_id,
               r.relationship, r.strength, 'incoming'
        FROM rpg_relationships r
        WHERE r.session_id = :sid
          AND r.target_type = :rt AND r.target_id = :ri{base_in_filter}
        UNION ALL
        -- Recursive: outgoing from discovered nodes
        SELECT r.target_type, r.target_id, g.depth + 1,
               g.path || '|' || r.target_type || ':' || r.target_id,
               r.source_type, r.source_id,
               r.target_type, r.target_id,
               r.relationship, r.strength, 'outgoing'
        FROM rpg_relationships r
        JOIN graph g ON r.source_type = g.entity_type AND r.source_id = g.entity_id
        WHERE r.session_id = :sid AND g.depth < :max_depth
          AND g.path NOT LIKE '%' || r.target_type || ':' || r.target_id || '%'
        UNION ALL
        -- Recursive: incoming to discovered nodes
        SELECT r.source_type, r.source_id, g.depth + 1,
               g.path || '|' || r.source_type || ':' || r.source_id,
               r.source_type, r.source_id,
               r.target_type, r.target_id,
               r.relationship, r.strength, 'incoming'
        FROM rpg_relationships r
        JOIN graph g ON r.target_type = g.entity_type AND r.target_id = g.entity_id
        WHERE r.session_id = :sid AND g.depth < :max_depth
          AND g.path NOT LIKE '%' || r.source_type || ':' || r.source_id || '%'
    )
    SELECT DISTINCT
        edge_src_type, edge_src_id, edge_tgt_type, edge_tgt_id,
        rel, strength, depth, direction
    FROM graph
    ORDER BY depth, strength DESC
    """

    params: dict = {
        "root_key": root_key,
        "sid": gs.id,
        "rt": entity_type,
        "ri": entity_id,
        "max_depth": depth,
    }
    if rel_filter:
        params["rel_filter"] = rel_filter

    result = await session.execute(text(cte_sql), params)
    rows = result.fetchall()

    # Collect all entity IDs for batch name resolution
    entity_pairs: set[tuple[str, str]] = set()
    for row in rows:
        entity_pairs.add((row[0], row[1]))  # edge_src_type, edge_src_id
        entity_pairs.add((row[2], row[3]))  # edge_tgt_type, edge_tgt_id

    names = await _resolve_names_batch(session, entity_pairs)

    # Build edge list
    seen_edges: set[str] = set()
    edges: list[dict] = []
    for row in rows:
        edge_key = f"{row[0]}:{row[1]}-{row[4]}-{row[2]}:{row[3]}"
        if edge_key in seen_edges:
            continue
        seen_edges.add(edge_key)
        edges.append({
            "source_name": names[(row[0], row[1])],
            "source_type": row[0],
            "target_name": names[(row[2], row[3])],
            "target_type": row[2],
            "relationship": row[4],
            "strength": row[5],
            "direction": row[7],
            "depth": row[6],
        })

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


async def get_entity_context(
    entity_name: str,
    entity_type: str = "",
    *,
    session: AsyncSession,
    conversation_id: str,
    embedding_service=None,
) -> str:
    """Compile a comprehensive context dossier for any game entity."""
    from app.models.rpg import GameMemory, Item

    gs = await get_or_create_session(session, conversation_id)

    # --- 1. Resolve entity ---
    if entity_type and entity_type.strip():
        entity_type = entity_type.lower().strip()
        _, entity_id = await resolve_entity(session, gs.id, entity_type, entity_name)
    else:
        entity_type, entity_id = await _auto_detect_entity(session, gs.id, entity_name)

    if not entity_id:
        return json.dumps({"type": "entity_context", "error": f"Entity '{entity_name}' not found."})

    # --- 2. Fetch entity details ---
    details: dict = {}
    display_name = entity_name

    if entity_type == "character":
        char = await get_character_by_name(session, gs.id, entity_name)
        if char:
            d = character_to_dict(char)
            display_name = d.get("name", entity_name)
            details = {
                "name": d.get("name"), "race": d.get("race"), "class": d.get("class"),
                "level": d.get("level"), "hp": f"{d.get('current_hp')}/{d.get('max_hp')}",
                "ac": d.get("armor_class"),
                "abilities": {
                    k: d.get(k) for k in ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
                },
                "conditions": d.get("conditions", []),
            }

    elif entity_type == "npc":
        npc = await get_npc_by_name(session, gs.id, entity_name)
        if npc:
            display_name = npc.name
            loc_name = None
            if npc.location_id:
                loc_name = await resolve_entity_name(session, "location", npc.location_id)
            memory = []
            if npc.memory:
                try:
                    memory = json.loads(npc.memory)
                except (json.JSONDecodeError, TypeError):
                    memory = []
            details = {
                "name": npc.name, "description": npc.description,
                "disposition": npc.disposition, "familiarity": npc.familiarity,
                "location": loc_name, "memory": memory,
            }

    elif entity_type == "location":
        loc = await get_location_by_name(session, gs.id, entity_name)
        if loc:
            display_name = loc.name
            exits_raw = json.loads(loc.exits) if loc.exits else {}
            exits = {}
            for direction, lid in exits_raw.items():
                exits[direction] = await resolve_entity_name(session, "location", lid)
            env = json.loads(loc.environment) if loc.environment else {}
            details = {
                "name": loc.name, "description": loc.description,
                "biome": loc.biome, "exits": exits, "environment": env,
            }

    elif entity_type == "quest":
        quest = await get_quest_by_title(session, gs.id, entity_name)
        if quest:
            display_name = quest.title
            objectives = []
            if quest.objectives:
                try:
                    objectives = json.loads(quest.objectives)
                except (json.JSONDecodeError, TypeError):
                    objectives = []
            rewards = {}
            if quest.rewards:
                try:
                    rewards = json.loads(quest.rewards)
                except (json.JSONDecodeError, TypeError):
                    rewards = {}
            details = {
                "name": quest.title, "description": quest.description,
                "status": quest.status, "objectives": objectives, "rewards": rewards,
            }

    elif entity_type == "item":
        result = await session.execute(
            select(Item).where(Item.name.ilike(entity_name))
        )
        item = result.scalars().first()
        if item:
            display_name = item.name
            props = {}
            if item.properties:
                try:
                    props = json.loads(item.properties)
                except (json.JSONDecodeError, TypeError):
                    props = {}
            details = {
                "name": item.name, "item_type": item.item_type,
                "description": item.description, "weight": item.weight,
                "value_gp": item.value_gp, "rarity": item.rarity, "properties": props,
            }

    # --- 3. Fetch relationships (reuse query_relationships) ---
    rels_json = await query_relationships(
        entity_name=entity_name,
        entity_type=entity_type,
        relationship_filter="",
        depth=1,
        session=session,
        conversation_id=conversation_id,
    )
    rels_data = json.loads(rels_json)
    relationships = rels_data.get("relationships", [])

    # --- 4. Search memories ---
    memories: list[dict] = []
    try:
        from app.services.memory_service import search_with_stanford_scoring

        results = await search_with_stanford_scoring(
            session,
            entity_name,
            embedding_service=embedding_service,
            session_id=gs.id,
            top_k=5,
        )
        if results:
            # results is list[(memory_id, score)] — fetch full records
            mem_ids = [mid for mid, _ in results]
            mem_result = await session.execute(
                select(GameMemory).where(GameMemory.id.in_(mem_ids))
            )
            mem_map = {m.id: m for m in mem_result.scalars().all()}
            for mid, score in results:
                m = mem_map.get(mid)
                if m:
                    entities = []
                    if m.entity_names:
                        try:
                            entities = json.loads(m.entity_names)
                        except (json.JSONDecodeError, TypeError):
                            entities = []
                    memories.append({
                        "content": m.content,
                        "memory_type": m.memory_type,
                        "importance": round(m.importance_score * 10),
                        "entities": entities,
                        "created_at": m.created_at.isoformat() if m.created_at else None,
                    })
    except Exception:
        pass  # memories section empty on failure

    # --- 5. Build compact summary ---
    summary_parts = [f"{display_name} ({entity_type}"]
    if entity_type == "character" and details.get("class"):
        summary_parts[0] += f", L{details.get('level')} {details.get('class')}"
    elif entity_type == "npc" and details.get("disposition"):
        summary_parts[0] += f", {details.get('disposition')}"
    elif entity_type == "location" and details.get("biome"):
        summary_parts[0] += f", {details.get('biome')}"
    elif entity_type == "quest" and details.get("status"):
        summary_parts[0] += f", {details.get('status')}"
    elif entity_type == "item" and details.get("rarity"):
        summary_parts[0] += f", {details.get('rarity')}"
    summary_parts[0] += ")"

    if relationships:
        rel_strs = []
        for r in relationships[:3]:
            other = r["target_name"] if r["direction"] == "outgoing" else r["source_name"]
            rel_strs.append(f"{r['relationship'].replace('_', ' ')} {other} ({r['strength']})")
        summary_parts.append("Relations: " + ", ".join(rel_strs))

    if memories:
        summary_parts.append(f"Memories: {memories[0]['content'][:60]}")

    summary = ". ".join(summary_parts) + "."

    return json.dumps({
        "type": "entity_context",
        "entity": {"name": display_name, "type": entity_type},
        "details": details,
        "relationships": relationships,
        "relationship_count": len(relationships),
        "memories": memories,
        "memory_count": len(memories),
        "summary": summary,
    })


async def find_connections(
    entity_name: str,
    target_name: str = "",
    entity_type: str = "",
    target_type: str = "",
    max_depth: int = 3,
    relationship_filter: str = "",
    *,
    session: AsyncSession,
    conversation_id: str,
) -> str:
    """Find connections between entities or discover all reachable entities."""
    from app.config import settings

    gs = await get_or_create_session(session, conversation_id)
    max_depth = max(1, min(settings.graph_max_traversal_depth, max_depth))

    # Resolve source entity
    if entity_type and entity_type.strip():
        entity_type = entity_type.lower().strip()
        _, entity_id = await resolve_entity(session, gs.id, entity_type, entity_name)
    else:
        entity_type, entity_id = await _auto_detect_entity(session, gs.id, entity_name)

    if not entity_id:
        err_type = "connection_paths" if target_name else "connection_map"
        return json.dumps({"type": err_type, "error": f"Entity '{entity_name}' not found."})

    root_key = f"{entity_type}:{entity_id}"
    rel_filter = _normalize_relationship(relationship_filter) if relationship_filter else ""
    base_filter = "\n      AND r.relationship = :rel_filter" if rel_filter else ""

    # --- Mode 1: Two-entity path finding ---
    if target_name and target_name.strip():
        if target_type and target_type.strip():
            target_type = target_type.lower().strip()
            _, target_id = await resolve_entity(session, gs.id, target_type, target_name)
        else:
            target_type, target_id = await _auto_detect_entity(session, gs.id, target_name)

        if not target_id:
            return json.dumps({"type": "connection_paths", "error": f"Target entity '{target_name}' not found."})

        path_sql = f"""
        WITH RECURSIVE paths(
            entity_type, entity_id, depth, path, rels
        ) AS (
            -- Base outgoing
            SELECT r.target_type, r.target_id, 1,
                   :root_key || '|' || r.target_type || ':' || r.target_id,
                   r.relationship
            FROM rpg_relationships r
            WHERE r.session_id = :sid
              AND r.source_type = :rt AND r.source_id = :ri{base_filter}
            UNION ALL
            -- Base incoming
            SELECT r.source_type, r.source_id, 1,
                   :root_key || '|' || r.source_type || ':' || r.source_id,
                   r.relationship
            FROM rpg_relationships r
            WHERE r.session_id = :sid
              AND r.target_type = :rt AND r.target_id = :ri{base_filter}
            UNION ALL
            -- Recursive outgoing
            SELECT r.target_type, r.target_id, p.depth + 1,
                   p.path || '|' || r.target_type || ':' || r.target_id,
                   p.rels || '|' || r.relationship
            FROM rpg_relationships r
            JOIN paths p ON r.source_type = p.entity_type AND r.source_id = p.entity_id
            WHERE r.session_id = :sid AND p.depth < :max_depth
              AND p.path NOT LIKE '%' || r.target_type || ':' || r.target_id || '%'
            UNION ALL
            -- Recursive incoming
            SELECT r.source_type, r.source_id, p.depth + 1,
                   p.path || '|' || r.source_type || ':' || r.source_id,
                   p.rels || '|' || r.relationship
            FROM rpg_relationships r
            JOIN paths p ON r.target_type = p.entity_type AND r.target_id = p.entity_id
            WHERE r.session_id = :sid AND p.depth < :max_depth
              AND p.path NOT LIKE '%' || r.source_type || ':' || r.source_id || '%'
        )
        SELECT path, rels, depth FROM paths
        WHERE entity_type = :tt AND entity_id = :ti
        ORDER BY depth LIMIT 10
        """

        params: dict = {
            "root_key": root_key, "sid": gs.id,
            "rt": entity_type, "ri": entity_id,
            "tt": target_type, "ti": target_id,
            "max_depth": max_depth,
        }
        if rel_filter:
            params["rel_filter"] = rel_filter

        result = await session.execute(text(path_sql), params)
        rows = result.fetchall()

        # Collect all entity IDs from paths for batch resolution
        entity_pairs: set[tuple[str, str]] = set()
        for row in rows:
            for segment in row[0].split("|"):
                if ":" in segment:
                    parts = segment.split(":", 1)
                    entity_pairs.add((parts[0], parts[1]))

        names = await _resolve_names_batch(session, entity_pairs)

        paths = []
        for row in rows:
            segments = row[0].split("|")
            nodes = []
            for seg in segments:
                if ":" in seg:
                    parts = seg.split(":", 1)
                    n = names.get((parts[0], parts[1]), parts[1][:8])
                    nodes.append({"name": n, "type": parts[0]})
            rels_list = row[1].split("|")
            paths.append({
                "hops": row[2],
                "nodes": nodes,
                "relationships": rels_list,
            })

        src_name = names.get((entity_type, entity_id), entity_name)
        tgt_name = names.get((target_type, target_id), target_name)

        return json.dumps({
            "type": "connection_paths",
            "source": {"name": src_name, "type": entity_type},
            "target": {"name": tgt_name, "type": target_type},
            "paths": paths,
            "path_count": len(paths),
            "max_depth": max_depth,
        })

    # --- Mode 2: Single-entity discovery ---
    map_sql = f"""
    WITH RECURSIVE paths(
        entity_type, entity_id, depth, path, rels
    ) AS (
        -- Base outgoing
        SELECT r.target_type, r.target_id, 1,
               :root_key || '|' || r.target_type || ':' || r.target_id,
               r.relationship
        FROM rpg_relationships r
        WHERE r.session_id = :sid
          AND r.source_type = :rt AND r.source_id = :ri{base_filter}
        UNION ALL
        -- Base incoming
        SELECT r.source_type, r.source_id, 1,
               :root_key || '|' || r.source_type || ':' || r.source_id,
               r.relationship
        FROM rpg_relationships r
        WHERE r.session_id = :sid
          AND r.target_type = :rt AND r.target_id = :ri{base_filter}
        UNION ALL
        -- Recursive outgoing
        SELECT r.target_type, r.target_id, p.depth + 1,
               p.path || '|' || r.target_type || ':' || r.target_id,
               p.rels || '|' || r.relationship
        FROM rpg_relationships r
        JOIN paths p ON r.source_type = p.entity_type AND r.source_id = p.entity_id
        WHERE r.session_id = :sid AND p.depth < :max_depth
          AND p.path NOT LIKE '%' || r.target_type || ':' || r.target_id || '%'
        UNION ALL
        -- Recursive incoming
        SELECT r.source_type, r.source_id, p.depth + 1,
               p.path || '|' || r.source_type || ':' || r.source_id,
               p.rels || '|' || r.relationship
        FROM rpg_relationships r
        JOIN paths p ON r.target_type = p.entity_type AND r.target_id = p.entity_id
        WHERE r.session_id = :sid AND p.depth < :max_depth
          AND p.path NOT LIKE '%' || r.source_type || ':' || r.source_id || '%'
    )
    SELECT entity_type, entity_id, MIN(depth) as min_depth,
           -- Pick the rels string from the shortest path
           MIN(rels) as via_rels
    FROM paths
    GROUP BY entity_type, entity_id
    ORDER BY min_depth, MIN(LENGTH(path))
    """

    params = {
        "root_key": root_key, "sid": gs.id,
        "rt": entity_type, "ri": entity_id,
        "max_depth": max_depth,
    }
    if rel_filter:
        params["rel_filter"] = rel_filter

    result = await session.execute(text(map_sql), params)
    rows = result.fetchall()

    entity_pairs: set[tuple[str, str]] = set()
    for row in rows:
        entity_pairs.add((row[0], row[1]))

    names = await _resolve_names_batch(session, entity_pairs)

    connected: list[dict] = []
    for row in rows:
        rels_list = row[3].split("|")
        via = " > ".join(r.replace("_", " ") for r in rels_list)
        connected.append({
            "name": names.get((row[0], row[1]), row[1][:8]),
            "type": row[0],
            "depth": row[2],
            "via": via,
        })

    src_name = await resolve_entity_name(session, entity_type, entity_id)

    return json.dumps({
        "type": "connection_map",
        "entity": {"name": src_name or entity_name, "type": entity_type},
        "connected_entities": connected,
        "count": len(connected),
        "max_depth": max_depth,
    })
