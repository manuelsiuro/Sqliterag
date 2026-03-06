"""MemGPT-style eviction with recall storage (Phase 2.8).

Wraps around Phase 1.2 summarization to:
1. Inject context pressure warnings when utilization exceeds warning threshold
2. Archive evicted messages to game_memories (type "recall") before removal
3. Generate a summary of evicted content and inject an eviction notice

Three-tier defense:
  Phase 1.2 (70%) -> Phase 2.8 (95%) -> truncate_history (hard cap)
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.token_utils import (
    SUMMARY_PREFIX,
    TokenBudget,
    _build_message_groups,
    _format_messages_for_summary,
    estimate_message_tokens,
    estimate_tokens,
    generate_summary,
)

if TYPE_CHECKING:
    from app.services.base import BaseLLMService

logger = logging.getLogger(__name__)

# Markers for injected system messages (stripped on re-entry)
_WARNING_MARKER = "[CONTEXT_PRESSURE_WARNING]"
_EVICTION_MARKER = "[EVICTION_NOTICE]"


def _budget_utilization(messages: list[dict], budget: TokenBudget) -> float:
    """Compute current input utilization as a fraction (0.0-1.0+)."""
    ib = budget.input_budget
    if ib <= 0:
        return 1.0
    return budget.total_input_tokens / ib


def should_warn(budget: TokenBudget) -> bool:
    """Check if context pressure warning should be injected."""
    return (budget.total_input_tokens / max(budget.input_budget, 1)) >= settings.memgpt_warning_threshold


def build_context_warning(budget: TokenBudget) -> dict:
    """Build a system message warning the LLM about context pressure."""
    pct = budget.total_input_tokens / max(budget.input_budget, 1) * 100
    return {
        "role": "system",
        "content": (
            f"{_WARNING_MARKER} "
            f"Context is {pct:.0f}% full. "
            "Important information may be evicted soon. "
            "Use archive_event to save critical facts, or recall_context to retrieve evicted messages."
        ),
    }


def _strip_eviction_messages(messages: list[dict]) -> list[dict]:
    """Remove previously injected warning and eviction notices to prevent accumulation."""
    return [
        m for m in messages
        if not (
            m.get("role") == "system"
            and isinstance(m.get("content"), str)
            and (
                _WARNING_MARKER in m["content"]
                or _EVICTION_MARKER in m["content"]
            )
        )
    ]


def _compute_history_budget(budget: TokenBudget) -> int:
    """Compute the history-only budget (input budget minus fixed costs)."""
    fixed_cost = (
        budget.system_prompt_tokens
        + budget.rag_context_tokens
        + budget.tool_definitions_tokens
    )
    return budget.input_budget - fixed_cost


async def evict_and_store(
    messages: list[dict],
    budget: TokenBudget,
    llm_service: BaseLLMService,
    model: str,
    *,
    session: AsyncSession,
    conversation_id: str,
    embedding_service=None,
    preserve_recent: int = 10,
) -> list[dict]:
    """MemGPT-style eviction pipeline with recall storage.

    1. Strip old warnings/eviction notices
    2. If below flush threshold but above warning threshold: inject warning only
    3. If above flush threshold: evict ~50% of oldest groups, archive to recall
    4. Inject eviction notice telling LLM to use recall_context

    Returns a new message list (never mutates the input).
    """
    # Strip old injected messages first
    messages = _strip_eviction_messages(messages)

    # Recompute history tokens after stripping
    conv_tokens = sum(
        estimate_message_tokens(m)
        for m in messages
        if m.get("role") != "system"
    )
    budget.conversation_history_tokens = conv_tokens

    utilization = budget.total_input_tokens / max(budget.input_budget, 1)

    logger.debug(
        "Eviction check: utilization=%.1f%% (%d/%d), conv_tokens=%d, msgs=%d",
        utilization * 100, budget.total_input_tokens, budget.input_budget,
        conv_tokens, len(messages),
    )

    # Below warning threshold — nothing to do
    if utilization < settings.memgpt_warning_threshold:
        return messages

    # Separate system vs conversation messages
    system_msgs: list[dict] = []
    conv_msgs: list[dict] = []
    existing_summary: str | None = None

    for m in messages:
        if m.get("role") == "system":
            content = m.get("content") or ""
            if content.startswith(SUMMARY_PREFIX):
                existing_summary = content[len(SUMMARY_PREFIX):].strip()
            else:
                system_msgs.append(m)
        else:
            conv_msgs.append(m)

    # Below flush threshold — just inject warning
    if utilization < settings.memgpt_flush_threshold:
        warning_msg = build_context_warning(budget)
        result = system_msgs
        if existing_summary:
            result = result + [{"role": "system", "content": f"{SUMMARY_PREFIX}\n{existing_summary}"}]
        result = result + [warning_msg] + conv_msgs
        budget.conversation_history_tokens = conv_tokens + estimate_message_tokens(warning_msg)
        logger.info(
            "Context pressure warning injected (%.1f%% utilization)",
            utilization * 100,
        )
        return result

    # --- Flush threshold exceeded: evict old messages ---
    groups = _build_message_groups(conv_msgs)
    if len(groups) <= preserve_recent:
        # Not enough groups to evict — just inject warning
        logger.debug("Not enough groups to evict (%d <= %d)", len(groups), preserve_recent)
        warning_msg = build_context_warning(budget)
        result = system_msgs
        if existing_summary:
            result = result + [{"role": "system", "content": f"{SUMMARY_PREFIX}\n{existing_summary}"}]
        result = result + [warning_msg] + conv_msgs
        budget.conversation_history_tokens = conv_tokens + estimate_message_tokens(warning_msg)
        return result

    # Determine how many groups to evict (~50% of non-preserved groups)
    evictable_count = len(groups) - preserve_recent
    evict_count = max(1, int(evictable_count * settings.memgpt_flush_target_pct))

    evicted_groups = groups[:evict_count]
    kept_groups = groups[evict_count:]

    evicted_messages = [msg for group in evicted_groups for msg in group]
    kept_messages = [msg for group in kept_groups for msg in group]

    logger.info(
        "Evicting %d message groups (%d messages) at %.1f%% utilization",
        evict_count,
        len(evicted_messages),
        utilization * 100,
    )

    # Archive evicted messages to recall storage
    try:
        await _store_recall(
            session, conversation_id, evicted_messages, embedding_service,
        )
    except Exception:
        logger.warning("Failed to store recall memories", exc_info=True)

    # Generate summary of evicted content (reuses Phase 1.2 infra)
    summary_text = ""
    try:
        summary_text = await generate_summary(
            llm_service,
            model,
            evicted_messages,
            previous_summary=existing_summary,
            max_tokens=settings.memgpt_max_recall_tokens,
        )
    except Exception:
        logger.warning("Eviction summary generation failed", exc_info=True)

    # Build result
    result = list(system_msgs)

    # Add summary
    if summary_text:
        summary_msg = {"role": "system", "content": f"{SUMMARY_PREFIX}\n{summary_text}"}
        result.append(summary_msg)

    # Add eviction notice
    eviction_notice = {
        "role": "system",
        "content": (
            f"{_EVICTION_MARKER} "
            f"{len(evicted_messages)} older messages were archived to recall storage. "
            "Use the recall_context tool with a search query to retrieve them."
        ),
    }
    result.append(eviction_notice)

    # Add kept conversation messages
    result.extend(kept_messages)

    # Update budget tracking
    new_conv_tokens = sum(estimate_message_tokens(m) for m in kept_messages)
    extra_system = sum(
        estimate_message_tokens(m)
        for m in result
        if m.get("role") == "system" and m not in system_msgs
    )
    budget.conversation_history_tokens = new_conv_tokens
    budget.rag_context_tokens += extra_system  # Account for new system messages in existing bucket

    logger.info(
        "Eviction complete: %d messages archived, %d kept, summary=%d chars",
        len(evicted_messages),
        len(kept_messages),
        len(summary_text),
    )

    return result


async def _store_recall(
    session: AsyncSession,
    conversation_id: str,
    evicted_messages: list[dict],
    embedding_service=None,
) -> None:
    """Archive evicted messages as a single recall memory in game_memories."""
    from app.services import memory_service
    from app.services.rpg_service import get_or_create_session

    gs = await get_or_create_session(session, conversation_id)

    # Format evicted messages into a text block
    text = _format_messages_for_summary(evicted_messages)
    if not text.strip():
        return

    # Extract entity names from tool results for searchability
    entities = _extract_entities_from_messages(evicted_messages)

    await memory_service.create_memory(
        session,
        session_id=gs.id,
        memory_type="recall",
        entity_type="conversation",
        content=text,
        entity_names=entities,
        importance_score=settings.memgpt_recall_importance,
        session_number=gs.session_number,
        embedding_service=embedding_service,
    )
    logger.info(
        "Stored recall memory: %d messages, %d entities, %d chars",
        len(evicted_messages),
        len(entities),
        len(text),
    )


# Pattern to extract names from common tool result fields
_NAME_KEYS = {"name", "character", "attacker", "target", "npc_name", "location",
              "from_character", "to_character", "healer", "caster", "world_name"}


def _extract_entities_from_messages(messages: list[dict]) -> list[str]:
    """Scan tool results for character/NPC/location names to make recall searchable."""
    names: set[str] = set()
    for msg in messages:
        if msg.get("role") != "tool":
            continue
        content = msg.get("content", "")
        try:
            data = json.loads(content)
            if isinstance(data, dict):
                for key in _NAME_KEYS:
                    val = data.get(key)
                    if isinstance(val, str) and val:
                        names.add(val)
        except (json.JSONDecodeError, TypeError):
            pass
    return sorted(names)[:20]  # Cap at 20 entities
