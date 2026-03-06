"""AgentOrchestrator — sequential pipeline coordinator for multi-agent execution."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator

from sse_starlette.sse import ServerSentEvent

from app.services.agent_base import BaseAgent
from app.services.agent_context import AgentContext

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Runs agents sequentially, injecting agent attribution into SSE events."""

    def __init__(self, agents: list[BaseAgent]):
        self.agents = agents

    async def run_pipeline(
        self, ctx: AgentContext,
    ) -> AsyncGenerator[ServerSentEvent, None]:
        for i, agent in enumerate(self.agents):
            ctx.current_agent = agent.name

            yield ServerSentEvent(
                data=json.dumps({"agent": agent.name, "index": i}),
                event="agent_start",
            )

            async for event in agent.run(ctx):
                try:
                    event_data = json.loads(event.data) if event.data else {}
                    event_data["agent"] = agent.name
                    yield ServerSentEvent(
                        data=json.dumps(event_data),
                        event=event.event,
                    )
                except (json.JSONDecodeError, TypeError):
                    yield event
