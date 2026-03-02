from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sse_starlette.sse import ServerSentEvent

from app.models.message import Message
from app.services.base import BaseLLMService
from app.services.rag_service import RAGService

logger = logging.getLogger(__name__)

RAG_SYSTEM_TEMPLATE = (
    "Use the following context to help answer the user's question. "
    "If the context is not relevant, ignore it and answer based on your knowledge.\n\n"
    "Context:\n{context}"
)


class ChatService:
    def __init__(self, llm_service: BaseLLMService, rag_service: RAGService):
        self.llm_service = llm_service
        self.rag_service = rag_service

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

        messages = [{"role": m.role, "content": m.content} for m in history]

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

        # Stream response
        full_response = ""
        try:
            kwargs = {}
            if options:
                kwargs["options"] = options
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
