"""RPG game-state models — D&D 5e engine integrated with sqliteRAG."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


# ---------------------------------------------------------------------------
# Campaign — groups multiple GameSessions (Phase 5.1)
# ---------------------------------------------------------------------------
class Campaign(Base):
    __tablename__ = "rpg_campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200))
    world_name: Mapped[str] = mapped_column(String(200), default="Unnamed World")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | completed
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())

    sessions: Mapped[list[GameSession]] = relationship(back_populates="campaign")


# ---------------------------------------------------------------------------
# GameSession — 1:1 with a Conversation
# ---------------------------------------------------------------------------
class GameSession(Base):
    __tablename__ = "rpg_game_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), unique=True
    )
    campaign_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("rpg_campaigns.id", ondelete="SET NULL"), nullable=True
    )
    world_name: Mapped[str] = mapped_column(String(200), default="Unnamed World")
    current_location_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    environment: Mapped[str] = mapped_column(Text, default='{"time_of_day":"day","weather":"clear","season":"summer"}')
    combat_state: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON blob when in combat
    session_number: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | ended
    session_summary: Mapped[str | None] = mapped_column(Text, nullable=True)  # LLM narrative
    session_recap: Mapped[str | None] = mapped_column(Text, nullable=True)  # "Previously on..." recap
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    campaign: Mapped[Campaign | None] = relationship(back_populates="sessions")

    characters: Mapped[list[Character]] = relationship(back_populates="game_session", cascade="all, delete-orphan")
    locations: Mapped[list[Location]] = relationship(back_populates="game_session", cascade="all, delete-orphan")
    npcs: Mapped[list[NPC]] = relationship(back_populates="game_session", cascade="all, delete-orphan")
    quests: Mapped[list[Quest]] = relationship(back_populates="game_session", cascade="all, delete-orphan")
    memories: Mapped[list[GameMemory]] = relationship(back_populates="game_session", cascade="all, delete-orphan")
    relationships: Mapped[list[Relationship]] = relationship(back_populates="game_session", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Character
# ---------------------------------------------------------------------------
class Character(Base):
    __tablename__ = "rpg_characters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("rpg_game_sessions.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    race: Mapped[str] = mapped_column(String(50), default="Human")
    char_class: Mapped[str] = mapped_column(String(50), default="Fighter")
    level: Mapped[int] = mapped_column(Integer, default=1)
    xp: Mapped[int] = mapped_column(Integer, default=0)

    # Ability scores
    strength: Mapped[int] = mapped_column(Integer, default=10)
    dexterity: Mapped[int] = mapped_column(Integer, default=10)
    constitution: Mapped[int] = mapped_column(Integer, default=10)
    intelligence: Mapped[int] = mapped_column(Integer, default=10)
    wisdom: Mapped[int] = mapped_column(Integer, default=10)
    charisma: Mapped[int] = mapped_column(Integer, default=10)

    # Combat stats
    max_hp: Mapped[int] = mapped_column(Integer, default=10)
    current_hp: Mapped[int] = mapped_column(Integer, default=10)
    temp_hp: Mapped[int] = mapped_column(Integer, default=0)
    armor_class: Mapped[int] = mapped_column(Integer, default=10)
    speed: Mapped[int] = mapped_column(Integer, default=30)

    # JSON blobs
    conditions: Mapped[str] = mapped_column(Text, default="[]")
    spell_slots: Mapped[str] = mapped_column(Text, default="{}")
    proficiencies: Mapped[str] = mapped_column(Text, default="[]")
    death_saves: Mapped[str] = mapped_column(Text, default='{"successes":0,"failures":0}')

    is_player: Mapped[bool] = mapped_column(Boolean, default=True)
    is_alive: Mapped[bool] = mapped_column(Boolean, default=True)
    location_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    game_session: Mapped[GameSession] = relationship(back_populates="characters")
    inventory_items: Mapped[list[InventoryItem]] = relationship(back_populates="character", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Item (template / definition)
# ---------------------------------------------------------------------------
class Item(Base):
    __tablename__ = "rpg_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), unique=True)
    item_type: Mapped[str] = mapped_column(String(50))  # weapon, armor, consumable, quest, scroll, misc
    description: Mapped[str] = mapped_column(Text, default="")
    weight: Mapped[float] = mapped_column(Float, default=0.0)
    value_gp: Mapped[int] = mapped_column(Integer, default=0)
    properties: Mapped[str] = mapped_column(Text, default="{}")  # JSON — damage, ac_bonus, etc.
    rarity: Mapped[str] = mapped_column(String(30), default="common")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


# ---------------------------------------------------------------------------
# InventoryItem — join between Character and Item
# ---------------------------------------------------------------------------
class InventoryItem(Base):
    __tablename__ = "rpg_inventory_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    character_id: Mapped[str] = mapped_column(String(36), ForeignKey("rpg_characters.id", ondelete="CASCADE"))
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey("rpg_items.id", ondelete="CASCADE"))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    is_equipped: Mapped[bool] = mapped_column(Boolean, default=False)

    character: Mapped[Character] = relationship(back_populates="inventory_items")
    item: Mapped[Item] = relationship()


# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------
class Location(Base):
    __tablename__ = "rpg_locations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("rpg_game_sessions.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    biome: Mapped[str] = mapped_column(String(50), default="town")
    exits: Mapped[str] = mapped_column(Text, default="{}")  # JSON {"north": location_id, ...}
    props: Mapped[str] = mapped_column(Text, default="{}")  # JSON — extra properties
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    game_session: Mapped[GameSession] = relationship(back_populates="locations")


# ---------------------------------------------------------------------------
# NPC
# ---------------------------------------------------------------------------
class NPC(Base):
    __tablename__ = "rpg_npcs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("rpg_game_sessions.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    location_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    disposition: Mapped[str] = mapped_column(String(30), default="neutral")  # hostile/unfriendly/neutral/friendly/helpful
    familiarity: Mapped[str] = mapped_column(String(30), default="stranger")  # stranger/acquaintance/friend/close_friend
    memory: Mapped[str] = mapped_column(Text, default="[]")  # JSON array of remembered events
    personality: Mapped[str] = mapped_column(Text, default="{}")  # JSON: {"traits":[], "voice":"", "motivation":"", "secrets":[]}
    backstory: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    game_session: Mapped[GameSession] = relationship(back_populates="npcs")


# ---------------------------------------------------------------------------
# Quest
# ---------------------------------------------------------------------------
class Quest(Base):
    __tablename__ = "rpg_quests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("rpg_game_sessions.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(30), default="active")  # active/completed/failed
    objectives: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    rewards: Mapped[str] = mapped_column(Text, default="{}")  # JSON — xp, gold, items
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    game_session: Mapped[GameSession] = relationship(back_populates="quests")


# ---------------------------------------------------------------------------
# GameMemory — three-tier memory for RAG-enhanced recall
# ---------------------------------------------------------------------------
class GameMemory(Base):
    __tablename__ = "game_memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("rpg_game_sessions.id", ondelete="CASCADE"))
    memory_type: Mapped[str] = mapped_column(String(20))       # procedural | episodic | semantic
    entity_type: Mapped[str | None] = mapped_column(String(20), nullable=True)  # character | location | npc | quest | item | event
    content: Mapped[str] = mapped_column(Text)
    importance_score: Mapped[float] = mapped_column(Float, default=0.5)  # 0.0 to 1.0
    session_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    entity_names: Mapped[str] = mapped_column(Text, default="[]")  # JSON array
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    last_accessed: Mapped[datetime] = mapped_column(server_default=func.now())

    game_session: Mapped[GameSession] = relationship(back_populates="memories")


# ---------------------------------------------------------------------------
# Relationship — Knowledge Graph edges (Phase 3.1)
# ---------------------------------------------------------------------------
class Relationship(Base):
    __tablename__ = "rpg_relationships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey("rpg_game_sessions.id", ondelete="CASCADE"))
    source_type: Mapped[str] = mapped_column(String(20))    # character | npc | location | quest | item
    source_id: Mapped[str] = mapped_column(String(36))
    target_type: Mapped[str] = mapped_column(String(20))
    target_id: Mapped[str] = mapped_column(String(36))

    # ORM relationship must be declared before the 'relationship' column to avoid
    # shadowing sqlalchemy.orm.relationship()
    game_session: Mapped[GameSession] = relationship(back_populates="relationships")

    relationship: Mapped[str] = mapped_column(String(50))    # knows_about, allied_with, enemy_of, etc.
    strength: Mapped[int] = mapped_column(Integer, default=50)  # 0-100
    detail: Mapped[str] = mapped_column(Text, default="{}")  # JSON extra context
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())
