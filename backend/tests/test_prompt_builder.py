"""Tests for the dynamic RPG system prompt builder."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.models.rpg import Character, GameSession, Location, NPC, Quest, Relationship
from app.services.prompt_builder import (
    GamePhase,
    PromptResult,
    RPG_TOOL_NAMES,
    _CORE_TOOLS,
    _PHASE_TOOLS,
    _STATIC_FALLBACK,
    _build_layer1_identity,
    _build_layer2_jit_rules,
    _build_layer3_state,
    _build_layer4_format,
    _compile_graph_context,
    build_rpg_system_prompt,
    detect_phase,
    extract_recent_tool_names,
    filter_tools_by_phase,
    get_phase_tool_names,
)


# --- detect_phase ---


class TestDetectPhase:
    def test_combat_state_present(self):
        assert detect_phase('{"turn": 1}', set()) is GamePhase.COMBAT

    def test_combat_state_overrides_social_tools(self):
        assert detect_phase('{"turn": 1}', {"talk_to_npc"}) is GamePhase.COMBAT

    def test_talk_to_npc_triggers_social(self):
        assert detect_phase(None, {"talk_to_npc"}) is GamePhase.SOCIAL

    def test_update_npc_relationship_triggers_social(self):
        assert detect_phase(None, {"update_npc_relationship"}) is GamePhase.SOCIAL

    def test_default_exploration(self):
        assert detect_phase(None, set()) is GamePhase.EXPLORATION

    def test_non_social_tools_stay_exploration(self):
        assert detect_phase(None, {"roll_check", "move_to"}) is GamePhase.EXPLORATION


# --- extract_recent_tool_names ---


class TestExtractRecentToolNames:
    def test_extracts_from_tool_messages(self):
        messages = [
            {"role": "user", "content": "attack"},
            {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "attack"}}]},
            {"role": "tool", "content": '{"type":"attack_result"}', "tool_name": "attack"},
            {"role": "tool", "content": '{"type":"roll_dice"}', "tool_name": "roll_dice"},
        ]
        result = extract_recent_tool_names(messages)
        assert result == {"attack", "roll_dice"}

    def test_respects_lookback_limit(self):
        messages = [
            {"role": "tool", "content": "a", "tool_name": "tool_a"},
            {"role": "tool", "content": "b", "tool_name": "tool_b"},
            {"role": "tool", "content": "c", "tool_name": "tool_c"},
            {"role": "tool", "content": "d", "tool_name": "tool_d"},
        ]
        result = extract_recent_tool_names(messages, lookback=2)
        # Should get the last 2: tool_d and tool_c
        assert result == {"tool_c", "tool_d"}

    def test_handles_empty_messages(self):
        assert extract_recent_tool_names([]) == set()

    def test_skips_non_tool_messages(self):
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello"},
        ]
        assert extract_recent_tool_names(messages) == set()

    def test_skips_tool_without_tool_name(self):
        messages = [
            {"role": "tool", "content": "result"},
        ]
        assert extract_recent_tool_names(messages) == set()


# --- Layer builders (unit) ---


class TestLayerBuilders:
    def test_layer1_contains_core_rules(self):
        text = _build_layer1_identity()
        assert "Dungeon Master" in text
        assert "D&D 5e" in text
        assert "create_character" in text

    def test_layer2_combat(self):
        text = _build_layer2_jit_rules(GamePhase.COMBAT)
        assert "COMBAT" in text
        assert "initiative" in text.lower()

    def test_layer2_social(self):
        text = _build_layer2_jit_rules(GamePhase.SOCIAL)
        assert "SOCIAL" in text
        assert "talk_to_npc" in text

    def test_layer2_exploration(self):
        text = _build_layer2_jit_rules(GamePhase.EXPLORATION)
        assert "EXPLORATION" in text
        assert "look_around" in text

    def test_layer4_format(self):
        text = _build_layer4_format()
        assert "2nd person" in text
        assert "200 words" in text


# --- _build_layer3_state (DB-backed) ---


class TestBuildLayer3State:
    @pytest.fixture
    async def game_data(self, session):
        """Create a GameSession with characters, location, NPCs, and quests."""
        gs = GameSession(
            conversation_id="test-conv-1",
            world_name="Stonebane",
            environment='{"time_of_day":"day","weather":"clear","season":"summer"}',
        )
        session.add(gs)
        await session.flush()

        loc = Location(
            session_id=gs.id,
            name="The Great Hall",
            biome="dungeon",
            exits="{}",
        )
        session.add(loc)
        await session.flush()

        gs.current_location_id = loc.id

        char = Character(
            session_id=gs.id,
            name="Thorin Ironforge",
            char_class="Fighter",
            level=1,
            max_hp=10,
            current_hp=10,
            armor_class=16,
        )
        session.add(char)

        npc = NPC(
            session_id=gs.id,
            name="Griselda",
            disposition="friendly",
            location_id=loc.id,
        )
        session.add(npc)

        quest = Quest(
            session_id=gs.id,
            title="Recovery of Cursed Relics",
            status="active",
        )
        session.add(quest)
        await session.flush()

        return gs

    @pytest.mark.asyncio
    async def test_contains_world_name(self, session, game_data):
        text = await _build_layer3_state(session, game_data)
        assert "Stonebane" in text

    @pytest.mark.asyncio
    async def test_contains_location(self, session, game_data):
        text = await _build_layer3_state(session, game_data)
        assert "The Great Hall" in text
        assert "dungeon" in text

    @pytest.mark.asyncio
    async def test_contains_character_stats(self, session, game_data):
        text = await _build_layer3_state(session, game_data)
        assert "Thorin Ironforge" in text
        assert "L1 Fighter" in text
        assert "HP:10/10" in text
        assert "AC:16" in text

    @pytest.mark.asyncio
    async def test_contains_npc(self, session, game_data):
        text = await _build_layer3_state(session, game_data)
        assert "Griselda" in text
        assert "friendly" in text

    @pytest.mark.asyncio
    async def test_contains_quest(self, session, game_data):
        text = await _build_layer3_state(session, game_data)
        assert "Recovery of Cursed Relics" in text

    @pytest.mark.asyncio
    async def test_no_location_shows_unknown(self, session):
        gs = GameSession(
            conversation_id="test-conv-2",
            world_name="Voidheim",
        )
        session.add(gs)
        await session.flush()
        text = await _build_layer3_state(session, gs)
        assert "unknown" in text
        assert "Voidheim" in text

    @pytest.mark.asyncio
    async def test_empty_party(self, session):
        gs = GameSession(
            conversation_id="test-conv-3",
            world_name="Emptyland",
        )
        session.add(gs)
        await session.flush()
        text = await _build_layer3_state(session, gs)
        assert "Party: (none)" in text

    @pytest.mark.asyncio
    async def test_combat_state_shown(self, session):
        gs = GameSession(
            conversation_id="test-conv-4",
            world_name="Battleground",
            combat_state='{"turn": 1}',
        )
        session.add(gs)
        await session.flush()
        text = await _build_layer3_state(session, gs)
        assert "Combat: active" in text

    @pytest.mark.asyncio
    async def test_exits_resolved(self, session):
        gs = GameSession(
            conversation_id="test-conv-5",
            world_name="Crossroads",
        )
        session.add(gs)
        await session.flush()

        loc_a = Location(session_id=gs.id, name="Town Square", biome="town", exits="{}")
        session.add(loc_a)
        await session.flush()

        loc_b = Location(session_id=gs.id, name="Dark Forest", biome="forest", exits="{}")
        session.add(loc_b)
        await session.flush()

        loc_a.exits = json.dumps({"north": loc_b.id})
        gs.current_location_id = loc_a.id
        await session.flush()

        text = await _build_layer3_state(session, gs)
        assert "north->Dark Forest" in text


# --- build_rpg_system_prompt (integration, returns PromptResult) ---


class TestBuildRpgSystemPrompt:
    @pytest.fixture
    async def game_session(self, session):
        gs = GameSession(
            conversation_id="test-conv-integ",
            world_name="Mythrealm",
            environment='{"time_of_day":"night","weather":"rain","season":"autumn"}',
        )
        session.add(gs)
        await session.flush()

        loc = Location(session_id=gs.id, name="Rainy Tavern", biome="town", exits="{}")
        session.add(loc)
        await session.flush()

        gs.current_location_id = loc.id

        char = Character(
            session_id=gs.id,
            name="Madrigal",
            char_class="Paladin",
            level=10,
            max_hp=94,
            current_hp=94,
            armor_class=11,
        )
        session.add(char)
        await session.flush()
        return gs

    @pytest.mark.asyncio
    async def test_all_layers_present(self, session, game_session):
        result = await build_rpg_system_prompt(session, "test-conv-integ", set())
        prompt = result.prompt
        # Layer 1
        assert "Dungeon Master" in prompt
        # Layer 2 (exploration by default)
        assert "EXPLORATION" in prompt
        # Layer 3
        assert "Mythrealm" in prompt
        assert "Madrigal" in prompt
        assert "Rainy Tavern" in prompt
        # Layer 4
        assert "2nd person" in prompt

    @pytest.mark.asyncio
    async def test_combat_phase_rules(self, session, game_session):
        game_session.combat_state = '{"turn": 1}'
        await session.flush()
        result = await build_rpg_system_prompt(session, "test-conv-integ", set())
        assert "COMBAT" in result.prompt
        assert "EXPLORATION" not in result.prompt

    @pytest.mark.asyncio
    async def test_social_phase_rules(self, session, game_session):
        result = await build_rpg_system_prompt(
            session, "test-conv-integ", {"talk_to_npc"},
        )
        assert "SOCIAL" in result.prompt

    @pytest.mark.asyncio
    async def test_fallback_on_error(self, session):
        import app.services.prompt_builder as pb

        original = pb.get_or_create_session

        async def _explode(*args, **kwargs):
            raise RuntimeError("DB exploded")

        pb.get_or_create_session = _explode
        try:
            result = await build_rpg_system_prompt(session, "bad-conv", set())
            assert result.prompt == _STATIC_FALLBACK
            assert result.phase is GamePhase.EXPLORATION
        finally:
            pb.get_or_create_session = original


# --- PromptResult type (DB-backed) ---


class TestPromptResultType:
    @pytest.fixture
    async def game_session(self, session):
        gs = GameSession(
            conversation_id="test-conv-pr",
            world_name="Testworld",
        )
        session.add(gs)
        await session.flush()
        return gs

    @pytest.mark.asyncio
    async def test_returns_prompt_result(self, session, game_session):
        result = await build_rpg_system_prompt(session, "test-conv-pr", set())
        assert isinstance(result, PromptResult)
        assert isinstance(result.prompt, str)
        assert isinstance(result.phase, GamePhase)

    @pytest.mark.asyncio
    async def test_exploration_phase_by_default(self, session, game_session):
        result = await build_rpg_system_prompt(session, "test-conv-pr", set())
        assert result.phase is GamePhase.EXPLORATION

    @pytest.mark.asyncio
    async def test_combat_phase_returned(self, session, game_session):
        game_session.combat_state = '{"turn": 1}'
        await session.flush()
        result = await build_rpg_system_prompt(session, "test-conv-pr", set())
        assert result.phase is GamePhase.COMBAT

    @pytest.mark.asyncio
    async def test_fallback_returns_exploration(self, session):
        import app.services.prompt_builder as pb

        original = pb.get_or_create_session

        async def _explode(*args, **kwargs):
            raise RuntimeError("forced")

        pb.get_or_create_session = _explode
        try:
            result = await build_rpg_system_prompt(session, "bad", set())
            assert result.prompt == _STATIC_FALLBACK
            assert result.phase is GamePhase.EXPLORATION
        finally:
            pb.get_or_create_session = original


# --- Tool filtering (Phase 1.4, pure unit tests) ---


def _make_tool(name: str) -> SimpleNamespace:
    """Create a minimal mock tool with a .name attribute."""
    return SimpleNamespace(name=name)


class TestToolFiltering:
    def test_core_tools_always_included(self):
        for phase in GamePhase:
            allowed = get_phase_tool_names(phase)
            assert _CORE_TOOLS <= allowed, f"CORE tools missing in {phase}"

    def test_combat_includes_combat_tools(self):
        allowed = get_phase_tool_names(GamePhase.COMBAT)
        assert "attack" in allowed
        assert "start_combat" in allowed
        assert "death_save" in allowed

    def test_combat_excludes_world_building(self):
        allowed = get_phase_tool_names(GamePhase.COMBAT)
        assert "create_location" not in allowed
        assert "connect_locations" not in allowed

    def test_social_excludes_combat(self):
        allowed = get_phase_tool_names(GamePhase.SOCIAL)
        assert "attack" not in allowed
        assert "cast_spell" not in allowed

    def test_social_includes_npc_tools(self):
        allowed = get_phase_tool_names(GamePhase.SOCIAL)
        assert "talk_to_npc" in allowed
        assert "npc_remember" in allowed

    def test_exploration_includes_world_and_combat_start(self):
        allowed = get_phase_tool_names(GamePhase.EXPLORATION)
        assert "move_to" in allowed
        assert "start_combat" in allowed

    def test_exploration_excludes_combat_actions(self):
        allowed = get_phase_tool_names(GamePhase.EXPLORATION)
        assert "attack" not in allowed
        assert "cast_spell" not in allowed

    def test_filter_reduces_tool_list(self):
        tools = [_make_tool(n) for n in ("roll_dice", "attack", "move_to", "create_location")]
        filtered = filter_tools_by_phase(tools, GamePhase.SOCIAL)
        names = {t.name for t in filtered}
        # roll_dice is CORE, move_to is SOCIAL — both kept
        assert "roll_dice" in names
        assert "move_to" in names
        # attack and create_location are NOT in SOCIAL
        assert "attack" not in names
        assert "create_location" not in names

    def test_custom_tools_never_filtered(self):
        tools = [
            _make_tool("roll_dice"),       # RPG tool — subject to filtering
            _make_tool("my_custom_tool"),   # Non-RPG — always kept
        ]
        for phase in GamePhase:
            filtered = filter_tools_by_phase(tools, phase)
            names = {t.name for t in filtered}
            assert "my_custom_tool" in names, f"Custom tool filtered out in {phase}"

    def test_all_41_tools_covered(self):
        """Every tool in the builtin registry should be in CORE or at least one phase."""
        from app.services.builtin_tools import BUILTIN_REGISTRY

        all_phase_tools = _CORE_TOOLS.union(*_PHASE_TOOLS.values())
        for tool_name in BUILTIN_REGISTRY:
            assert tool_name in all_phase_tools, (
                f"Tool '{tool_name}' is not in CORE or any phase"
            )

    def test_phase_tool_counts(self):
        assert len(get_phase_tool_names(GamePhase.COMBAT)) == 29
        assert len(get_phase_tool_names(GamePhase.EXPLORATION)) == 32
        assert len(get_phase_tool_names(GamePhase.SOCIAL)) == 24


# --- Graph-to-context compiler (Phase 3.4) ---


class TestGraphContext:
    @pytest.fixture
    async def game_with_rels(self, session):
        """Game with characters, NPC, location, and a relationship."""
        gs = GameSession(conversation_id="test-graph", world_name="Graphland")
        session.add(gs)
        await session.flush()

        loc = Location(session_id=gs.id, name="Tavern", biome="town", exits="{}")
        session.add(loc)
        await session.flush()
        gs.current_location_id = loc.id

        char = Character(
            session_id=gs.id, name="Arin", char_class="Fighter",
            level=3, max_hp=28, current_hp=28, armor_class=16,
        )
        session.add(char)

        npc = NPC(
            session_id=gs.id, name="Grim", disposition="friendly",
            location_id=loc.id,
        )
        session.add(npc)
        await session.flush()

        rel = Relationship(
            session_id=gs.id,
            source_type="npc", source_id=npc.id,
            target_type="character", target_id=char.id,
            relationship="knows", strength=70,
        )
        session.add(rel)
        await session.flush()
        return gs

    @pytest.mark.asyncio
    async def test_relations_in_state(self, session, game_with_rels):
        text = await _build_layer3_state(session, game_with_rels)
        assert "Relations:" in text
        assert "Grim knows(70) Arin" in text

    @pytest.mark.asyncio
    async def test_low_strength_filtered(self, session, game_with_rels):
        gs = game_with_rels
        chars = (await session.execute(
            select(Character).where(Character.session_id == gs.id)
        )).scalars().all()
        npcs = (await session.execute(
            select(NPC).where(NPC.session_id == gs.id)
        )).scalars().all()
        weak = Relationship(
            session_id=gs.id,
            source_type="character", source_id=chars[0].id,
            target_type="npc", target_id=npcs[0].id,
            relationship="suspects", strength=10,
        )
        session.add(weak)
        await session.flush()
        text = await _build_layer3_state(session, gs)
        assert "suspects" not in text

    @pytest.mark.asyncio
    async def test_no_rels_no_line(self, session):
        gs = GameSession(conversation_id="test-no-rels", world_name="Empty")
        session.add(gs)
        await session.flush()
        text = await _build_layer3_state(session, gs)
        assert "Relations:" not in text

    @pytest.mark.asyncio
    async def test_disabled_via_config(self, session, game_with_rels):
        from app.config import settings
        orig = settings.graph_context_enabled
        settings.graph_context_enabled = False
        try:
            text = await _build_layer3_state(session, game_with_rels)
            assert "Relations:" not in text
        finally:
            settings.graph_context_enabled = orig
