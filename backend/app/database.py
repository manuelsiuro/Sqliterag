from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator

import sqlite_vec
from sqlalchemy import event, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.database_url,
    echo=False,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine.sync_engine, "connect")
def _load_sqlite_extensions(dbapi_connection, _connection_record):
    """Load sqlite-vec extension on every new connection.

    aiosqlite wraps the raw sqlite3.Connection, so we must unwrap it.
    macOS system Python may not have enable_load_extension compiled in —
    in that case we log a warning and continue without vector search.
    """
    # Unwrap: AsyncAdapt_aiosqlite_connection → aiosqlite.Connection → sqlite3.Connection
    raw_conn = getattr(dbapi_connection, "driver_connection", dbapi_connection)
    if hasattr(raw_conn, "_conn"):
        raw_conn = raw_conn._conn

    if not hasattr(raw_conn, "enable_load_extension"):
        logger.warning(
            "sqlite3.Connection lacks enable_load_extension — "
            "sqlite-vec will NOT be loaded. Use Homebrew or pyenv Python for full support."
        )
        return

    raw_conn.enable_load_extension(True)
    sqlite_vec.load(raw_conn)
    raw_conn.enable_load_extension(False)
    logger.info("sqlite-vec extension loaded")


async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession]:
    async with async_session_factory() as session:
        yield session


async def init_db() -> None:
    """Create ORM tables and the vec0 virtual table."""
    from app.models import Base  # noqa: F811

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            await conn.execute(
                text(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks "
                    "USING vec0(embedding float[768])"
                )
            )
        except Exception:
            logger.warning(
                "Could not create vec_chunks table — "
                "vector search will be unavailable until sqlite-vec is loaded",
                exc_info=True,
            )
        try:
            await conn.execute(
                text(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS vec_memories "
                    "USING vec0(embedding float[768])"
                )
            )
        except Exception:
            logger.warning(
                "Could not create vec_memories table — "
                "memory embeddings will be unavailable until sqlite-vec is loaded",
                exc_info=True,
            )

        # Mapping table: vec_memories rowid ↔ GameMemory UUID (Phase 2.3)
        try:
            await conn.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS vec_memory_map ("
                    "rowid INTEGER PRIMARY KEY AUTOINCREMENT, "
                    "memory_id TEXT NOT NULL UNIQUE)"
                )
            )
        except Exception:
            logger.warning(
                "Could not create vec_memory_map table",
                exc_info=True,
            )

        # FTS5 full-text index for game memories (standalone, synced via memory_service)
        try:
            await conn.execute(
                text(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS fts_memories "
                    "USING fts5(content, entity_names, memory_id UNINDEXED)"
                )
            )
        except Exception:
            logger.warning(
                "Could not create fts_memories table — "
                "full-text search for game memories will be unavailable",
                exc_info=True,
            )

        # Indexes for metadata-enhanced retrieval (Phase 2.7)
        for idx_name, idx_col in [
            ("idx_game_memories_memory_type", "memory_type"),
            ("idx_game_memories_entity_type", "entity_type"),
            ("idx_game_memories_session_number", "session_number"),
        ]:
            try:
                await conn.execute(text(
                    f"CREATE INDEX IF NOT EXISTS {idx_name} ON game_memories({idx_col})"
                ))
            except Exception:
                pass

        # Indexes for knowledge graph (Phase 3.1)
        for idx_name, idx_cols in [
            ("idx_rel_source", "session_id, source_type, source_id"),
            ("idx_rel_target", "session_id, target_type, target_id"),
            ("idx_rel_type", "session_id, relationship"),
        ]:
            try:
                await conn.execute(text(
                    f"CREATE INDEX IF NOT EXISTS {idx_name} ON rpg_relationships({idx_cols})"
                ))
            except Exception:
                pass

        # Drop orphaned rpg_chronicle table (superseded by game_memories)
        try:
            await conn.execute(text("DROP TABLE IF EXISTS rpg_chronicle"))
        except Exception:
            pass

        await _migrate_messages_table(conn)
        await _migrate_game_sessions_table(conn)
        await _migrate_campaigns_table(conn)

    # If fts_memories is empty but game_memories has rows, rebuild the FTS index
    await _sync_fts_on_startup()
    await _warn_vec_on_startup()

    await seed_builtin_tools()
    logger.info("Database initialized")


async def _migrate_game_sessions_table(conn) -> None:
    """Add columns introduced in Phase 2.6 (idempotent)."""
    columns_to_add = [
        ("session_number", "INTEGER DEFAULT 1"),
        ("status", "VARCHAR(20) DEFAULT 'active'"),
        ("session_summary", "TEXT"),
    ]
    for col_name, col_type in columns_to_add:
        try:
            await conn.execute(
                text(f"ALTER TABLE rpg_game_sessions ADD COLUMN {col_name} {col_type}")
            )
            logger.info("Added column rpg_game_sessions.%s", col_name)
        except Exception:
            pass  # Column already exists


async def _migrate_campaigns_table(conn) -> None:
    """Add campaign_id column to rpg_game_sessions (Phase 5.1, idempotent)."""
    try:
        await conn.execute(
            text("ALTER TABLE rpg_game_sessions ADD COLUMN campaign_id VARCHAR(36) REFERENCES rpg_campaigns(id) ON DELETE SET NULL")
        )
        logger.info("Added column rpg_game_sessions.campaign_id")
    except Exception:
        pass  # Column already exists
    try:
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_gamesession_campaign ON rpg_game_sessions(campaign_id)"
        ))
    except Exception:
        pass


async def _migrate_messages_table(conn) -> None:
    """Add columns introduced after initial schema (idempotent)."""
    columns_to_add = [
        ("tool_calls", "TEXT"),
        ("tool_name", "VARCHAR(100)"),
    ]
    for col_name, col_type in columns_to_add:
        try:
            await conn.execute(text(f"ALTER TABLE messages ADD COLUMN {col_name} {col_type}"))
            logger.info("Added column messages.%s", col_name)
        except Exception:
            # Column already exists — expected on subsequent starts
            pass


async def _sync_fts_on_startup() -> None:
    """If fts_memories is empty but game_memories has rows, rebuild the FTS index."""
    try:
        async with async_session_factory() as session:
            fts_count = (
                await session.execute(
                    text("SELECT COUNT(*) FROM fts_memories")
                )
            ).scalar() or 0
            if fts_count > 0:
                return
            mem_count = (
                await session.execute(
                    text("SELECT COUNT(*) FROM game_memories")
                )
            ).scalar() or 0
            if mem_count == 0:
                return
            # Populate FTS from existing game_memories
            await session.execute(
                text(
                    "INSERT INTO fts_memories(content, entity_names, memory_id) "
                    "SELECT content, entity_names, id FROM game_memories"
                )
            )
            await session.commit()
            logger.info("Rebuilt fts_memories index from %d existing game memories", mem_count)
    except Exception:
        logger.warning("Could not sync fts_memories on startup", exc_info=True)


async def _warn_vec_on_startup() -> None:
    """Warn if game_memories exist but vec_memory_map is empty (needs rebuild)."""
    try:
        async with async_session_factory() as session:
            vec_count = (
                await session.execute(text("SELECT COUNT(*) FROM vec_memory_map"))
            ).scalar() or 0
            if vec_count > 0:
                return
            mem_count = (
                await session.execute(text("SELECT COUNT(*) FROM game_memories"))
            ).scalar() or 0
            if mem_count > 0:
                logger.warning(
                    "%d game memories exist but vec_memory_map is empty — "
                    "run rebuild_vec_index() to enable vector search",
                    mem_count,
                )
    except Exception:
        logger.warning("Could not check vec_memory_map on startup", exc_info=True)


def _schema(required: list[str], properties: dict) -> str:
    return json.dumps({"type": "object", "required": required, "properties": properties})


def _config(fn: str) -> str:
    return json.dumps({"function_name": fn})


def _builtin_tool_defs() -> dict[str, dict]:
    """All built-in tool definitions for seeding."""
    return {
        # ── Original ──────────────────────────────────────────────
        "roll_d20": {
            "description": "Roll one or more 20-sided dice (d20) with an optional modifier.",
            "parameters_schema": _schema([], {
                "modifier": {"type": "integer", "description": "Flat number added to the total."},
                "num_dice": {"type": "integer", "description": "How many d20 dice to roll (default 1)."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("roll_d20"),
        },

        # ── Phase 1: Dice & Math ─────────────────────────────────
        "roll_dice": {
            "description": (
                "Roll dice using full D&D notation. Supports XdY, +/-N, kh/kl (keep highest/lowest), "
                "dh/dl (drop), r<N (reroll), ! (exploding). Examples: '2d6+3', '4d6kh3', '1d20!'."
            ),
            "parameters_schema": _schema(["notation"], {
                "notation": {"type": "string", "description": "Dice notation (e.g. '2d6+3', '4d6kh3', '1d8!')."},
                "label": {"type": "string", "description": "Optional label for the roll (e.g. 'Damage', 'Initiative')."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("roll_dice"),
        },
        "roll_check": {
            "description": "Roll a D&D 5e ability check: d20 + ability modifier vs a Difficulty Class (DC). Supports advantage/disadvantage.",
            "parameters_schema": _schema(["character_name", "ability"], {
                "character_name": {"type": "string", "description": "Name of the character making the check."},
                "ability": {"type": "string", "description": "Ability to use (strength, dexterity, constitution, intelligence, wisdom, charisma)."},
                "dc": {"type": "integer", "description": "Difficulty Class (default 10)."},
                "advantage": {"type": "boolean", "description": "Roll with advantage (roll 2d20, take highest)."},
                "disadvantage": {"type": "boolean", "description": "Roll with disadvantage (roll 2d20, take lowest)."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("roll_check"),
        },
        "roll_save": {
            "description": "Roll a D&D 5e saving throw: d20 + ability modifier vs DC.",
            "parameters_schema": _schema(["character_name", "ability"], {
                "character_name": {"type": "string", "description": "Name of the character."},
                "ability": {"type": "string", "description": "Ability for the save."},
                "dc": {"type": "integer", "description": "Difficulty Class (default 10)."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("roll_save"),
        },

        # ── Phase 2: Character Management ────────────────────────
        "create_character": {
            "description": "Create a D&D 5e character with race, class, level, and ability scores. Auto-calculates HP, AC, modifiers.",
            "parameters_schema": _schema(["name"], {
                "name": {"type": "string", "description": "Character name."},
                "race": {"type": "string", "description": "Race (e.g. Human, Elf, Dwarf). Default: Human."},
                "char_class": {"type": "string", "description": "Class (e.g. Fighter, Wizard, Rogue). Default: Fighter."},
                "level": {"type": "integer", "description": "Starting level (1-20). Default: 1."},
                "strength": {"type": "integer", "description": "Strength score (default 10)."},
                "dexterity": {"type": "integer", "description": "Dexterity score (default 10)."},
                "constitution": {"type": "integer", "description": "Constitution score (default 10)."},
                "intelligence": {"type": "integer", "description": "Intelligence score (default 10)."},
                "wisdom": {"type": "integer", "description": "Wisdom score (default 10)."},
                "charisma": {"type": "integer", "description": "Charisma score (default 10)."},
                "is_player": {"type": "boolean", "description": "True for player characters, false for NPCs/monsters. Default: true."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("create_character"),
        },
        "get_character": {
            "description": "Get a character's full sheet: stats, HP, AC, conditions, abilities.",
            "parameters_schema": _schema(["name"], {
                "name": {"type": "string", "description": "Character name."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("get_character"),
        },
        "update_character": {
            "description": "Update a character: adjust HP, add/remove conditions, grant XP (auto-levels up), set AC.",
            "parameters_schema": _schema(["name"], {
                "name": {"type": "string", "description": "Character name."},
                "hp_change": {"type": "integer", "description": "HP change (positive to heal, negative to damage)."},
                "add_condition": {"type": "string", "description": "Add a condition (e.g. poisoned, blinded, charmed)."},
                "remove_condition": {"type": "string", "description": "Remove a condition."},
                "add_xp": {"type": "integer", "description": "XP to grant. Auto-levels up when threshold reached."},
                "set_armor_class": {"type": "integer", "description": "Override armor class value."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("update_character"),
        },
        "list_characters": {
            "description": "List all characters in the current RPG game session.",
            "parameters_schema": _schema([], {}),
            "execution_type": "builtin",
            "execution_config": _config("list_characters"),
        },

        # ── Phase 3: Combat System ───────────────────────────────
        "start_combat": {
            "description": "Start a combat encounter. Rolls initiative for all named combatants and establishes turn order.",
            "parameters_schema": _schema(["combatant_names"], {
                "combatant_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of character names participating in combat.",
                },
            }),
            "execution_type": "builtin",
            "execution_config": _config("start_combat"),
        },
        "get_combat_status": {
            "description": "Get current combat state: turn order, HP, conditions, whose turn it is.",
            "parameters_schema": _schema([], {}),
            "execution_type": "builtin",
            "execution_config": _config("get_combat_status"),
        },
        "next_turn": {
            "description": "Advance to the next combatant's turn in initiative order.",
            "parameters_schema": _schema([], {}),
            "execution_type": "builtin",
            "execution_config": _config("next_turn"),
        },
        "end_combat": {
            "description": "End the current combat encounter.",
            "parameters_schema": _schema([], {}),
            "execution_type": "builtin",
            "execution_config": _config("end_combat"),
        },
        "attack": {
            "description": "Make a melee or ranged attack: d20 + modifier + proficiency vs target AC. Rolls damage on hit.",
            "parameters_schema": _schema(["attacker", "target"], {
                "attacker": {"type": "string", "description": "Attacking character name."},
                "target": {"type": "string", "description": "Target character name."},
                "weapon": {"type": "string", "description": "Weapon name (default: unarmed)."},
                "advantage": {"type": "boolean", "description": "Attack with advantage."},
                "disadvantage": {"type": "boolean", "description": "Attack with disadvantage."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("attack"),
        },
        "cast_spell": {
            "description": "Cast a spell from the SRD spell list. Consumes a spell slot, applies damage/healing/effects.",
            "parameters_schema": _schema(["caster", "spell_name"], {
                "caster": {"type": "string", "description": "Casting character name."},
                "spell_name": {"type": "string", "description": "Spell name (e.g. 'fireball', 'cure_wounds', 'magic_missile')."},
                "target": {"type": "string", "description": "Target character name (if applicable)."},
                "level": {"type": "integer", "description": "Spell slot level to use (default: spell's base level)."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("cast_spell"),
        },
        "heal": {
            "description": "Heal a character by a flat HP amount or by casting a healing spell.",
            "parameters_schema": _schema(["healer", "target"], {
                "healer": {"type": "string", "description": "Character providing healing."},
                "target": {"type": "string", "description": "Character receiving healing."},
                "amount": {"type": "integer", "description": "Flat HP to restore (if not using a spell)."},
                "spell": {"type": "string", "description": "Healing spell name (e.g. 'cure_wounds')."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("heal"),
        },
        "take_damage": {
            "description": "Apply damage to a character. Triggers death saves if HP drops to 0.",
            "parameters_schema": _schema(["character", "damage"], {
                "character": {"type": "string", "description": "Character taking damage."},
                "damage": {"type": "integer", "description": "Amount of damage."},
                "damage_type": {"type": "string", "description": "Damage type (e.g. fire, slashing, necrotic). Default: bludgeoning."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("take_damage"),
        },
        "death_save": {
            "description": "Roll a death saving throw for a character at 0 HP. 10+ = success, <10 = failure. 3 successes = stabilize, 3 failures = death. Nat 20 = regain 1 HP.",
            "parameters_schema": _schema(["character"], {
                "character": {"type": "string", "description": "Character at 0 HP."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("death_save"),
        },
        "combat_action": {
            "description": "Perform a non-attack combat action: dodge, dash, disengage, help, or hide.",
            "parameters_schema": _schema(["character", "action"], {
                "character": {"type": "string", "description": "Acting character name."},
                "action": {"type": "string", "description": "Action to take (dodge, dash, disengage, help, hide)."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("combat_action"),
        },

        # ── Phase 4: Inventory & Items ───────────────────────────
        "create_item": {
            "description": "Create a new item template (weapon, armor, consumable, quest item, etc.).",
            "parameters_schema": _schema(["name", "item_type"], {
                "name": {"type": "string", "description": "Item name (e.g. 'Longsword', 'Healing Potion')."},
                "item_type": {"type": "string", "description": "Type: weapon, armor, consumable, quest, scroll, misc."},
                "description": {"type": "string", "description": "Item description."},
                "weight": {"type": "number", "description": "Weight in pounds."},
                "value_gp": {"type": "integer", "description": "Value in gold pieces."},
                "properties": {"type": "string", "description": "JSON properties (e.g. damage, ac bonus)."},
                "rarity": {"type": "string", "description": "Rarity: common, uncommon, rare, very_rare, legendary."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("create_item"),
        },
        "give_item": {
            "description": "Give an item to a character's inventory.",
            "parameters_schema": _schema(["character", "item_name"], {
                "character": {"type": "string", "description": "Character receiving the item."},
                "item_name": {"type": "string", "description": "Name of the item to give."},
                "quantity": {"type": "integer", "description": "How many to give (default 1)."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("give_item"),
        },
        "equip_item": {
            "description": "Equip an item from a character's inventory. Updates AC for armor.",
            "parameters_schema": _schema(["character", "item_name"], {
                "character": {"type": "string", "description": "Character name."},
                "item_name": {"type": "string", "description": "Item to equip."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("equip_item"),
        },
        "unequip_item": {
            "description": "Unequip an item. Resets AC if it was armor.",
            "parameters_schema": _schema(["character", "item_name"], {
                "character": {"type": "string", "description": "Character name."},
                "item_name": {"type": "string", "description": "Item to unequip."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("unequip_item"),
        },
        "get_inventory": {
            "description": "View a character's full inventory with weight, capacity, and equipped items.",
            "parameters_schema": _schema(["character"], {
                "character": {"type": "string", "description": "Character name."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("get_inventory"),
        },
        "transfer_item": {
            "description": "Transfer items from one character to another.",
            "parameters_schema": _schema(["from_character", "to_character", "item_name"], {
                "from_character": {"type": "string", "description": "Character giving the item."},
                "to_character": {"type": "string", "description": "Character receiving the item."},
                "item_name": {"type": "string", "description": "Item to transfer."},
                "quantity": {"type": "integer", "description": "How many to transfer (default 1)."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("transfer_item"),
        },

        # ── Phase 5: World & Spatial ─────────────────────────────
        "create_location": {
            "description": "Create a new location in the game world with a name, description, and biome.",
            "parameters_schema": _schema(["name"], {
                "name": {"type": "string", "description": "Location name."},
                "description": {"type": "string", "description": "Location description."},
                "biome": {"type": "string", "description": "Biome type (e.g. town, forest, dungeon, cave, mountain)."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("create_location"),
        },
        "connect_locations": {
            "description": "Create a bidirectional link between two locations (e.g. north/south).",
            "parameters_schema": _schema(["location1", "location2", "direction"], {
                "location1": {"type": "string", "description": "First location name."},
                "location2": {"type": "string", "description": "Second location name."},
                "direction": {"type": "string", "description": "Direction from location1 to location2 (north, south, east, west, up, down)."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("connect_locations"),
        },
        "move_to": {
            "description": "Move a character to a new location by direction or location name.",
            "parameters_schema": _schema(["character"], {
                "character": {"type": "string", "description": "Character to move."},
                "direction": {"type": "string", "description": "Direction to move (north, south, east, west, up, down)."},
                "location_name": {"type": "string", "description": "Or move directly to a named location."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("move_to"),
        },
        "look_around": {
            "description": "Describe the current location: exits, characters present, NPCs, and environment.",
            "parameters_schema": _schema([], {}),
            "execution_type": "builtin",
            "execution_config": _config("look_around"),
        },
        "set_environment": {
            "description": "Update the game world's environment: time of day, weather, and season.",
            "parameters_schema": _schema([], {
                "time_of_day": {"type": "string", "description": "Time (dawn, morning, noon, afternoon, dusk, evening, night, midnight)."},
                "weather": {"type": "string", "description": "Weather (clear, cloudy, rain, storm, snow, fog, wind)."},
                "season": {"type": "string", "description": "Season (spring, summer, autumn, winter)."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("set_environment"),
        },

        # ── Phase 6: NPC System ──────────────────────────────────
        "create_npc": {
            "description": "Create a new NPC with a name, description, location, and disposition.",
            "parameters_schema": _schema(["name"], {
                "name": {"type": "string", "description": "NPC name."},
                "description": {"type": "string", "description": "NPC description and personality."},
                "location": {"type": "string", "description": "Location name where the NPC is placed."},
                "disposition": {"type": "string", "description": "Attitude: hostile, unfriendly, neutral, friendly, helpful. Default: neutral."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("create_npc"),
        },
        "talk_to_npc": {
            "description": "Initiate conversation with an NPC. Returns their context, memories, and roleplay guidance.",
            "parameters_schema": _schema(["npc_name"], {
                "npc_name": {"type": "string", "description": "NPC to talk to."},
                "topic": {"type": "string", "description": "Conversation topic or question."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("talk_to_npc"),
        },
        "update_npc_relationship": {
            "description": "Change an NPC's disposition (hostile→helpful) or familiarity (stranger→close_friend).",
            "parameters_schema": _schema(["npc_name"], {
                "npc_name": {"type": "string", "description": "NPC name."},
                "character": {"type": "string", "description": "Player character interacting with NPC."},
                "disposition_change": {"type": "string", "description": "New disposition: hostile, unfriendly, neutral, friendly, helpful."},
                "familiarity_change": {"type": "string", "description": "New familiarity: stranger, acquaintance, friend, close_friend."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("update_npc_relationship"),
        },
        "npc_remember": {
            "description": "Record an event or fact in an NPC's memory for future interactions.",
            "parameters_schema": _schema(["npc_name", "event"], {
                "npc_name": {"type": "string", "description": "NPC name."},
                "event": {"type": "string", "description": "Event or fact to remember."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("npc_remember"),
        },

        # ── Phase 7: Quest System ────────────────────────────────
        "create_quest": {
            "description": "Create a new quest with title, description, objectives, and rewards.",
            "parameters_schema": _schema(["title"], {
                "title": {"type": "string", "description": "Quest title."},
                "description": {"type": "string", "description": "Quest description."},
                "objectives": {"type": "string", "description": 'JSON array of objectives (e.g. \'[{"text":"Find the sword","completed":false}]\').'},
                "rewards": {"type": "string", "description": 'JSON rewards (e.g. \'{"xp":100,"gold":50}\').'},
            }),
            "execution_type": "builtin",
            "execution_config": _config("create_quest"),
        },
        "update_quest_objective": {
            "description": "Mark a quest objective as completed or incomplete by index.",
            "parameters_schema": _schema(["quest_title", "objective_index"], {
                "quest_title": {"type": "string", "description": "Quest title."},
                "objective_index": {"type": "integer", "description": "0-based index of the objective."},
                "completed": {"type": "boolean", "description": "True to mark complete, false to undo. Default: true."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("update_quest_objective"),
        },
        "complete_quest": {
            "description": "Complete a quest and distribute rewards (XP, gold) to all player characters.",
            "parameters_schema": _schema(["quest_title"], {
                "quest_title": {"type": "string", "description": "Quest title to complete."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("complete_quest"),
        },
        "get_quest_journal": {
            "description": "View all quests organized by status: active, completed, and failed.",
            "parameters_schema": _schema([], {}),
            "execution_type": "builtin",
            "execution_config": _config("get_quest_journal"),
        },

        # ── Phase 8: Rest & Recovery ─────────────────────────────
        "short_rest": {
            "description": "Take a short rest: spend hit dice to heal HP.",
            "parameters_schema": _schema(["character"], {
                "character": {"type": "string", "description": "Character taking the short rest."},
                "hit_dice_to_spend": {"type": "integer", "description": "Number of hit dice to spend for healing (default 1)."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("short_rest"),
        },
        "long_rest": {
            "description": "Take a long rest: restore full HP, recover spell slots, reset death saves, remove unconscious.",
            "parameters_schema": _schema(["character"], {
                "character": {"type": "string", "description": "Character taking the long rest."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("long_rest"),
        },

        # ── Phase 9: Session Management ──────────────────────────
        "init_game_session": {
            "description": "Initialize a new RPG game session or resume an existing one for this conversation.",
            "parameters_schema": _schema([], {
                "world_name": {"type": "string", "description": "Name of the game world (default: 'The Realm')."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("init_game_session"),
        },
        "get_game_state": {
            "description": "Get the full RPG game state: all characters, current location, active quests, NPCs, combat status, and environment.",
            "parameters_schema": _schema([], {}),
            "execution_type": "builtin",
            "execution_config": _config("get_game_state"),
        },

        # ── Phase 10: Memory Management ─────────────────────────
        "archive_event": {
            "description": "Record a significant story event into long-term game memory for future recall. Use for important plot points, discoveries, battles, and character moments.",
            "parameters_schema": _schema(["description"], {
                "description": {"type": "string", "description": "Description of the event to remember."},
                "importance": {"type": "integer", "description": "Importance level 1-10 (1=trivial, 10=critical). Default: 5."},
                "entity_names": {"type": "string", "description": "Comma-separated names of entities involved (characters, locations, items)."},
                "memory_type": {"type": "string", "description": "Memory category: episodic (events), semantic (facts/lore), procedural (rules/tactics). Default: episodic."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("archive_event"),
        },
        "search_memory": {
            "description": "Search long-term game memory for past events, facts, or knowledge. Supports filtering by memory type, entity type, and session range.",
            "parameters_schema": _schema(["query"], {
                "query": {"type": "string", "description": "Search query describing what to recall."},
                "memory_type": {"type": "string", "description": "Filter by memory type: episodic, semantic, procedural, summary. Comma-separated for multiple. Empty for all."},
                "entity_type": {"type": "string", "description": "Filter by entity type: character, location, npc, quest, item, event. Comma-separated for multiple. Empty for all."},
                "session_range": {"type": "string", "description": "Filter by session number: 'N' for single session, 'N-M' for range. Empty for all."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("search_memory"),
        },
        "get_session_summary": {
            "description": "Get a narrative summary of the current game session. Returns an LLM-generated narrative if available, or generates one on demand.",
            "parameters_schema": _schema([], {
                "session_number": {"type": "integer", "description": "Session number to summarize (default: current session)."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("get_session_summary"),
        },
        "recall_context": {
            "description": "Search recall storage for evicted conversation context. Use this when you need to remember something from earlier in the conversation that was archived due to context limits.",
            "parameters_schema": _schema(["query"], {
                "query": {"type": "string", "description": "Search query describing what to recall from earlier conversation."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("recall_context"),
        },
        "end_session": {
            "description": "End the current game session. Generates a narrative summary of the session, archives it to memory, and marks the session as ended.",
            "parameters_schema": _schema([], {
                "summary_override": {"type": "string", "description": "Optional custom summary text. If provided, skips LLM generation."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("end_session"),
        },

        # ── Phase 12: Campaign Persistence ────────────────────────
        "start_campaign": {
            "description": "Start a new campaign to persist characters, locations, NPCs, and quests across multiple sessions. Links the current session to the campaign.",
            "parameters_schema": _schema(["campaign_name"], {
                "campaign_name": {"type": "string", "description": "Name of the campaign (e.g. 'Shadows of Eldenhollow')."},
                "world_name": {"type": "string", "description": "World name for the campaign. Defaults to current world name."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("start_campaign"),
        },
        "list_campaigns": {
            "description": "List all available campaigns with their status and session count.",
            "parameters_schema": _schema([], {}),
            "execution_type": "builtin",
            "execution_config": _config("list_campaigns"),
        },

        # ── Phase 11: Knowledge Graph ───────────────────────────
        "add_relationship": {
            "description": "Create or update a relationship between two game entities (characters, NPCs, locations, quests, items). Tracks social bonds, spatial connections, quest involvement, ownership, and knowledge.",
            "parameters_schema": _schema(["source_name", "source_type", "target_name", "target_type", "relationship"], {
                "source_name": {"type": "string", "description": "Name of the source entity"},
                "source_type": {"type": "string", "description": "Type: character, npc, location, quest, or item"},
                "target_name": {"type": "string", "description": "Name of the target entity"},
                "target_type": {"type": "string", "description": "Type: character, npc, location, quest, or item"},
                "relationship": {"type": "string", "description": "Relationship: knows_about, allied_with, enemy_of, fears, trusts, located_at, quest_giver, owns, guards, seeks, etc."},
                "strength": {"type": "integer", "description": "Strength 0-100 (default 50). 0=weak, 100=defining"},
            }),
            "execution_type": "builtin",
            "execution_config": _config("add_relationship"),
        },
        "query_relationships": {
            "description": "Query the relationship graph for an entity. Returns connections up to 3 hops deep. Use to understand who knows what and how entities relate.",
            "parameters_schema": _schema(["entity_name"], {
                "entity_name": {"type": "string", "description": "Name of the entity to query"},
                "entity_type": {"type": "string", "description": "Type: character, npc, location, quest, item. Auto-detected if empty."},
                "relationship_filter": {"type": "string", "description": "Filter by relationship type. Empty for all."},
                "depth": {"type": "integer", "description": "Traversal depth: 1=direct, 2=two-hop, 3=three-hop. Default 1."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("query_relationships"),
        },
        "get_entity_relationships": {
            "description": "Get a compact summary of an entity's direct relationships. Simpler than query_relationships.",
            "parameters_schema": _schema(["entity_name"], {
                "entity_name": {"type": "string", "description": "Name of the entity"},
                "entity_type": {"type": "string", "description": "Type: character, npc, location, quest, item. Auto-detected if empty."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("get_entity_relationships"),
        },
        "get_entity_context": {
            "description": "Get a comprehensive context summary for any game entity. Compiles the entity's database record, knowledge graph relationships, and relevant memories into a single view. Use to understand everything known about a character, NPC, location, quest, or item.",
            "parameters_schema": _schema(["entity_name"], {
                "entity_name": {"type": "string", "description": "Name of the entity to look up"},
                "entity_type": {"type": "string", "description": "Type: character, npc, location, quest, item. Auto-detected if empty."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("get_entity_context"),
        },
        "find_connections": {
            "description": "Find connections between entities in the knowledge graph. With one entity: discovers everything connected within N hops. With two entities: finds all paths connecting them. Use for 'who knows about X?', 'how is A connected to B?'.",
            "parameters_schema": _schema(["entity_name"], {
                "entity_name": {"type": "string", "description": "Starting entity name"},
                "target_name": {"type": "string", "description": "Target entity name. If provided, finds paths between source and target."},
                "entity_type": {"type": "string", "description": "Source type: character, npc, location, quest, item. Auto-detected if empty."},
                "target_type": {"type": "string", "description": "Target type. Auto-detected if empty."},
                "max_depth": {"type": "integer", "description": "Max traversal depth 1-3 (default 3)."},
                "relationship_filter": {"type": "string", "description": "Filter by relationship type. Empty for all."},
            }),
            "execution_type": "builtin",
            "execution_config": _config("find_connections"),
        },
    }


async def seed_builtin_tools() -> None:
    """Insert or update built-in tools (idempotent)."""
    from app.models.tool import Tool

    builtin_defs = _builtin_tool_defs()

    async with async_session_factory() as session:
        for name, defn in builtin_defs.items():
            result = await session.execute(select(Tool).where(Tool.name == name))
            existing = result.scalars().first()

            if existing is None:
                tool = Tool(name=name, is_enabled=True, **defn)
                session.add(tool)
                logger.info("Seeded built-in tool: %s", name)
            else:
                existing.execution_type = defn["execution_type"]
                existing.execution_config = defn["execution_config"]
                existing.description = defn["description"]
                existing.parameters_schema = defn["parameters_schema"]
                logger.info("Updated built-in tool: %s", name)

        await session.commit()
