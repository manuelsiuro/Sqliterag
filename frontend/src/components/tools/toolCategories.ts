import type { ToolDefinition } from "@/types";

export interface ToolCategory {
  key: string;
  emoji: string;
  label: string;
  order: number;
}

export interface ToolGroup {
  category: ToolCategory;
  tools: ToolDefinition[];
}

export const TOOL_CATEGORIES: ToolCategory[] = [
  { key: "dice", emoji: "\u{1F3B2}", label: "Dice & Rolls", order: 0 },
  { key: "characters", emoji: "\u{1F9D9}", label: "Characters", order: 1 },
  { key: "combat", emoji: "\u2694\uFE0F", label: "Combat", order: 2 },
  { key: "inventory", emoji: "\u{1F392}", label: "Inventory & Items", order: 3 },
  { key: "world", emoji: "\u{1F5FA}\uFE0F", label: "World & Exploration", order: 4 },
  { key: "npcs", emoji: "\u{1F5E3}\uFE0F", label: "NPCs", order: 5 },
  { key: "quests", emoji: "\u{1F4DC}", label: "Quests", order: 6 },
  { key: "rest", emoji: "\u26FA", label: "Rest & Recovery", order: 7 },
  { key: "session", emoji: "\u{1F3AE}", label: "Game Session", order: 8 },
  { key: "custom", emoji: "\u{1F527}", label: "Custom Tools", order: 9 },
];

const TOOL_CATEGORY_MAP: Record<string, string> = {
  // Dice & Rolls
  roll_d20: "dice",
  roll_dice: "dice",
  roll_check: "dice",
  roll_save: "dice",

  // Characters
  create_character: "characters",
  get_character: "characters",
  update_character: "characters",
  list_characters: "characters",

  // Combat
  start_combat: "combat",
  get_combat_status: "combat",
  next_turn: "combat",
  end_combat: "combat",
  attack: "combat",
  cast_spell: "combat",
  heal: "combat",
  take_damage: "combat",
  death_save: "combat",
  combat_action: "combat",

  // Inventory & Items
  create_item: "inventory",
  give_item: "inventory",
  equip_item: "inventory",
  unequip_item: "inventory",
  get_inventory: "inventory",
  transfer_item: "inventory",

  // World & Exploration
  create_location: "world",
  connect_locations: "world",
  move_to: "world",
  look_around: "world",
  set_environment: "world",

  // NPCs
  create_npc: "npcs",
  talk_to_npc: "npcs",
  update_npc_relationship: "npcs",
  npc_remember: "npcs",

  // Quests
  create_quest: "quests",
  update_quest_objective: "quests",
  complete_quest: "quests",
  get_quest_journal: "quests",

  // Rest & Recovery
  short_rest: "rest",
  long_rest: "rest",

  // Game Session
  init_game_session: "session",
  get_game_state: "session",
};

const categoryByKey = new Map(TOOL_CATEGORIES.map((c) => [c.key, c]));

export function getCategoryKey(tool: ToolDefinition): string {
  return TOOL_CATEGORY_MAP[tool.name] ?? "custom";
}

export function getCategory(key: string): ToolCategory {
  return categoryByKey.get(key) ?? categoryByKey.get("custom")!;
}

/** Return tool IDs belonging to a given category key. */
export function getToolIdsByCategory(
  tools: ToolDefinition[],
  categoryKey: string,
): string[] {
  return tools
    .filter((t) => getCategoryKey(t) === categoryKey)
    .map((t) => t.id);
}

/**
 * Estimate the token count for a single tool definition.
 * Reconstructs the Ollama JSON shape and uses chars/4 approximation.
 */
export function estimateToolTokens(tool: ToolDefinition): number {
  const shape = {
    type: "function" as const,
    function: {
      name: tool.name,
      description: tool.description,
      parameters: tool.parameters_schema,
    },
  };
  return Math.ceil(JSON.stringify(shape).length / 4);
}

/** Sum estimated tokens for an array of tools, plus small array overhead. */
export function estimateTotalToolTokens(tools: ToolDefinition[]): number {
  if (tools.length === 0) return 0;
  const perTool = tools.reduce((sum, t) => sum + estimateToolTokens(t), 0);
  // ~2 tokens per tool for JSON array separators / overhead
  return perTool + tools.length * 2;
}
