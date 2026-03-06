export {
  tryParseToolResult,
  getToolRenderer,
  registerToolRenderer,
} from "./toolRendererRegistry";
export type {
  StructuredToolResult,
  ToolRendererProps,
} from "./toolRendererRegistry";

import { registerToolRenderer } from "./toolRendererRegistry";

// Phase 0 — Original
import { DiceResultRenderer } from "./DiceResultRenderer";
registerToolRenderer("roll_d20", DiceResultRenderer);

// Phase 1 — Dice & Math
import { DiceRollRenderer } from "./DiceRollRenderer";
import { CheckResultRenderer } from "./CheckResultRenderer";
registerToolRenderer("roll_dice", DiceRollRenderer);
registerToolRenderer("check_result", CheckResultRenderer);

// Phase 2 — Characters
import { CharacterSheetRenderer } from "./CharacterSheetRenderer";
import { CharacterListRenderer } from "./CharacterListRenderer";
registerToolRenderer("character_sheet", CharacterSheetRenderer);
registerToolRenderer("character_list", CharacterListRenderer);

// Phase 3 — Combat
import { InitiativeOrderRenderer } from "./InitiativeOrderRenderer";
import { AttackResultRenderer } from "./AttackResultRenderer";
import { SpellCastRenderer } from "./SpellCastRenderer";
import { DeathSaveRenderer } from "./DeathSaveRenderer";
import { CombatActionRenderer } from "./CombatActionRenderer";
import { DamageResultRenderer } from "./DamageResultRenderer";
import { HealResultRenderer } from "./HealResultRenderer";
registerToolRenderer("initiative_order", InitiativeOrderRenderer);
registerToolRenderer("attack_result", AttackResultRenderer);
registerToolRenderer("spell_cast", SpellCastRenderer);
registerToolRenderer("death_save", DeathSaveRenderer);
registerToolRenderer("combat_summary", InitiativeOrderRenderer);
registerToolRenderer("combat_action", CombatActionRenderer);
registerToolRenderer("damage_result", DamageResultRenderer);
registerToolRenderer("heal_result", HealResultRenderer);

// Phase 4 — Inventory
import { InventoryRenderer } from "./InventoryRenderer";
import { ItemDetailRenderer } from "./ItemDetailRenderer";
registerToolRenderer("inventory", InventoryRenderer);
registerToolRenderer("item_detail", ItemDetailRenderer);
registerToolRenderer("transfer_result", InventoryRenderer);

// Phase 5 — World & Spatial
import { LocationRenderer } from "./LocationRenderer";
registerToolRenderer("location", LocationRenderer);
registerToolRenderer("location_connected", LocationRenderer);
registerToolRenderer("environment", LocationRenderer);

// Phase 6 — NPCs
import { NPCRenderer } from "./NPCRenderer";
registerToolRenderer("npc_info", NPCRenderer);

// Phase 7 — Quests
import { QuestJournalRenderer } from "./QuestJournalRenderer";
registerToolRenderer("quest_info", QuestJournalRenderer);
registerToolRenderer("quest_journal", QuestJournalRenderer);
registerToolRenderer("quest_complete", QuestJournalRenderer);

// Phase 8 — Rest
import { RestResultRenderer } from "./RestResultRenderer";
registerToolRenderer("rest_result", RestResultRenderer);

// Phase 9 — Game State
import { GameStateRenderer } from "./GameStateRenderer";
registerToolRenderer("game_session", GameStateRenderer);
registerToolRenderer("game_state", GameStateRenderer);

// Phase 10 — Memory
import { MemoryRenderer } from "./MemoryRenderer";
registerToolRenderer("memory_archived", MemoryRenderer);
registerToolRenderer("memory_results", MemoryRenderer);
registerToolRenderer("recall_results", MemoryRenderer);
registerToolRenderer("session_summary", MemoryRenderer);
registerToolRenderer("session_ended", MemoryRenderer);

// Phase 11 — Knowledge Graph
import { RelationshipRenderer } from "./RelationshipRenderer";
registerToolRenderer("relationship_added", RelationshipRenderer);
registerToolRenderer("relationship_graph", RelationshipRenderer);
registerToolRenderer("connection_paths", RelationshipRenderer);
registerToolRenderer("connection_map", RelationshipRenderer);

// Phase 12 — Entity Context
import { EntityContextRenderer } from "./EntityContextRenderer";
registerToolRenderer("entity_context", EntityContextRenderer);

// Phase 13 — Campaign
import { CampaignRenderer } from "./CampaignRenderer";
registerToolRenderer("campaign_started", CampaignRenderer);
registerToolRenderer("campaign_list", CampaignRenderer);
