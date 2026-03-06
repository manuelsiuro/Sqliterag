"""Visualization REST endpoints — memories, graph, budget (Phase 5.6)."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies import get_chat_service
from app.models.rpg import GameMemory, GameSession, Relationship
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["visualization"])


async def _get_session_id(db: AsyncSession, conversation_id: str) -> str | None:
    result = await db.execute(
        select(GameSession.id).where(
            GameSession.conversation_id == conversation_id
        )
    )
    row = result.scalar_one_or_none()
    return row


@router.get("/conversations/{conversation_id}/rpg/memories")
async def get_memories(
    conversation_id: str,
    db: AsyncSession = Depends(get_session),
    type: str | None = Query(None),
    entity_type: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    session_id = await _get_session_id(db, conversation_id)
    if not session_id:
        return {"memories": [], "total": 0, "types_summary": {}}

    # Types summary
    summary_q = (
        select(GameMemory.memory_type, func.count())
        .where(GameMemory.session_id == session_id)
        .group_by(GameMemory.memory_type)
    )
    summary_result = await db.execute(summary_q)
    types_summary = {row[0]: row[1] for row in summary_result.all()}

    # Memories query
    q = select(GameMemory).where(GameMemory.session_id == session_id)
    count_q = select(func.count()).select_from(GameMemory).where(
        GameMemory.session_id == session_id
    )

    if type:
        q = q.where(GameMemory.memory_type == type)
        count_q = count_q.where(GameMemory.memory_type == type)
    if entity_type:
        q = q.where(GameMemory.entity_type == entity_type)
        count_q = count_q.where(GameMemory.entity_type == entity_type)

    total = (await db.execute(count_q)).scalar() or 0

    q = q.order_by(GameMemory.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(q)
    memories = result.scalars().all()

    return {
        "memories": [
            {
                "id": m.id,
                "memory_type": m.memory_type,
                "entity_type": m.entity_type,
                "content": m.content,
                "importance_score": m.importance_score,
                "entity_names": json.loads(m.entity_names) if m.entity_names else [],
                "session_number": m.session_number,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in memories
        ],
        "total": total,
        "types_summary": types_summary,
    }


@router.get("/conversations/{conversation_id}/rpg/graph")
async def get_graph(
    conversation_id: str,
    db: AsyncSession = Depends(get_session),
    min_strength: int = Query(0, ge=0, le=100),
):
    session_id = await _get_session_id(db, conversation_id)
    if not session_id:
        return {"nodes": [], "edges": []}

    q = select(Relationship).where(Relationship.session_id == session_id)
    if min_strength > 0:
        q = q.where(Relationship.strength >= min_strength)
    result = await db.execute(q)
    rels = result.scalars().all()

    # Collect unique entities as nodes
    entity_set: set[tuple[str, str]] = set()
    edges = []
    for r in rels:
        entity_set.add((r.source_type, r.source_id))
        entity_set.add((r.target_type, r.target_id))
        edges.append({
            "source_id": f"{r.source_type}:{r.source_id}",
            "target_id": f"{r.target_type}:{r.target_id}",
            "relationship": r.relationship,
            "strength": r.strength,
            "source_type": r.source_type,
            "target_type": r.target_type,
        })

    # Resolve entity names
    from app.services.rpg_service import resolve_entity_name
    nodes = []
    for etype, eid in entity_set:
        name = await resolve_entity_name(db, etype, eid)
        nodes.append({
            "id": f"{etype}:{eid}",
            "name": name or f"unknown-{eid[:8]}",
            "type": etype,
            "entity_id": eid,
        })

    return {"nodes": nodes, "edges": edges}


@router.get("/conversations/{conversation_id}/rpg/budget")
async def get_budget(
    conversation_id: str,
    chat_service: ChatService = Depends(get_chat_service),
):
    return chat_service.get_cached_budget(conversation_id)
