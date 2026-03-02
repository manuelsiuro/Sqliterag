from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.exceptions import NotFoundError
from app.models.tool import ConversationTool, Tool
from app.schemas.tool import (
    ConversationToolToggle,
    ToolCreate,
    ToolRead,
    ToolUpdate,
)

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("", response_model=list[ToolRead])
async def list_tools(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Tool).order_by(Tool.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=ToolRead, status_code=201)
async def create_tool(data: ToolCreate, session: AsyncSession = Depends(get_session)):
    tool = Tool(
        name=data.name,
        description=data.description,
        parameters_schema=json.dumps(data.parameters_schema.model_dump()),
        execution_type=data.execution_type,
        execution_config=json.dumps(data.execution_config),
    )
    session.add(tool)
    await session.commit()
    await session.refresh(tool)
    return tool


@router.get("/{tool_id}", response_model=ToolRead)
async def get_tool(tool_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()
    if not tool:
        raise NotFoundError("Tool", tool_id)
    return tool


@router.patch("/{tool_id}", response_model=ToolRead)
async def update_tool(
    tool_id: str,
    data: ToolUpdate,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()
    if not tool:
        raise NotFoundError("Tool", tool_id)

    if data.name is not None:
        tool.name = data.name
    if data.description is not None:
        tool.description = data.description
    if data.parameters_schema is not None:
        tool.parameters_schema = json.dumps(data.parameters_schema.model_dump())
    if data.execution_type is not None:
        tool.execution_type = data.execution_type
    if data.execution_config is not None:
        tool.execution_config = json.dumps(data.execution_config)
    if data.is_enabled is not None:
        tool.is_enabled = data.is_enabled

    await session.commit()
    await session.refresh(tool)
    return tool


@router.delete("/{tool_id}", status_code=204)
async def delete_tool(tool_id: str, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Tool).where(Tool.id == tool_id))
    tool = result.scalar_one_or_none()
    if not tool:
        raise NotFoundError("Tool", tool_id)

    await session.delete(tool)
    await session.commit()


@router.get("/conversations/{conversation_id}", response_model=list[ToolRead])
async def get_conversation_tools(
    conversation_id: str,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Tool)
        .join(ConversationTool, ConversationTool.tool_id == Tool.id)
        .where(ConversationTool.conversation_id == conversation_id)
    )
    return result.scalars().all()


@router.put("/conversations/{conversation_id}")
async def set_conversation_tools(
    conversation_id: str,
    data: ConversationToolToggle,
    session: AsyncSession = Depends(get_session),
):
    # Remove existing
    await session.execute(
        delete(ConversationTool).where(
            ConversationTool.conversation_id == conversation_id
        )
    )

    # Add new
    for tool_id in data.tool_ids:
        session.add(ConversationTool(conversation_id=conversation_id, tool_id=tool_id))

    await session.commit()
    return {"status": "ok", "tool_ids": data.tool_ids}
