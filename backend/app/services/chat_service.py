from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sse_starlette.sse import ServerSentEvent

from app.models.message import Message
from app.models.tool import ConversationTool, Tool
from app.services.base import BaseLLMService
from app.services.rag_service import RAGService
from app.services.tool_service import ToolService

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

        # Try RAG context injection
        try:
            context_chunks = await self.rag_service.retrieve_context(session, user_message)
            if context_chunks:
                context_text = "\n---\n".join(context_chunks)
                rag_system = RAG_SYSTEM_TEMPLATE.format(context=context_text)
                messages.insert(0, {"role": "system", "content": rag_system})
                logger.info("Injected %d RAG chunks into context", len(context_chunks))
        except Exception:
            logger.warning("RAG retrieval failed, proceeding without context", exc_info=True)

        # Load conversation tools
        conv_tools = await self._load_conversation_tools(session, conversation_id)

        kwargs = {}
        if options:
            kwargs["options"] = options

        if conv_tools:
            # === Agent loop with tool calling (non-streaming) ===
            ollama_tools = self.tool_service.build_ollama_tools(conv_tools)
            tool_map = {t.name: t for t in conv_tools}

            for _round in range(MAX_TOOL_ROUNDS):
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
                    messages.append({
                        "role": "assistant",
                        "content": content or "",
                        "tool_calls": tool_calls,
                    })

                    # Execute each tool call
                    for tc in tool_calls:
                        func_info = tc.get("function", {})
                        tool_name = func_info.get("name", "")
                        arguments = func_info.get("arguments", {})

                        tool = tool_map.get(tool_name)
                        if tool:
                            tool_result = await self.tool_service.execute_tool(tool, arguments)
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
                        messages.append({
                            "role": "tool",
                            "content": tool_result,
                            "tool_name": tool_name,
                        })
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
