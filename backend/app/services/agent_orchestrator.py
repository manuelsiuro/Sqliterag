"""AgentOrchestrator — sequential pipeline coordinator for multi-agent execution."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator

from sse_starlette.sse import ServerSentEvent

from app.services.agent_base import BaseAgent
from app.services.agent_context import AgentContext
from app.services.token_utils import estimate_tokens

logger = logging.getLogger(__name__)


def _replace_system_prompt(ctx: AgentContext, new_prompt: str) -> None:
    """Replace the RPG system prompt in ctx.messages with the agent's prompt.

    The RPG system prompt starts with '/nothink'.  We find the first matching
    system message and swap its content, adjusting the token budget delta.
    """
    for msg in ctx.messages:
        if msg.get("role") == "system" and msg.get("content", "").startswith("/nothink"):
            old_tokens = estimate_tokens(msg["content"])
            msg["content"] = new_prompt
            new_tokens = estimate_tokens(new_prompt)
            ctx.budget.system_prompt_tokens += new_tokens - old_tokens
            return

    # Fallback: no existing system prompt found — insert at position 0
    ctx.messages.insert(0, {"role": "system", "content": new_prompt})
    ctx.budget.system_prompt_tokens = estimate_tokens(new_prompt)


class AgentOrchestrator:
    """Runs agents sequentially, injecting agent attribution into SSE events."""

    def __init__(self, agents: list[BaseAgent]):
        self.agents = agents

    async def run_pipeline(
        self, ctx: AgentContext,
    ) -> AsyncGenerator[ServerSentEvent, None]:
        active_agents = [(i, a) for i, a in enumerate(self.agents) if a.should_run(ctx)]
        if not active_agents:
            return

        for seq, (i, agent) in enumerate(active_agents):
            is_last = seq == len(active_agents) - 1
            ctx.current_agent = agent.name

            # Phase 4.2: Apply agent-specific system prompt
            new_prompt = None
            if hasattr(agent, "build_system_prompt_async"):
                new_prompt = await agent.build_system_prompt_async(ctx)
            if new_prompt is None:
                new_prompt = agent.build_system_prompt(ctx)
            if new_prompt is not None:
                _replace_system_prompt(ctx, new_prompt)

            yield ServerSentEvent(
                data=json.dumps({"agent": agent.name, "index": i}),
                event="agent_start",
            )

            agent_text = ""
            async for event in agent.run(ctx):
                try:
                    event_data = json.loads(event.data) if event.data else {}
                    event_data["agent"] = agent.name

                    if event.event == "token" and "token" in event_data:
                        agent_text += event_data["token"]

                    # Suppress token/done from non-final agents
                    if not is_last and event.event in ("token", "done"):
                        if event.event == "done":
                            yield ServerSentEvent(
                                data=json.dumps(event_data),
                                event="agent_done",
                            )
                        continue

                    yield ServerSentEvent(
                        data=json.dumps(event_data),
                        event=event.event,
                    )
                except (json.JSONDecodeError, TypeError):
                    yield event

            if agent_text:
                ctx.agent_outputs[agent.name] = agent_text
