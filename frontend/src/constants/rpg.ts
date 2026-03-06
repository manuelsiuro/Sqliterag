// Shared RPG constants — single source of truth for renderers + GamePanel

export const TIME_ICONS: Record<string, string> = {
  dawn: "\uD83C\uDF05", morning: "\uD83C\uDF04", day: "\u2600\uFE0F", noon: "\uD83C\uDF1E",
  afternoon: "\uD83C\uDF24\uFE0F", dusk: "\uD83C\uDF07", evening: "\uD83C\uDF06",
  night: "\uD83C\uDF19", midnight: "\uD83C\uDF11",
};

export const WEATHER_ICONS: Record<string, string> = {
  clear: "\u2600\uFE0F", cloudy: "\u2601\uFE0F", overcast: "\uD83C\uDF25\uFE0F",
  rain: "\uD83C\uDF27\uFE0F", storm: "\u26C8\uFE0F", snow: "\u2744\uFE0F",
  fog: "\uD83C\uDF2B\uFE0F", wind: "\uD83D\uDCA8",
};

export const SEASON_ICONS: Record<string, string> = {
  spring: "\uD83C\uDF38", summer: "\uD83C\uDF3B", autumn: "\uD83C\uDF42",
  fall: "\uD83C\uDF42", winter: "\u2744\uFE0F",
};

export const BIOME_ICONS: Record<string, string> = {
  town: "\uD83C\uDFD8\uFE0F", village: "\uD83C\uDFE1", forest: "\uD83C\uDF32",
  dungeon: "\uD83D\uDD73\uFE0F", cave: "\u26F0\uFE0F", mountain: "\uD83C\uDFD4\uFE0F",
  desert: "\uD83C\uDFDC\uFE0F", swamp: "\uD83E\uDEB9", ocean: "\uD83C\uDF0A",
  plains: "\uD83C\uDF3E", castle: "\uD83C\uDFF0", temple: "\u26EA",
  tavern: "\uD83C\uDF7A", shop: "\uD83D\uDED2",
};

export const RACE_ICONS: Record<string, string> = {
  human: "\uD83D\uDC64", elf: "\uD83E\uDDDD", dwarf: "\u26CF\uFE0F",
  halfling: "\uD83E\uDDB6", gnome: "\uD83D\uDD27", "half-elf": "\uD83C\uDF1F",
  "half-orc": "\uD83D\uDCAA", tiefling: "\uD83D\uDD25", dragonborn: "\uD83D\uDC09",
  orc: "\uD83D\uDC79",
};

export const CLASS_ICONS: Record<string, string> = {
  fighter: "\u2694\uFE0F", wizard: "\uD83E\uDE84", rogue: "\uD83D\uDDE1\uFE0F",
  cleric: "\u2695\uFE0F", ranger: "\uD83C\uDFF9", paladin: "\uD83D\uDEE1\uFE0F",
  barbarian: "\uD83E\uDE93", bard: "\uD83C\uDFB6", druid: "\uD83C\uDF3F",
  monk: "\u270A", sorcerer: "\u2728", warlock: "\uD83D\uDD2E",
};

export const ABILITY_ABBR: Record<string, string> = {
  strength: "STR", dexterity: "DEX", constitution: "CON",
  intelligence: "INT", wisdom: "WIS", charisma: "CHA",
};

export const ABILITY_ORDER = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"];

export const RARITY_COLORS: Record<string, string> = {
  common: "text-gray-400", uncommon: "text-green-400", rare: "text-blue-400",
  "very rare": "text-purple-400", very_rare: "text-purple-400",
  legendary: "text-amber-400", artifact: "text-red-400",
};

export const RARITY_BORDER: Record<string, string> = {
  common: "border-l-gray-600", uncommon: "border-l-green-500", rare: "border-l-blue-500",
  "very rare": "border-l-purple-500", legendary: "border-l-amber-400", artifact: "border-l-red-500",
};

export const TYPE_ICONS: Record<string, string> = {
  weapon: "\u2694\uFE0F", armor: "\uD83D\uDEE1\uFE0F", consumable: "\uD83E\uDDEA",
  quest: "\uD83D\uDCDC", scroll: "\uD83D\uDCDC", misc: "\uD83C\uDF92",
  potion: "\uD83E\uDDEA", shield: "\uD83D\uDEE1\uFE0F", ring: "\uD83D\uDC8D",
  wand: "\uD83E\uDE84", staff: "\uD83E\uDE84", amulet: "\uD83D\uDCAE",
};

export const DISPOSITION_COLORS: Record<string, string> = {
  hostile: "text-red-400 bg-red-900/30 border-red-700/30",
  unfriendly: "text-orange-400 bg-orange-900/30 border-orange-700/30",
  neutral: "text-gray-400 bg-gray-800/50 border-gray-600/30",
  friendly: "text-green-400 bg-green-900/30 border-green-700/30",
  helpful: "text-emerald-400 bg-emerald-900/30 border-emerald-700/30",
};

export const FAMILIARITY_ICONS: Record<string, string> = {
  stranger: "\uD83D\uDC64",
  acquaintance: "\uD83D\uDC4B",
  friend: "\uD83E\uDD1D",
  close_friend: "\u2764\uFE0F",
};

export const DIR_ARROWS: Record<string, string> = {
  north: "\u2191", south: "\u2193", east: "\u2192", west: "\u2190",
  northeast: "\u2197", northwest: "\u2196",
  southeast: "\u2198", southwest: "\u2199",
  up: "\u2B06", down: "\u2B07",
};

export function capitalize(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}
