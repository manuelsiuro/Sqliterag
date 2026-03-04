from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sse_starlette.sse import ServerSentEvent

from app.config import settings
from app.models.message import Message
from app.models.tool import ConversationTool, Tool
from app.services.base import BaseLLMService
from app.services.rag_service import RAGService
from app.services.token_utils import (
    TokenBudget,
    apply_history_summarization,
    estimate_message_tokens,
    estimate_tokens,
    estimate_tool_definitions_tokens,
    truncate_history,
)
from app.services.prompt_builder import (
    RPG_TOOL_NAMES,
    build_rpg_system_prompt,
    extract_recent_tool_names,
    filter_tools_by_phase,
)
from app.services.tool_service import ToolService
from app.services.tool_validation import validate_tool_call

logger = logging.getLogger(__name__)

RAG_SYSTEM_TEMPLATE = (
    "Use the following context to help answer the user's question. "
    "If the context is not relevant, ignore it and answer based on your knowledge.\n\n"
    "Context:\n{context}"
)

MAX_TOOL_ROUNDS = 10
TOKEN_CHUNK_SIZE = 4  # chars per fake "token" when chunking non-streamed response


class ChatService:
    def __init__(self, llm_service: BaseLLMService, rag_service: RAGService, tool_service: ToolService):
        self.llm_service = llm_service
        self.rag_service = rag_service
        self.tool_service = tool_service

    async def stream_chat(
        self,
        session: AsyncSession,
        conversation_id: str,
        model: str,
        user_message: str,
        options: dict | None = None,
    ) -> AsyncGenerator[str]:
        # Save user message
        user_msg = Message(
            conversation_id=conversation_id,
            role="user",
            content=user_message,
        )
        session.add(user_msg)
        await session.flush()

        # Merge default model parameters with user overrides (user wins)
        merged_options = dict(settings.default_model_parameters)
        merged_options["num_ctx"] = settings.default_num_ctx
        if options:
            merged_options.update(options)
        options = merged_options

        # Initialize token budget
        num_ctx = options.get("num_ctx", settings.default_num_ctx)
        budget = TokenBudget(num_ctx=num_ctx)

        # Build message history
        result = await session.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        history = result.scalars().all()

        messages = []
        for m in history:
            msg = {"role": m.role, "content": m.content}
            if m.role == "assistant" and m.tool_calls:
                msg["tool_calls"] = json.loads(m.tool_calls)
            if m.role == "tool" and m.tool_name:
                msg["tool_name"] = m.tool_name
            messages.append(msg)

        budget.conversation_history_tokens = sum(
            estimate_message_tokens(m) for m in messages
        )

        # Try RAG context injection
        try:
            context_chunks = await self.rag_service.retrieve_context(session, user_message)
            if context_chunks:
                context_text = "\n---\n".join(context_chunks)
                rag_system = RAG_SYSTEM_TEMPLATE.format(context=context_text)
                messages.insert(0, {"role": "system", "content": rag_system})
                budget.rag_context_tokens = estimate_tokens(rag_system)
                logger.info("Injected %d RAG chunks into context", len(context_chunks))
        except Exception:
            logger.warning("RAG retrieval failed, proceeding without context", exc_info=True)

        # Load conversation tools
        conv_tools = await self._load_conversation_tools(session, conversation_id)

        # Inject dynamic RPG DM system prompt if RPG tools are enabled
        phase = None
        if conv_tools:
            tool_names = {t.name for t in conv_tools}
            if tool_names & RPG_TOOL_NAMES:
                recent_tools = extract_recent_tool_names(messages)
                prompt_result = await build_rpg_system_prompt(
                    session, conversation_id, recent_tools,
                )
                dynamic_prompt = prompt_result.prompt
                phase = prompt_result.phase
                messages.insert(0, {"role": "system", "content": dynamic_prompt})
                budget.system_prompt_tokens = estimate_tokens(dynamic_prompt)

        kwargs = {"think": False}
        if options:
            kwargs["options"] = options

        if conv_tools:
            # === Agent loop with tool calling (non-streaming) ===
            # Phase 1.4: Filter tools by game phase
            if phase is not None and settings.tool_injection_enabled:
                llm_tools = filter_tools_by_phase(conv_tools, phase)
                logger.info("Tool injection: phase=%s, %d/%d tools", phase.value, len(llm_tools), len(conv_tools))
            else:
                llm_tools = conv_tools

            ollama_tools = self.tool_service.build_ollama_tools(llm_tools)
            budget.tool_definitions_tokens = estimate_tool_definitions_tokens(ollama_tools)

            # Phase 1.2: Summarize older history if over threshold
            if settings.history_summary_enabled:
                messages = await apply_history_summarization(
                    messages,
                    budget,
                    self.llm_service,
                    model,
                    preserve_recent=settings.history_preserve_recent,
                    threshold=settings.history_summarization_threshold,
                    max_summary_tokens=settings.history_summary_max_tokens,
                )

            messages = truncate_history(messages, budget)
            budget.log_summary()
            tool_map = {t.name: t for t in conv_tools}

            for _round in range(MAX_TOOL_ROUNDS):
                if budget.tokens_remaining < 0:
                    logger.warning(
                        "Agent round %d: token budget already exceeded by %d tokens",
                        _round,
                        -budget.tokens_remaining,
                    )
                try:
                    response = await self.llm_service.chat(
                        model, messages, tools=ollama_tools, **kwargs
                    )
                except asyncio.CancelledError:
                    logger.info("Chat cancelled by client for conversation %s", conversation_id)
                    return
                except Exception:
                    logger.exception("LLM chat failed for conversation %s", conversation_id)
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
                        conversation_id=conversation_id,
                        role="assistant",
                        content=content or "",
                        tool_calls=json.dumps(tool_calls),
                    )
                    session.add(assistant_msg)
                    await session.flush()

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
                    messages.append(assistant_ctx)
                    budget.conversation_history_tokens += estimate_message_tokens(assistant_ctx)

                    # Execute each tool call
                    for tc in tool_calls:
                        func_info = tc.get("function", {})
                        raw_name = func_info.get("name", "")
                        raw_arguments = func_info.get("arguments", {})

                        if settings.tool_validation_enabled:
                            vr = validate_tool_call(raw_name, raw_arguments, tool_map)
                            if not vr.ok:
                                tool_name = raw_name
                                arguments = raw_arguments if isinstance(raw_arguments, dict) else {}
                                tool_result = f"[Tool call error: {'; '.join(vr.errors)}]"
                            else:
                                tool_name = vr.tool_name
                                arguments = vr.arguments
                                tool = tool_map[tool_name]
                                tool_result = await self.tool_service.execute_tool(
                                    tool, arguments,
                                    session=session,
                                    conversation_id=conversation_id,
                                )
                        else:
                            tool_name = raw_name
                            arguments = raw_arguments
                            tool = tool_map.get(tool_name)
                            if tool:
                                tool_result = await self.tool_service.execute_tool(
                                    tool, arguments,
                                    session=session,
                                    conversation_id=conversation_id,
                                )
                            else:
                                tool_result = f"[Unknown tool: {tool_name}]"

                        # Save tool result message
                        tool_msg = Message(
                            conversation_id=conversation_id,
                            role="tool",
                            content=tool_result,
                            tool_name=tool_name,
                        )
                        session.add(tool_msg)
                        await session.flush()

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
                        messages.append(tool_ctx)
                        budget.conversation_history_tokens += estimate_message_tokens(tool_ctx)
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
                            conversation_id=conversation_id,
                            role="assistant",
                            content=content,
                        )
                        session.add(assistant_msg)
                        await session.commit()
                    except Exception:
                        logger.exception("Failed to save assistant message")
                        yield ServerSentEvent(
                            data=json.dumps({"error": "Failed to save response."}),
                            event="error",
                        )
                        return

                    yield ServerSentEvent(
                        data=json.dumps({"message_id": assistant_msg.id}),
                        event="done",
                    )
                    return

            # Max rounds reached — send whatever we have
            yield ServerSentEvent(
                data=json.dumps({"error": "Tool calling exceeded maximum rounds."}),
                event="error",
            )
        else:
            # === Original streaming path (no tools) ===
            messages = truncate_history(messages, budget)
            budget.log_summary()
            full_response = ""
            try:
                async for token in self.llm_service.chat_stream(model, messages, **kwargs):
                    full_response += token
                    yield ServerSentEvent(data=json.dumps({"token": token}), event="token")
            except asyncio.CancelledError:
                logger.info("Stream cancelled by client for conversation %s", conversation_id)
                return
            except Exception:
                logger.exception("LLM streaming failed for conversation %s", conversation_id)
                yield ServerSentEvent(data=json.dumps({"error": "Model error. Is Ollama running?"}), event="error")
                return

            # Save assistant message
            try:
                assistant_msg = Message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=full_response,
                )
                session.add(assistant_msg)
                await session.commit()
            except Exception:
                logger.exception("Failed to save assistant message")
                yield ServerSentEvent(data=json.dumps({"error": "Failed to save response."}), event="error")
                return

            yield ServerSentEvent(data=json.dumps({"message_id": assistant_msg.id}), event="done")

    async def _load_conversation_tools(
        self, session: AsyncSession, conversation_id: str
    ) -> list[Tool]:
        result = await session.execute(
            select(Tool)
            .join(ConversationTool, ConversationTool.tool_id == Tool.id)
            .where(
                ConversationTool.conversation_id == conversation_id,
                Tool.is_enabled == True,  # noqa: E712
            )
        )
        return list(result.scalars().all())
