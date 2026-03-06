"""Built-in tool implementations that ship with the app.

Organized by category:
  dice       -- Phase 0-1: Dice rolling and checks
  characters -- Phase 2:   Character CRUD
  combat     -- Phase 3:   Combat system
  inventory  -- Phase 4:   Items and inventory
  world      -- Phase 5:   Locations and spatial
  npcs       -- Phase 6:   NPC interactions
  quests     -- Phase 7:   Quest system
  rest       -- Phase 8:   Rest and recovery
  session    -- Phase 9:   Game session management
"""

from app.services.builtin_tools.characters import (
    create_character,
    get_character,
    list_characters,
    update_character,
)
from app.services.builtin_tools.combat import (
    attack,
    cast_spell,
    combat_action,
    death_save,
    end_combat,
    get_combat_status,
    heal,
    next_turn,
    start_combat,
    take_damage,
)
from app.services.builtin_tools.dice import roll_check, roll_d20, roll_dice, roll_save
from app.services.builtin_tools.inventory import (
    create_item,
    equip_item,
    get_inventory,
    give_item,
    transfer_item,
    unequip_item,
)
from app.services.builtin_tools.npcs import (
    create_npc,
    npc_remember,
    talk_to_npc,
    update_npc_relationship,
)
from app.services.builtin_tools.quests import (
    complete_quest,
    create_quest,
    get_quest_journal,
    update_quest_objective,
)
from app.services.builtin_tools.relationships import (
    add_relationship,
    find_connections,
    get_entity_context,
    get_entity_relationships,
    query_relationships,
)
from app.services.builtin_tools.encounters import (
    award_xp,
    balance_encounter,
    generate_monster,
)
from app.services.builtin_tools.rest import long_rest, short_rest
from app.services.builtin_tools.memory import archive_event, end_session, get_session_summary, recall_context, search_memory
from app.services.builtin_tools.session import get_game_state, init_game_session, list_campaigns_tool, start_campaign
from app.services.builtin_tools.world import (
    connect_locations,
    create_location,
    look_around,
    move_to,
    set_environment,
)

BUILTIN_REGISTRY: dict[str, callable] = {
    # Phase 0 — Original
    "roll_d20": roll_d20,
    # Phase 1 — Dice
    "roll_dice": roll_dice,
    "roll_check": roll_check,
    "roll_save": roll_save,
    # Phase 2 — Characters
    "create_character": create_character,
    "get_character": get_character,
    "update_character": update_character,
    "list_characters": list_characters,
    # Phase 3 — Combat
    "start_combat": start_combat,
    "get_combat_status": get_combat_status,
    "next_turn": next_turn,
    "end_combat": end_combat,
    "attack": attack,
    "cast_spell": cast_spell,
    "heal": heal,
    "take_damage": take_damage,
    "death_save": death_save,
    "combat_action": combat_action,
    # Phase 4 — Inventory
    "create_item": create_item,
    "give_item": give_item,
    "equip_item": equip_item,
    "unequip_item": unequip_item,
    "get_inventory": get_inventory,
    "transfer_item": transfer_item,
    # Phase 5 — World
    "create_location": create_location,
    "connect_locations": connect_locations,
    "move_to": move_to,
    "look_around": look_around,
    "set_environment": set_environment,
    # Phase 6 — NPCs
    "create_npc": create_npc,
    "talk_to_npc": talk_to_npc,
    "update_npc_relationship": update_npc_relationship,
    "npc_remember": npc_remember,
    # Phase 7 — Quests
    "create_quest": create_quest,
    "update_quest_objective": update_quest_objective,
    "complete_quest": complete_quest,
    "get_quest_journal": get_quest_journal,
    # Phase 8 — Rest
    "short_rest": short_rest,
    "long_rest": long_rest,
    # Phase 9 — Session
    "init_game_session": init_game_session,
    "get_game_state": get_game_state,
    "start_campaign": start_campaign,
    "list_campaigns": list_campaigns_tool,
    # Phase 10 — Memory
    "archive_event": archive_event,
    "search_memory": search_memory,
    "recall_context": recall_context,
    "get_session_summary": get_session_summary,
    "end_session": end_session,
    # Phase 11 — Knowledge Graph
    "add_relationship": add_relationship,
    "query_relationships": query_relationships,
    "get_entity_relationships": get_entity_relationships,
    "get_entity_context": get_entity_context,
    "find_connections": find_connections,
    # Phase 14 — Encounter Balancing
    "balance_encounter": balance_encounter,
    "generate_monster": generate_monster,
    "award_xp": award_xp,
}
