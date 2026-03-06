from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sse_starlette.sse import ServerSentEvent

from app.config import settings
from app.models.message import Message
from app.models.tool import ConversationTool, Tool
from app.services.agent_base import SingleAgent
from app.services.agent_context import AgentContext
from app.services.base import BaseLLMService

if TYPE_CHECKING:
    from app.services.agent_orchestrator import AgentOrchestrator
from app.services.rag_service import RAGService
from app.services.token_utils import (
    TokenBudget,
    estimate_message_tokens,
    estimate_tokens,
    truncate_history,
)
from app.services.prompt_builder import (
    GamePhase,
    RPG_TOOL_NAMES,
    build_rpg_system_prompt,
    extract_recent_tool_names,
)
from app.services.tool_service import ToolService

# Phase-aware memory type preferences for auto-injection (Phase 2.7)
_PHASE_MEMORY_TYPES: dict[GamePhase, list[str]] = {
    GamePhase.COMBAT: ["episodic", "procedural"],
    GamePhase.SOCIAL: ["episodic", "semantic"],
    GamePhase.EXPLORATION: ["episodic", "semantic"],
}

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Action-suggestion extraction
# ---------------------------------------------------------------------------

_ACTION_BOLD_RE = re.compile(r"^(?:\d+[.)]\s*|[-•]\s+)?\*\*(.+?)\*\*\s*[–—\-:]\s*(.+)$")
_NUMBERED_RE = re.compile(r"^(?:\d+[.)]\s*|[-•]\s+)(.+)$")
_PROMPT_RE = re.compile(
    r"^\*{0,2}(what would you like to do|possible next actions|choose an action|"
    r"pick an action|select an option|what do you do|type what you'?d like to do|"
    r"your options|here are your options|your choices|available actions)",
    re.IGNORECASE,
)
_TRAILING_JUNK_RE = re.compile(r"^[\s🎮🎲⚔️🗡️🛡️✨💀🐉🧙📜]*$")


def _extract_suggestions(content: str) -> list[dict]:
    """Extract action suggestions from the tail of LLM output.

    Returns a list of ``{"label": ..., "description": ...}`` dicts.
    Empty list when no action block is detected.
    """
    lines = content.rstrip().split("\n")

    # --- Pass 1: bold-format actions (**Label** – Description) ---
    end = len(lines) - 1
    # Skip trailing blank/emoji lines AND prompt lines ("What would you like to do?")
    while end >= 0 and (
        _TRAILING_JUNK_RE.match(lines[end].strip())
        or _PROMPT_RE.match(lines[end].strip())
    ):
        end -= 1
    if end < 0:
        return []

    start = end
    while start >= 0 and _ACTION_BOLD_RE.match(lines[start].strip()):
        start -= 1
    start += 1

    if end - start + 1 >= 2:
        actions: list[dict] = []
        for i in range(start, end + 1):
            m = _ACTION_BOLD_RE.match(lines[i].strip())
            if m:
                actions.append({"label": m.group(1).strip(), "description": m.group(2).strip()})
        return actions

    # --- Pass 2: numbered/bulleted list after a prompt header ---
    prompt_idx = -1
    for i in range(len(lines) - 1, -1, -1):
        if _PROMPT_RE.match(lines[i].strip()):
            prompt_idx = i
            break
    if prompt_idx < 0:
        return []

    actions = []
    started = False
    for i in range(prompt_idx + 1, len(lines)):
        trimmed = lines[i].strip()
        if not trimmed or _TRAILING_JUNK_RE.match(trimmed):
            if started:
                break
            continue
        started = True
        nm = _NUMBERED_RE.match(trimmed)
        label = nm.group(1).strip() if nm else trimmed
        actions.append({"label": label, "description": ""})

    return actions if len(actions) >= 2 else []


RAG_SYSTEM_TEMPLATE = (
    "Use the following context to help answer the user's question. "
    "If the context is not relevant, ignore it and answer based on your knowledge.\n\n"
    "Context:\n{context}"
)

class ChatService:
    def __init__(
        self,
        llm_service: BaseLLMService,
        rag_service: RAGService,
        tool_service: ToolService,
        embedding_service: BaseLLMService | None = None,
        orchestrator: "AgentOrchestrator | None" = None,
    ):
        self.llm_service = llm_service
        self.rag_service = rag_service
        self.tool_service = tool_service
        self.embedding_service = embedding_service
        self.orchestrator = orchestrator
        self._budget_cache: dict[str, dict] = {}

    def get_cached_budget(self, conversation_id: str) -> dict | None:
        return self._budget_cache.get(conversation_id)

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

        # Inject relevant game memories into context (Phase 2.3)
        if phase is not None and settings.memory_hybrid_search_enabled:
            try:
                from app.services.rpg_service import get_or_create_session as get_game_session
                from app.services.memory_service import search_graphrag, get_memories_by_ids

                game_session = await get_game_session(session, conversation_id)
                preferred_types = None
                if settings.memory_prefilter_enabled and phase is not None:
                    preferred_types = _PHASE_MEMORY_TYPES.get(phase)
                memory_results = await search_graphrag(
                    session, user_message,
                    embedding_service=self.embedding_service,
                    session_id=game_session.id,
                    game_session_id=game_session.id,
                    memory_types=preferred_types,
                )
                if memory_results:
                    memory_ids = [mid for mid, _score in memory_results]
                    memories = await get_memories_by_ids(session, memory_ids)
                    if memories:
                        memory_text = "\n---\n".join(
                            f"[{m.memory_type}] {m.content}" for m in memories
                        )
                        memory_system = (
                            "Relevant game memories (use these to maintain consistency "
                            "and recall past events):\n" + memory_text
                        )
                        messages.insert(0, {"role": "system", "content": memory_system})
                        budget.rag_context_tokens += estimate_tokens(memory_system)
                        logger.info(
                            "Injected %d game memories into context", len(memories)
                        )
            except Exception:
                logger.warning("Game memory retrieval failed", exc_info=True)

        kwargs = {"think": False}
        if options:
            kwargs["options"] = options

        if conv_tools:
            # === Agent loop with tool calling ===
            ctx = AgentContext(
                session=session,
                conversation_id=conversation_id,
                model=model,
                user_message=user_message,
                options=options,
                llm_service=self.llm_service,
                tool_service=self.tool_service,
                embedding_service=self.embedding_service,
                budget=budget,
                messages=messages,
                conv_tools=conv_tools,
                tool_map={t.name: t for t in conv_tools},
                phase=phase,
            )

            if (
                settings.multi_agent_enabled
                and self.orchestrator is not None
                and phase is not None
            ):
                async for event in self.orchestrator.run_pipeline(ctx):
                    yield event
            else:
                agent = SingleAgent()
                async for event in agent.run(ctx):
                    yield event
            self._budget_cache[conversation_id] = ctx.budget.to_dict()
        else:
            # === Original streaming path (no tools) ===
            messages = truncate_history(messages, budget)
            budget.log_summary()
            # Emit budget for frontend visualization (Phase 5.6)
            yield ServerSentEvent(
                data=json.dumps(budget.to_dict()), event="budget"
            )
            self._budget_cache[conversation_id] = budget.to_dict()
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

            actions = _extract_suggestions(full_response)
            done_data2: dict = {"message_id": assistant_msg.id}
            if actions:
                done_data2["actions"] = actions
            yield ServerSentEvent(data=json.dumps(done_data2), event="done")

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
