"""AgentContext — shared mutable state flowing through the agent pipeline.

Created once per user turn in ChatService.stream_chat(), passed to all agents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tool import Tool
from app.services.token_utils import TokenBudget

if TYPE_CHECKING:
    from app.services.base import BaseLLMService
    from app.services.prompt_builder import GamePhase
    from app.services.tool_service import ToolService


@dataclass
class AgentContext:
    # Per-turn identifiers
    session: AsyncSession
    conversation_id: str
    model: str
    user_message: str
    options: dict

    # Shared services
    llm_service: BaseLLMService
    tool_service: ToolService
    embedding_service: BaseLLMService | None

    # Token budget (shared across all agents — NOT split)
    budget: TokenBudget

    # Conversation state
    messages: list[dict] = field(default_factory=list)
    conv_tools: list[Tool] = field(default_factory=list)
    tool_map: dict[str, Tool] = field(default_factory=dict)
    phase: GamePhase | None = None

    # Pipeline outputs
    final_response: str | None = None
    actions: list[dict] = field(default_factory=list)
    current_agent: str = ""
    agent_outputs: dict[str, str] = field(default_factory=dict)
    agent_handoffs: dict[str, str] = field(default_factory=dict)
