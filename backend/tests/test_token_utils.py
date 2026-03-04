"""Tests for token estimation utilities and TokenBudget."""

import json
import logging
from unittest.mock import AsyncMock

import pytest

from app.services.token_utils import (
    MESSAGE_OVERHEAD,
    SUMMARY_PREFIX,
    TokenBudget,
    _build_message_groups,
    _format_messages_for_summary,
    apply_history_summarization,
    estimate_message_tokens,
    estimate_tokens,
    estimate_tool_definitions_tokens,
    generate_summary,
    truncate_history,
)


# --- estimate_tokens ---


class TestEstimateTokens:
    def test_empty_string(self):
        assert estimate_tokens("") == 1

    def test_short_text(self):
        # "hi" = 2 chars -> 2 // 4 + 1 = 1
        assert estimate_tokens("hi") == 1

    def test_exact_multiple_of_4(self):
        # 8 chars -> 8 // 4 + 1 = 3
        assert estimate_tokens("abcdefgh") == 3

    def test_long_text(self):
        text = "a" * 400
        assert estimate_tokens(text) == 101

    def test_json_content(self):
        data = json.dumps({"key": "value", "number": 42})
        result = estimate_tokens(data)
        assert result == len(data) // 4 + 1


# --- estimate_message_tokens ---


class TestEstimateMessageTokens:
    def test_simple_user_message(self):
        msg = {"role": "user", "content": "Hello world"}
        result = estimate_message_tokens(msg)
        expected = MESSAGE_OVERHEAD + estimate_tokens("Hello world")
        assert result == expected

    def test_assistant_with_tool_calls(self):
        tool_calls = [{"function": {"name": "roll_dice", "arguments": {"notation": "2d6"}}}]
        msg = {"role": "assistant", "content": "Rolling...", "tool_calls": tool_calls}
        result = estimate_message_tokens(msg)
        expected = (
            MESSAGE_OVERHEAD
            + estimate_tokens("Rolling...")
            + estimate_tokens(json.dumps(tool_calls))
        )
        assert result == expected

    def test_empty_content(self):
        msg = {"role": "assistant", "content": ""}
        result = estimate_message_tokens(msg)
        # Empty string is falsy, so content not counted
        assert result == MESSAGE_OVERHEAD

    def test_none_content(self):
        msg = {"role": "assistant", "content": None}
        result = estimate_message_tokens(msg)
        assert result == MESSAGE_OVERHEAD

    def test_no_content_key(self):
        msg = {"role": "system"}
        result = estimate_message_tokens(msg)
        assert result == MESSAGE_OVERHEAD

    def test_tool_result_with_tool_name(self):
        msg = {"role": "tool", "content": '{"type": "roll_dice"}', "tool_name": "roll_dice"}
        result = estimate_message_tokens(msg)
        expected = (
            MESSAGE_OVERHEAD
            + estimate_tokens('{"type": "roll_dice"}')
            + estimate_tokens("roll_dice")
        )
        assert result == expected


# --- estimate_tool_definitions_tokens ---


class TestEstimateToolDefinitionsTokens:
    def test_empty_list(self):
        assert estimate_tool_definitions_tokens([]) == 0

    def test_single_tool(self):
        tools = [{"type": "function", "function": {"name": "roll_dice", "parameters": {}}}]
        result = estimate_tool_definitions_tokens(tools)
        assert result == estimate_tokens(json.dumps(tools))
        assert result > 0

    def test_more_tools_more_tokens(self):
        one_tool = [{"type": "function", "function": {"name": "a", "parameters": {}}}]
        two_tools = one_tool + [{"type": "function", "function": {"name": "b", "parameters": {}}}]
        assert estimate_tool_definitions_tokens(two_tools) > estimate_tool_definitions_tokens(one_tool)


# --- TokenBudget ---


class TestTokenBudget:
    def test_default_values(self):
        b = TokenBudget()
        assert b.num_ctx == 8192
        assert b.response_reserve == 2000
        assert b.safety_buffer == 300
        assert b.input_budget == 8192 - 2000 - 300  # 5892

    def test_custom_num_ctx(self):
        b = TokenBudget(num_ctx=16384)
        assert b.input_budget == 16384 - 2000 - 300

    def test_total_input_tokens(self):
        b = TokenBudget()
        b.system_prompt_tokens = 100
        b.rag_context_tokens = 200
        b.tool_definitions_tokens = 300
        b.conversation_history_tokens = 400
        assert b.total_input_tokens == 1000

    def test_tokens_remaining(self):
        b = TokenBudget()
        b.conversation_history_tokens = 1000
        assert b.tokens_remaining == b.input_budget - 1000

    def test_utilization_pct(self):
        b = TokenBudget(num_ctx=4300, response_reserve=2000, safety_buffer=300)
        # input_budget = 2000
        b.conversation_history_tokens = 1000
        assert b.utilization_pct == pytest.approx(50.0)

    def test_over_budget_detection(self):
        b = TokenBudget(num_ctx=2300, response_reserve=2000, safety_buffer=300)
        # input_budget = 0
        b.conversation_history_tokens = 500
        assert b.tokens_remaining < 0
        assert b.utilization_pct == 100.0  # zero budget edge case

    def test_log_summary_info(self, caplog):
        b = TokenBudget()
        b.conversation_history_tokens = 100
        with caplog.at_level(logging.INFO, logger="app.services.token_utils"):
            b.log_summary()
        assert "Token budget:" in caplog.text
        assert "total_input=100" in caplog.text

    def test_log_summary_warning_exceeded(self, caplog):
        b = TokenBudget(num_ctx=2500, response_reserve=2000, safety_buffer=300)
        # input_budget = 200
        b.conversation_history_tokens = 500
        with caplog.at_level(logging.WARNING, logger="app.services.token_utils"):
            b.log_summary()
        assert "EXCEEDED" in caplog.text

    def test_log_summary_warning_high(self, caplog):
        b = TokenBudget(num_ctx=2500, response_reserve=2000, safety_buffer=300)
        # input_budget = 200, 85% of 200 = 170
        b.conversation_history_tokens = 170
        with caplog.at_level(logging.WARNING, logger="app.services.token_utils"):
            b.log_summary()
        assert "HIGH" in caplog.text

    def test_log_summary_truncated_suffix(self, caplog):
        b = TokenBudget()
        b.conversation_history_tokens = 100
        b.truncated_message_count = 5
        with caplog.at_level(logging.INFO, logger="app.services.token_utils"):
            b.log_summary()
        assert "truncated=5 msgs" in caplog.text

    def test_log_summary_no_truncated_suffix(self, caplog):
        b = TokenBudget()
        b.conversation_history_tokens = 100
        with caplog.at_level(logging.INFO, logger="app.services.token_utils"):
            b.log_summary()
        assert "truncated=" not in caplog.text


# --- _build_message_groups ---


class TestBuildMessageGroups:
    def test_standalone_messages(self):
        msgs = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
            {"role": "user", "content": "bye"},
        ]
        groups = _build_message_groups(msgs)
        assert len(groups) == 3
        assert all(len(g) == 1 for g in groups)

    def test_tool_call_group(self):
        msgs = [
            {"role": "user", "content": "roll dice"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "roll_dice"}}]},
            {"role": "tool", "content": '{"type":"roll_dice"}', "tool_name": "roll_dice"},
            {"role": "assistant", "content": "You rolled a 6!"},
        ]
        groups = _build_message_groups(msgs)
        assert len(groups) == 3  # user, (assistant+tool), assistant
        assert len(groups[1]) == 2  # assistant + tool grouped

    def test_multiple_tool_results(self):
        msgs = [
            {"role": "assistant", "content": "", "tool_calls": [
                {"function": {"name": "a"}},
                {"function": {"name": "b"}},
            ]},
            {"role": "tool", "content": "r1", "tool_name": "a"},
            {"role": "tool", "content": "r2", "tool_name": "b"},
            {"role": "user", "content": "ok"},
        ]
        groups = _build_message_groups(msgs)
        assert len(groups) == 2  # (assistant+tool+tool), user
        assert len(groups[0]) == 3


# --- truncate_history ---


class TestTruncateHistory:
    def _make_msg(self, role, content, **extra):
        msg = {"role": role, "content": content}
        msg.update(extra)
        return msg

    def _budget(self, **overrides):
        defaults = dict(num_ctx=8192, response_reserve=2000, safety_buffer=300)
        defaults.update(overrides)
        return TokenBudget(**defaults)

    def test_no_truncation_within_budget(self):
        """Short history returned unchanged, truncated_message_count == 0."""
        msgs = [
            self._make_msg("user", "hi"),
            self._make_msg("assistant", "hello"),
        ]
        budget = self._budget()
        result = truncate_history(msgs, budget)
        assert result == msgs
        assert budget.truncated_message_count == 0

    def test_drops_oldest_messages(self):
        """Oldest conversation messages dropped, newest preserved."""
        # Build messages that will exceed a tiny budget
        msgs = [self._make_msg("user", "x" * 200) for _ in range(20)]
        # Tiny context window: input_budget = 500 - 200 - 100 = 200
        budget = self._budget(num_ctx=500, response_reserve=200, safety_buffer=100)
        result = truncate_history(msgs, budget)
        # Should have fewer messages than original
        conv_result = [m for m in result if m.get("role") != "system"]
        assert len(conv_result) < 20
        # Last message should be the most recent user message
        assert conv_result[-1]["content"] == "x" * 200
        assert budget.truncated_message_count > 0

    def test_system_messages_preserved(self):
        """System messages at front never dropped."""
        sys_msg = self._make_msg("system", "You are a helpful assistant. " * 10)
        msgs = [sys_msg] + [self._make_msg("user", "x" * 200) for _ in range(20)]
        budget = self._budget(num_ctx=500, response_reserve=200, safety_buffer=100)
        budget.system_prompt_tokens = estimate_message_tokens(sys_msg)
        result = truncate_history(msgs, budget)
        # First message should still be the system message
        assert result[0] == sys_msg

    def test_tool_call_groups_atomic(self):
        """Assistant+tool groups never split."""
        msgs = [
            self._make_msg("user", "do something"),
            self._make_msg("assistant", "", tool_calls=[{"function": {"name": "t"}}]),
            self._make_msg("tool", '{"type":"test"}', tool_name="t"),
            self._make_msg("user", "another thing " * 20),
            self._make_msg("assistant", "response " * 20),
            self._make_msg("user", "latest"),
            self._make_msg("assistant", "latest reply"),
        ]
        budget = self._budget(num_ctx=700, response_reserve=200, safety_buffer=100)
        result = truncate_history(msgs, budget)
        # Check: no orphaned tool messages (every tool msg preceded by assistant with tool_calls)
        for i, m in enumerate(result):
            if m.get("role") == "tool":
                prev = result[i - 1]
                assert (
                    prev.get("role") == "assistant" and prev.get("tool_calls")
                ) or (
                    prev.get("role") == "tool"  # consecutive tool results in same group
                ), f"Orphaned tool message at index {i}"

    def test_truncation_inserts_notice(self):
        """Synthetic system notice present when messages dropped."""
        msgs = [self._make_msg("user", "x" * 200) for _ in range(20)]
        budget = self._budget(num_ctx=500, response_reserve=200, safety_buffer=100)
        result = truncate_history(msgs, budget)
        notices = [m for m in result if "truncated" in (m.get("content") or "").lower()]
        assert len(notices) == 1
        assert "messages omitted" in notices[0]["content"]

    def test_budget_fields_updated(self):
        """history_budget and conversation_history_tokens populated."""
        msgs = [
            self._make_msg("user", "hi"),
            self._make_msg("assistant", "hello"),
        ]
        budget = self._budget()
        budget.system_prompt_tokens = 50
        budget.rag_context_tokens = 100
        budget.tool_definitions_tokens = 200
        truncate_history(msgs, budget)
        # history_budget = input_budget - 50 - 100 - 200
        expected_hb = budget.input_budget - 350
        assert budget.history_budget == expected_hb
        assert budget.conversation_history_tokens > 0


# --- _format_messages_for_summary ---


class TestFormatMessagesForSummary:
    def test_simple_messages(self):
        msgs = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        result = _format_messages_for_summary(msgs)
        assert "USER: Hello" in result
        assert "ASSISTANT: Hi there" in result

    def test_tool_result_abbreviated(self):
        long_content = "x" * 300
        msgs = [{"role": "tool", "content": long_content, "tool_name": "roll_dice"}]
        result = _format_messages_for_summary(msgs)
        assert "[roll_dice result]" in result
        assert "..." in result
        # Should be abbreviated, not full 300 chars
        assert len(result) < 300

    def test_assistant_with_tool_calls(self):
        msgs = [
            {
                "role": "assistant",
                "content": "Let me roll",
                "tool_calls": [{"function": {"name": "roll_dice"}}],
            }
        ]
        result = _format_messages_for_summary(msgs)
        assert "Let me roll" in result
        assert "roll_dice" in result

    def test_assistant_tool_calls_no_content(self):
        msgs = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": "attack"}}],
            }
        ]
        result = _format_messages_for_summary(msgs)
        assert "ASSISTANT called tools: attack" in result


# --- generate_summary ---


class TestGenerateSummary:
    @pytest.fixture
    def mock_llm(self):
        llm = AsyncMock()
        llm.chat = AsyncMock(return_value={"content": "The party explored the dungeon."})
        return llm

    @pytest.mark.asyncio
    async def test_basic_summary(self, mock_llm):
        msgs = [
            {"role": "user", "content": "I enter the dungeon"},
            {"role": "assistant", "content": "You see a dark corridor"},
        ]
        result = await generate_summary(mock_llm, "llama3.2", msgs)
        assert result == "The party explored the dungeon."
        mock_llm.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_prompt_includes_messages(self, mock_llm):
        msgs = [{"role": "user", "content": "I attack the goblin"}]
        await generate_summary(mock_llm, "llama3.2", msgs)
        call_args = mock_llm.chat.call_args
        prompt = call_args[0][1][0]["content"]
        assert "I attack the goblin" in prompt

    @pytest.mark.asyncio
    async def test_recursive_summary(self, mock_llm):
        msgs = [{"role": "user", "content": "I rest at the inn"}]
        await generate_summary(
            mock_llm, "llama3.2", msgs,
            previous_summary="The party defeated a dragon.",
        )
        call_args = mock_llm.chat.call_args
        prompt = call_args[0][1][0]["content"]
        assert "The party defeated a dragon." in prompt
        assert "Previous summary" in prompt

    @pytest.mark.asyncio
    async def test_empty_response_returns_empty(self, mock_llm):
        mock_llm.chat = AsyncMock(return_value={"content": ""})
        result = await generate_summary(mock_llm, "llama3.2", [])
        assert result == ""


# --- apply_history_summarization ---


class TestApplyHistorySummarization:
    def _make_msg(self, role, content, **extra):
        msg = {"role": role, "content": content}
        msg.update(extra)
        return msg

    def _budget(self, **overrides):
        defaults = dict(num_ctx=8192, response_reserve=2000, safety_buffer=300)
        defaults.update(overrides)
        return TokenBudget(**defaults)

    @pytest.fixture
    def mock_llm(self):
        llm = AsyncMock()
        llm.chat = AsyncMock(return_value={"content": "Summary of events so far."})
        return llm

    @pytest.mark.asyncio
    async def test_no_summarization_under_threshold(self, mock_llm):
        """Short history stays unchanged."""
        msgs = [
            self._make_msg("user", "hi"),
            self._make_msg("assistant", "hello"),
        ]
        budget = self._budget()
        budget.conversation_history_tokens = sum(
            estimate_message_tokens(m) for m in msgs
        )
        result = await apply_history_summarization(msgs, budget, mock_llm, "llama3.2")
        assert result == msgs
        mock_llm.chat.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_summarization_few_groups(self, mock_llm):
        """Not enough groups to split → unchanged."""
        msgs = [self._make_msg("user", "x" * 400) for _ in range(5)]
        budget = self._budget(num_ctx=1000, response_reserve=200, safety_buffer=100)
        budget.conversation_history_tokens = sum(
            estimate_message_tokens(m) for m in msgs
        )
        result = await apply_history_summarization(
            msgs, budget, mock_llm, "llama3.2", preserve_recent=10,
        )
        assert result == msgs

    @pytest.mark.asyncio
    async def test_summarization_triggered(self, mock_llm):
        """When over threshold with enough groups, summary replaces old messages."""
        # 20 message groups, each ~105 tokens → well over threshold for a small budget
        msgs = [self._make_msg("user", "x" * 400) for _ in range(20)]
        budget = self._budget(num_ctx=3000, response_reserve=500, safety_buffer=100)
        budget.conversation_history_tokens = sum(
            estimate_message_tokens(m) for m in msgs
        )
        result = await apply_history_summarization(
            msgs, budget, mock_llm, "llama3.2", preserve_recent=5,
        )
        # Should have summary + 5 recent messages
        summary_msgs = [m for m in result if SUMMARY_PREFIX in (m.get("content") or "")]
        assert len(summary_msgs) == 1
        assert "Summary of events so far." in summary_msgs[0]["content"]
        # Recent messages preserved
        conv_msgs = [m for m in result if m.get("role") != "system"]
        assert len(conv_msgs) == 5
        mock_llm.chat.assert_called_once()

    @pytest.mark.asyncio
    async def test_system_messages_preserved(self, mock_llm):
        """System messages at front never removed."""
        sys_msg = self._make_msg("system", "You are a DM.")
        msgs = [sys_msg] + [self._make_msg("user", "x" * 400) for _ in range(20)]
        budget = self._budget(num_ctx=3000, response_reserve=500, safety_buffer=100)
        budget.system_prompt_tokens = estimate_message_tokens(sys_msg)
        budget.conversation_history_tokens = sum(
            estimate_message_tokens(m) for m in msgs if m.get("role") != "system"
        )
        result = await apply_history_summarization(
            msgs, budget, mock_llm, "llama3.2", preserve_recent=5,
        )
        assert result[0] == sys_msg

    @pytest.mark.asyncio
    async def test_tool_groups_stay_atomic(self, mock_llm):
        """Tool-call + results in recent window are not split."""
        old_msgs = [self._make_msg("user", "x" * 400) for _ in range(15)]
        # Recent: user, assistant+tool, user, assistant
        recent = [
            self._make_msg("user", "attack goblin"),
            self._make_msg("assistant", "", tool_calls=[{"function": {"name": "attack"}}]),
            self._make_msg("tool", '{"type":"attack_result"}', tool_name="attack"),
            self._make_msg("user", "nice"),
            self._make_msg("assistant", "The goblin falls!"),
        ]
        msgs = old_msgs + recent
        budget = self._budget(num_ctx=3000, response_reserve=500, safety_buffer=100)
        budget.conversation_history_tokens = sum(
            estimate_message_tokens(m) for m in msgs
        )
        result = await apply_history_summarization(
            msgs, budget, mock_llm, "llama3.2", preserve_recent=4,
        )
        # Verify no orphaned tool messages
        conv_result = [m for m in result if m.get("role") != "system"]
        for i, m in enumerate(conv_result):
            if m.get("role") == "tool":
                prev = conv_result[i - 1]
                assert (
                    prev.get("role") == "assistant" and prev.get("tool_calls")
                ) or prev.get("role") == "tool"

    @pytest.mark.asyncio
    async def test_budget_fields_updated(self, mock_llm):
        """summarized_message_count and summary_tokens are set."""
        msgs = [self._make_msg("user", "x" * 400) for _ in range(20)]
        budget = self._budget(num_ctx=3000, response_reserve=500, safety_buffer=100)
        budget.conversation_history_tokens = sum(
            estimate_message_tokens(m) for m in msgs
        )
        await apply_history_summarization(
            msgs, budget, mock_llm, "llama3.2", preserve_recent=5,
        )
        assert budget.summarized_message_count == 15
        assert budget.summary_tokens > 0

    @pytest.mark.asyncio
    async def test_llm_failure_returns_original(self, mock_llm):
        """If LLM call fails, original messages returned."""
        mock_llm.chat = AsyncMock(side_effect=RuntimeError("Ollama down"))
        msgs = [self._make_msg("user", "x" * 400) for _ in range(20)]
        budget = self._budget(num_ctx=3000, response_reserve=500, safety_buffer=100)
        budget.conversation_history_tokens = sum(
            estimate_message_tokens(m) for m in msgs
        )
        result = await apply_history_summarization(
            msgs, budget, mock_llm, "llama3.2", preserve_recent=5,
        )
        assert result == msgs

    @pytest.mark.asyncio
    async def test_empty_summary_returns_original(self, mock_llm):
        """If LLM returns empty summary, original messages returned."""
        mock_llm.chat = AsyncMock(return_value={"content": ""})
        msgs = [self._make_msg("user", "x" * 400) for _ in range(20)]
        budget = self._budget(num_ctx=3000, response_reserve=500, safety_buffer=100)
        budget.conversation_history_tokens = sum(
            estimate_message_tokens(m) for m in msgs
        )
        result = await apply_history_summarization(
            msgs, budget, mock_llm, "llama3.2", preserve_recent=5,
        )
        assert result == msgs

    @pytest.mark.asyncio
    async def test_recursive_summary_extracts_previous(self, mock_llm):
        """Existing summary message is extracted and passed as previous_summary."""
        existing_summary_msg = self._make_msg(
            "system", f"{SUMMARY_PREFIX}\nThe party fought wolves."
        )
        msgs = (
            [existing_summary_msg]
            + [self._make_msg("user", "x" * 400) for _ in range(20)]
        )
        budget = self._budget(num_ctx=3000, response_reserve=500, safety_buffer=100)
        budget.conversation_history_tokens = sum(
            estimate_message_tokens(m) for m in msgs if m.get("role") != "system"
        )
        await apply_history_summarization(
            msgs, budget, mock_llm, "llama3.2", preserve_recent=5,
        )
        # The LLM prompt should include the previous summary
        call_args = mock_llm.chat.call_args
        prompt = call_args[0][1][0]["content"]
        assert "The party fought wolves." in prompt

    @pytest.mark.asyncio
    async def test_log_summary_includes_summarized(self, mock_llm, caplog):
        """log_summary() shows summarized count when > 0."""
        msgs = [self._make_msg("user", "x" * 400) for _ in range(20)]
        budget = self._budget(num_ctx=3000, response_reserve=500, safety_buffer=100)
        budget.conversation_history_tokens = sum(
            estimate_message_tokens(m) for m in msgs
        )
        await apply_history_summarization(
            msgs, budget, mock_llm, "llama3.2", preserve_recent=5,
        )
        with caplog.at_level(logging.INFO, logger="app.services.token_utils"):
            budget.log_summary()
        assert "summarized=15 msgs" in caplog.text
