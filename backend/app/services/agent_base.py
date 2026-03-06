"""BaseAgent ABC and SingleAgent — extracted from chat_service.py agent loop."""

from __future__ import annotations

import abc
import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from sse_starlette.sse import ServerSentEvent

from app.config import settings
from app.models.message import Message
from app.services.agent_context import AgentContext
from app.services.eviction_service import evict_and_store
from app.services.prompt_builder import filter_tools_by_phase
from app.services.token_utils import (
    apply_history_summarization,
    estimate_message_tokens,
    estimate_tool_definitions_tokens,
    truncate_history,
)
from app.services.tool_validation import validate_tool_call

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 10
TOKEN_CHUNK_SIZE = 4


class BaseAgent(abc.ABC):
    """Abstract base for all agents in the pipeline."""

    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @property
    @abc.abstractmethod
    def allowed_tool_names(self) -> frozenset[str] | None:
        """Tool names this agent may use, or None for all tools."""
        ...

    @abc.abstractmethod
    def build_system_prompt(self, ctx: AgentContext) -> str | None:
        """Build agent-specific system prompt. Return None to use existing."""
        ...

    @property
    def is_user_facing(self) -> bool:
        """Whether this agent's text output should stream to the user."""
        return True

    def should_run(self, ctx: AgentContext) -> bool:
        """Whether this agent should run for the current context. Default: True."""
        return True

    @abc.abstractmethod
    async def run(self, ctx: AgentContext) -> AsyncGenerator[ServerSentEvent, None]:
        """Execute agent logic, yield SSE events."""
        ...


class SingleAgent(BaseAgent):
    """Wraps the original chat_service agent loop verbatim.

    This is a mechanical extraction — every `self.X` became `ctx.X`.
    """

    @property
    def name(self) -> str:
        return "default"

    @property
    def allowed_tool_names(self) -> frozenset[str] | None:
        return None  # All tools

    def build_system_prompt(self, ctx: AgentContext) -> str | None:
        return None  # System prompt already in ctx.messages

    async def run(self, ctx: AgentContext) -> AsyncGenerator[ServerSentEvent, None]:
        # Import here to avoid circular import
        from app.services.chat_service import _extract_suggestions

        # Phase 1.4: Filter tools by game phase
        if ctx.phase is not None and settings.tool_injection_enabled:
            llm_tools = filter_tools_by_phase(ctx.conv_tools, ctx.phase)
            logger.info(
                "Tool injection: phase=%s, %d/%d tools",
                ctx.phase.value, len(llm_tools), len(ctx.conv_tools),
            )
        else:
            llm_tools = ctx.conv_tools

        # Agent-level tool narrowing (Phase 4.3)
        if self.allowed_tool_names is not None:
            llm_tools = [t for t in llm_tools if t.name in self.allowed_tool_names]
            logger.info(
                "Agent '%s' tool filter: %d tools after agent narrowing",
                self.name, len(llm_tools),
            )

        ollama_tools = ctx.tool_service.build_ollama_tools(llm_tools)
        ctx.budget.tool_definitions_tokens = estimate_tool_definitions_tokens(ollama_tools)

        # Phase 1.2: Summarize older history if over threshold
        if settings.history_summary_enabled:
            ctx.messages = await apply_history_summarization(
                ctx.messages,
                ctx.budget,
                ctx.llm_service,
                ctx.model,
                preserve_recent=settings.history_preserve_recent,
                threshold=settings.history_summarization_threshold,
                max_summary_tokens=settings.history_summary_max_tokens,
            )

        # Phase 2.8: MemGPT-style eviction with recall storage
        if settings.memgpt_eviction_enabled:
            ctx.messages = await evict_and_store(
                ctx.messages, ctx.budget, ctx.llm_service, ctx.model,
                session=ctx.session,
                conversation_id=ctx.conversation_id,
                embedding_service=ctx.embedding_service,
                preserve_recent=max(4, settings.history_preserve_recent // 2),
            )

        ctx.messages = truncate_history(ctx.messages, ctx.budget)
        ctx.budget.log_summary()

        kwargs: dict = {"think": False}
        if ctx.options:
            kwargs["options"] = ctx.options

        for _round in range(MAX_TOOL_ROUNDS):
            if ctx.budget.tokens_remaining < 0:
                logger.warning(
                    "Agent round %d: token budget already exceeded by %d tokens",
                    _round,
                    -ctx.budget.tokens_remaining,
                )
            try:
                response = await ctx.llm_service.chat(
                    ctx.model, ctx.messages, tools=ollama_tools, **kwargs
                )
            except asyncio.CancelledError:
                logger.info("Chat cancelled by client for conversation %s", ctx.conversation_id)
                return
            except Exception:
                logger.exception("LLM chat failed for conversation %s", ctx.conversation_id)
                yield ServerSentEvent(
                    data=json.dumps({"error": "Model error. Is Ollama running?"}),
                    event="error",
                )
                return

            tool_calls = response.get("tool_calls")
            content = response.get("content", "")

            if tool_calls:
                # Save assistant message with tool_calls
                assistant_msg = Message(
                    conversation_id=ctx.conversation_id,
                    role="assistant",
                    content=content or "",
                    tool_calls=json.dumps(tool_calls),
                )
                ctx.session.add(assistant_msg)
                await ctx.session.flush()

                yield ServerSentEvent(
                    data=json.dumps({
                        "tool_calls": tool_calls,
                        "message_id": assistant_msg.id,
                    }),
                    event="tool_calls",
                )

                # Append assistant message to context
                assistant_ctx = {
                    "role": "assistant",
                    "content": content or "",
                    "tool_calls": tool_calls,
                }
                ctx.messages.append(assistant_ctx)
                ctx.budget.conversation_history_tokens += estimate_message_tokens(assistant_ctx)

                # Execute each tool call
                for tc in tool_calls:
                    func_info = tc.get("function", {})
                    raw_name = func_info.get("name", "")
                    raw_arguments = func_info.get("arguments", {})

                    if settings.tool_validation_enabled:
                        vr = validate_tool_call(raw_name, raw_arguments, ctx.tool_map)
                        if not vr.ok:
                            tool_name = raw_name
                            arguments = raw_arguments if isinstance(raw_arguments, dict) else {}
                            tool_result = f"[Tool call error: {'; '.join(vr.errors)}]"
                        else:
                            tool_name = vr.tool_name
                            arguments = vr.arguments
                            tool = ctx.tool_map[tool_name]
                            tool_result = await ctx.tool_service.execute_tool(
                                tool, arguments,
                                session=ctx.session,
                                conversation_id=ctx.conversation_id,
                                embedding_service=ctx.embedding_service,
                                llm_service=ctx.llm_service,
                            )
                    else:
                        tool_name = raw_name
                        arguments = raw_arguments
                        tool = ctx.tool_map.get(tool_name)
                        if tool:
                            tool_result = await ctx.tool_service.execute_tool(
                                tool, arguments,
                                session=ctx.session,
                                conversation_id=ctx.conversation_id,
                                embedding_service=ctx.embedding_service,
                                llm_service=ctx.llm_service,
                            )
                        else:
                            tool_result = f"[Unknown tool: {tool_name}]"

                    # Save tool result message
                    tool_msg = Message(
                        conversation_id=ctx.conversation_id,
                        role="tool",
                        content=tool_result,
                        tool_name=tool_name,
                    )
                    ctx.session.add(tool_msg)
                    await ctx.session.flush()

                    yield ServerSentEvent(
                        data=json.dumps({
                            "tool_name": tool_name,
                            "arguments": arguments,
                            "result": tool_result,
                            "message_id": tool_msg.id,
                        }),
                        event="tool_result",
                    )

                    # Append tool result to context
                    tool_ctx = {
                        "role": "tool",
                        "content": tool_result,
                        "tool_name": tool_name,
                    }
                    ctx.messages.append(tool_ctx)
                    ctx.budget.conversation_history_tokens += estimate_message_tokens(tool_ctx)
            else:
                # Final text response — chunk into token-like SSE events
                for i in range(0, len(content), TOKEN_CHUNK_SIZE):
                    chunk = content[i : i + TOKEN_CHUNK_SIZE]
                    yield ServerSentEvent(
                        data=json.dumps({"token": chunk}), event="token"
                    )

                # Save assistant message
                try:
                    assistant_msg = Message(
                        conversation_id=ctx.conversation_id,
                        role="assistant",
                        content=content,
                    )
                    ctx.session.add(assistant_msg)
                    await ctx.session.commit()
                except Exception:
                    logger.exception("Failed to save assistant message")
                    yield ServerSentEvent(
                        data=json.dumps({"error": "Failed to save response."}),
                        event="error",
                    )
                    return

                actions = _extract_suggestions(content)
                done_data: dict = {"message_id": assistant_msg.id}
                if actions:
                    done_data["actions"] = actions
                yield ServerSentEvent(
                    data=json.dumps(done_data),
                    event="done",
                )
                return

        # Max rounds reached
        yield ServerSentEvent(
            data=json.dumps({"error": "Tool calling exceeded maximum rounds."}),
            event="error",
        )
