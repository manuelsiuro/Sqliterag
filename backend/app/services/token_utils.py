"""Token estimation utilities and budget tracking for context window management."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Approximate overhead per message (role name, delimiters, etc.)
MESSAGE_OVERHEAD = 4


def estimate_tokens(text: str) -> int:
    """Estimate token count using ~4 chars per token heuristic.

    Returns at least 1 for any input (including empty string) to account
    for structural tokens.
    """
    return len(text) // 4 + 1


def estimate_message_tokens(message: dict) -> int:
    """Estimate tokens for a single Ollama chat message.

    Accounts for role overhead, content, tool_calls (serialized), and tool_name.
    """
    tokens = MESSAGE_OVERHEAD

    content = message.get("content")
    if content:
        tokens += estimate_tokens(content)

    tool_calls = message.get("tool_calls")
    if tool_calls:
        tokens += estimate_tokens(json.dumps(tool_calls))

    tool_name = message.get("tool_name")
    if tool_name:
        tokens += estimate_tokens(tool_name)

    return tokens


def estimate_tool_definitions_tokens(tools: list[dict]) -> int:
    """Estimate tokens for the Ollama tools definition list.

    Returns 0 for an empty list since no tool definitions are sent.
    """
    if not tools:
        return 0
    return estimate_tokens(json.dumps(tools))


@dataclass
class TokenBudget:
    """Tracks per-component token costs against the context window budget."""

    num_ctx: int = 8192
    response_reserve: int = 2000
    safety_buffer: int = 300

    # Populated during stream_chat()
    system_prompt_tokens: int = 0
    rag_context_tokens: int = 0
    tool_definitions_tokens: int = 0
    conversation_history_tokens: int = 0

    # Populated by truncate_history()
    truncated_message_count: int = 0
    history_budget: int = 0

    @property
    def input_budget(self) -> int:
        """Maximum tokens available for input (context window minus reserves)."""
        return self.num_ctx - self.response_reserve - self.safety_buffer

    @property
    def total_input_tokens(self) -> int:
        """Sum of all tracked input token costs."""
        return (
            self.system_prompt_tokens
            + self.rag_context_tokens
            + self.tool_definitions_tokens
            + self.conversation_history_tokens
        )

    @property
    def tokens_remaining(self) -> int:
        """Tokens still available within the input budget."""
        return self.input_budget - self.total_input_tokens

    @property
    def utilization_pct(self) -> float:
        """Input budget utilization as a percentage (can exceed 100)."""
        budget = self.input_budget
        if budget <= 0:
            return 100.0
        return (self.total_input_tokens / budget) * 100

    def log_summary(self) -> None:
        """Log a token budget breakdown.

        INFO level for every request; WARNING when utilization is high or exceeded.
        """
        pct = self.utilization_pct
        trunc_suffix = ""
        if self.truncated_message_count > 0:
            trunc_suffix = f" | truncated={self.truncated_message_count} msgs"
        logger.info(
            "Token budget: system=%d rag=%d tools=%d history=%d "
            "| total_input=%d / %d (%.1f%%) | remaining=%d%s",
            self.system_prompt_tokens,
            self.rag_context_tokens,
            self.tool_definitions_tokens,
            self.conversation_history_tokens,
            self.total_input_tokens,
            self.input_budget,
            pct,
            self.tokens_remaining,
            trunc_suffix,
        )
        if pct > 100:
            logger.warning(
                "Token budget EXCEEDED: %.1f%% utilization (%d / %d)",
                pct,
                self.total_input_tokens,
                self.input_budget,
            )
        elif pct > 80:
            logger.warning(
                "Token budget HIGH: %.1f%% utilization (%d / %d)",
                pct,
                self.total_input_tokens,
                self.input_budget,
            )


# ---------------------------------------------------------------------------
# Conversation history truncation
# ---------------------------------------------------------------------------


def _build_message_groups(messages: list[dict]) -> list[list[dict]]:
    """Group messages into atomic units for truncation.

    An assistant message with ``tool_calls`` plus all immediately following
    ``tool`` messages form one indivisible group.  Every other message is a
    standalone group.  This prevents the LLM from seeing orphaned tool results.
    """
    groups: list[list[dict]] = []
    i = 0
    while i < len(messages):
        msg = messages[i]
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            group = [msg]
            i += 1
            while i < len(messages) and messages[i].get("role") == "tool":
                group.append(messages[i])
                i += 1
            groups.append(group)
        else:
            groups.append([msg])
            i += 1
    return groups


def _group_tokens(group: list[dict]) -> int:
    """Sum estimated tokens across all messages in a group."""
    return sum(estimate_message_tokens(m) for m in group)


def truncate_history(
    messages: list[dict],
    budget: TokenBudget,
    *,
    preserve_last: int = 10,
) -> list[dict]:
    """Truncate conversation history to fit within the token budget.

    The algorithm:
    1. Separate system messages (front) from conversation messages.
    2. Compute ``history_budget`` — tokens available after fixed costs.
    3. If conversation already fits, return unchanged.
    4. Build atomic message groups (tool-call + results stay together).
    5. Preserve the most recent ``preserve_last`` messages worth of groups.
    6. If even the tail exceeds budget, trim oldest groups from the tail.
    7. With remaining budget, add older groups newest-first.
    8. Insert a synthetic truncation notice when messages are dropped.
    9. Update *budget* fields in place.

    Returns a new message list (never mutates the input).
    """
    # 1. Separate system messages from conversation messages
    system_msgs: list[dict] = []
    conv_msgs: list[dict] = []
    for m in messages:
        if m.get("role") == "system":
            system_msgs.append(m)
        else:
            conv_msgs.append(m)

    # 2. Compute history budget (what's left for conversation messages)
    fixed_cost = (
        budget.system_prompt_tokens
        + budget.rag_context_tokens
        + budget.tool_definitions_tokens
    )
    history_budget = budget.input_budget - fixed_cost
    budget.history_budget = history_budget

    # 3. Check if conversation fits
    conv_tokens = sum(estimate_message_tokens(m) for m in conv_msgs)
    if conv_tokens <= history_budget:
        budget.conversation_history_tokens = conv_tokens
        budget.truncated_message_count = 0
        return messages

    # 4. Build atomic groups
    groups = _build_message_groups(conv_msgs)
    group_costs = [_group_tokens(g) for g in groups]

    # 5. Identify the preserved tail (last N messages worth of groups)
    tail_groups: list[int] = []  # indices into groups, from end
    tail_msg_count = 0
    for idx in range(len(groups) - 1, -1, -1):
        msg_count = len(groups[idx])
        if tail_msg_count + msg_count > preserve_last and tail_groups:
            break
        tail_groups.append(idx)
        tail_msg_count += msg_count
    tail_groups.reverse()

    # 6. If tail itself exceeds budget, trim oldest groups from it
    tail_tokens = sum(group_costs[i] for i in tail_groups)
    while tail_tokens > history_budget and len(tail_groups) > 1:
        removed_idx = tail_groups.pop(0)
        tail_tokens -= group_costs[removed_idx]

    # 7. With remaining budget, try adding older groups newest-first
    remaining_budget = history_budget - tail_tokens
    older_indices = [i for i in range(len(groups)) if i not in set(tail_groups)]
    kept_older: list[int] = []
    for idx in reversed(older_indices):
        cost = group_costs[idx]
        if cost <= remaining_budget:
            kept_older.append(idx)
            remaining_budget -= cost
    kept_older.reverse()

    # Combine kept indices
    all_kept = set(kept_older) | set(tail_groups)
    total_original_msgs = sum(len(groups[i]) for i in range(len(groups)))
    total_kept_msgs = sum(len(groups[i]) for i in all_kept)
    dropped_count = total_original_msgs - total_kept_msgs

    # 8. Assemble the result
    result = list(system_msgs)

    if dropped_count > 0:
        notice = {
            "role": "system",
            "content": (
                f"[Earlier conversation history was truncated. "
                f"{dropped_count} messages omitted.]"
            ),
        }
        result.append(notice)

    # Add groups in original order
    for idx in sorted(all_kept):
        result.extend(groups[idx])

    # 9. Update budget fields
    final_conv_tokens = sum(
        estimate_message_tokens(m)
        for m in result
        if m.get("role") != "system" or m not in system_msgs
    )
    budget.conversation_history_tokens = final_conv_tokens
    budget.truncated_message_count = dropped_count

    if dropped_count > 0:
        logger.info(
            "History truncated: dropped %d messages (history_budget=%d tokens)",
            dropped_count,
            history_budget,
        )

    return result
