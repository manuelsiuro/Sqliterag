import { useState, useEffect, useRef } from "react";
import { useChatStore } from "@/store/chatStore";
import { useCampaignStore } from "@/store/campaignStore";
import { api } from "@/services/api";

interface AbilityScore {
  score: number;
  modifier: number;
}

interface InventoryItem {
  name: string;
  item_type: string;
  quantity: number;
  is_equipped: boolean;
  rarity: string;
  weight?: number;
  value_gp?: number;
}

interface CharacterState {
  name: string;
  race: string;
  class: string;
  level: number;
  current_hp: number;
  max_hp: number;
  temp_hp: number;
  armor_class: number;
  speed: number;
  is_alive: boolean;
  is_player: boolean;
  xp: number;
  xp_next_level: number | null;
  proficiency_bonus: number;
  hit_die: string;
  abilities: Record<string, AbilityScore>;
  conditions: string[];
  inventory: InventoryItem[];
}

interface QuestRewards {
  xp?: number;
  gold?: number;
  items?: string[];
}

interface QuestObjective {
  description?: string;
  text?: string;
  completed?: boolean;
}

interface QuestState {
  title: string;
  objectives: QuestObjective[];
  description: string;
  rewards: QuestRewards;
}

interface NPCState {
  name: string;
  disposition: string;
  familiarity: string;
  description: string;
}

interface CampaignInfo {
  id: string;
  name: string;
  session_number: number;
  status: string;
}

interface GameState {
  world_name: string;
  characters: CharacterState[];
  current_location: { name: string; description: string; biome: string } | null;
  active_quests: QuestState[];
  npcs: NPCState[];
  in_combat: boolean;
  combat: unknown;
  environment: { time_of_day: string; weather: string; season: string };
  campaign?: CampaignInfo | null;
  session_status?: string;
}

const BIOME_ICONS: Record<string, string> = {
  town: "\uD83C\uDFD8\uFE0F", village: "\uD83C\uDFE1", forest: "\uD83C\uDF32",
  dungeon: "\uD83D\uDD73\uFE0F", cave: "\u26F0\uFE0F", mountain: "\uD83C\uDFD4\uFE0F",
  desert: "\uD83C\uDFDC\uFE0F", ocean: "\uD83C\uDF0A", castle: "\uD83C\uDFF0", tavern: "\uD83C\uDF7A",
};

const TIME_ICONS: Record<string, string> = {
  dawn: "\uD83C\uDF05", morning: "\uD83C\uDF04", day: "\u2600\uFE0F", noon: "\uD83C\uDF1E",
  afternoon: "\uD83C\uDF24\uFE0F", dusk: "\uD83C\uDF07", evening: "\uD83C\uDF06",
  night: "\uD83C\uDF19", midnight: "\uD83C\uDF11",
};
const WEATHER_ICONS: Record<string, string> = {
  clear: "\u2600\uFE0F", cloudy: "\u2601\uFE0F", overcast: "\uD83C\uDF25\uFE0F",
  rain: "\uD83C\uDF27\uFE0F", storm: "\u26C8\uFE0F", snow: "\u2744\uFE0F",
  fog: "\uD83C\uDF2B\uFE0F", wind: "\uD83D\uDCA8",
};
const SEASON_ICONS: Record<string, string> = {
  spring: "\uD83C\uDF38", summer: "\uD83C\uDF3B", autumn: "\uD83C\uDF42",
  fall: "\uD83C\uDF42", winter: "\u2744\uFE0F",
};

const RACE_ICONS: Record<string, string> = {
  human: "\uD83D\uDC64", elf: "\uD83E\uDDDD", dwarf: "\u26CF\uFE0F",
  halfling: "\uD83E\uDDB6", gnome: "\uD83D\uDD27", "half-elf": "\uD83C\uDF1F",
  "half-orc": "\uD83D\uDCAA", tiefling: "\uD83D\uDD25", dragonborn: "\uD83D\uDC09",
  orc: "\uD83D\uDC79",
};

const CLASS_ICONS: Record<string, string> = {
  fighter: "\u2694\uFE0F", wizard: "\uD83E\uDE84", rogue: "\uD83D\uDDE1\uFE0F",
  cleric: "\u2695\uFE0F", ranger: "\uD83C\uDFF9", paladin: "\uD83D\uDEE1\uFE0F",
  barbarian: "\uD83E\uDE93", bard: "\uD83C\uDFB6", druid: "\uD83C\uDF3F",
  monk: "\u270A", sorcerer: "\u2728", warlock: "\uD83D\uDD2E",
};

const RARITY_COLORS: Record<string, string> = {
  common: "text-gray-400", uncommon: "text-green-400", rare: "text-blue-400",
  "very rare": "text-purple-400", legendary: "text-amber-400", artifact: "text-red-400",
};

const RARITY_BORDER: Record<string, string> = {
  common: "border-l-gray-600", uncommon: "border-l-green-500", rare: "border-l-blue-500",
  "very rare": "border-l-purple-500", legendary: "border-l-amber-400", artifact: "border-l-red-500",
};

const DISPOSITION_COLORS: Record<string, string> = {
  hostile: "text-red-400 bg-red-900/30 border-red-700/30",
  unfriendly: "text-orange-400 bg-orange-900/30 border-orange-700/30",
  neutral: "text-gray-400 bg-gray-800/50 border-gray-600/30",
  friendly: "text-green-400 bg-green-900/30 border-green-700/30",
  helpful: "text-emerald-400 bg-emerald-900/30 border-emerald-700/30",
};

const TYPE_ICONS: Record<string, string> = {
  weapon: "\u2694\uFE0F", armor: "\uD83D\uDEE1\uFE0F", consumable: "\uD83E\uDDEA",
  quest: "\uD83D\uDCDC", scroll: "\uD83D\uDCDC", misc: "\uD83C\uDF92",
  potion: "\uD83E\uDDEA", shield: "\uD83D\uDEE1\uFE0F", ring: "\uD83D\uDC8D",
  wand: "\uD83E\uDE84", staff: "\uD83E\uDE84", amulet: "\uD83D\uDCAE",
};

const ABILITY_ABBR: Record<string, string> = {
  strength: "STR", dexterity: "DEX", constitution: "CON",
  intelligence: "INT", wisdom: "WIS", charisma: "CHA",
};

function capitalize(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function CharacterCard({ c }: { c: CharacterState }) {
  const hpPct = Math.max(0, (c.current_hp / Math.max(c.max_hp, 1)) * 100);
  const raceIcon = RACE_ICONS[c.race.toLowerCase()] || "\uD83D\uDC64";
  const classIcon = CLASS_ICONS[c.class.toLowerCase()] || "\u2694\uFE0F";

  return (
    <div
      className={`bg-gray-800/50 rounded-lg px-3 py-2.5 border ${
        !c.is_alive ? "border-red-800/40 opacity-50" : "border-gray-700/40"
      }`}
    >
      {/* Row 1: Name + Dead indicator */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-bold text-white truncate">
          {c.name}
          {!c.is_alive && <span className="text-red-400 text-xs ml-1 font-normal">(Dead)</span>}
        </span>
      </div>

      {/* Row 2: Race + Class with level badge */}
      <div className="flex items-center gap-1.5 mt-0.5">
        <span className="text-[11px]">{raceIcon}</span>
        <span className="text-[11px] text-gray-400">{c.race}</span>
        <span className="text-gray-600 text-[10px]">{"\u00B7"}</span>
        <span className="text-[11px]">{classIcon}</span>
        <span className="text-[11px] text-gray-400">{c.class}</span>
        <span className="text-[10px] px-1.5 py-px rounded-full bg-amber-900/40 text-amber-300 border border-amber-700/30 font-medium ml-auto">
          Lv {c.level}
        </span>
      </div>

      {/* Row 3: AC + Speed */}
      <div className="flex items-center gap-3 mt-1.5">
        <div className="flex items-center gap-1">
          <span className="text-[10px] text-gray-500">AC</span>
          <span className="text-xs font-bold text-blue-300">{c.armor_class}</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-[10px] text-gray-500">SPD</span>
          <span className="text-xs font-medium text-gray-300">{c.speed}ft</span>
        </div>
      </div>

      {/* Row 4: HP bar */}
      <div className="flex items-center gap-2 mt-1.5">
        <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${
              hpPct > 50 ? "bg-emerald-500" : hpPct > 25 ? "bg-yellow-500" : "bg-red-500"
            }`}
            style={{ width: `${hpPct}%` }}
          />
        </div>
        <span className="text-[10px] text-gray-500 whitespace-nowrap">
          {c.current_hp}/{c.max_hp}
          {c.temp_hp > 0 && <span className="text-blue-400"> +{c.temp_hp}</span>}
        </span>
      </div>

      {/* Row 5: Mini ability scores */}
      {c.abilities && (
        <div className="flex gap-1 mt-1.5">
          {Object.entries(ABILITY_ABBR).map(([key, abbr]) => {
            const ab = c.abilities[key];
            if (!ab) return null;
            return (
              <div key={key} className="text-center flex-1">
                <div className="text-[8px] text-gray-600">{abbr}</div>
                <div className="text-xs font-bold text-white">{ab.score}</div>
                <div className={`text-[9px] ${ab.modifier >= 0 ? "text-gray-400" : "text-red-400"}`}>
                  {ab.modifier >= 0 ? "+" : ""}{ab.modifier}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Row 6: Conditions */}
      {c.conditions && c.conditions.length > 0 && (
        <div className="flex flex-wrap gap-1 mt-1.5">
          {c.conditions.map((cond) => (
            <span key={cond} className="text-[9px] px-1.5 py-px rounded-full bg-red-900/40 text-red-300 border border-red-700/30">
              {cond}
            </span>
          ))}
        </div>
      )}

      {/* Row 7: Collapsible Inventory */}
      {c.inventory && <InventorySection inventory={c.inventory} />}
    </div>
  );
}

function InventorySection({ inventory }: { inventory: InventoryItem[] }) {
  const [open, setOpen] = useState(false);

  if (inventory.length === 0) return null;

  const sorted = [...inventory].sort((a, b) => {
    if (a.is_equipped !== b.is_equipped) return a.is_equipped ? -1 : 1;
    return a.name.localeCompare(b.name);
  });

  return (
    <div className="mt-1.5">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 text-[10px] text-gray-500 hover:text-gray-300 transition-colors w-full"
      >
        <span className="transition-transform duration-150" style={{ transform: open ? "rotate(90deg)" : "rotate(0deg)" }}>
          {"\u25B6"}
        </span>
        <span>Inventory ({inventory.length})</span>
      </button>
      {open && (
        <div className="mt-1 space-y-0.5 pl-2">
          {sorted.map((item, i) => (
            <div key={i} className={`flex items-center gap-1.5 text-[10px] bg-gray-800/40 rounded px-1.5 py-1 border border-gray-700/20 border-l-2 ${RARITY_BORDER[item.rarity] || "border-l-gray-600"}`}>
              <span>{TYPE_ICONS[item.item_type] || "\uD83D\uDCE6"}</span>
              <span className={`flex-1 truncate ${RARITY_COLORS[item.rarity] || "text-gray-400"}`}>
                {item.name}
                {item.quantity > 1 && ` x${item.quantity}`}
              </span>
              {item.is_equipped && (
                <span className="text-[9px] px-1 py-px rounded bg-amber-900/40 text-amber-400 border border-amber-700/30">
                  E
                </span>
              )}
              <span className="text-[9px] text-gray-600 capitalize">{item.item_type}</span>
              {item.weight != null && (
                <span className="text-gray-600">{item.weight}lb</span>
              )}
              {item.value_gp != null && (
                <span className="text-yellow-600">{item.value_gp}gp</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function QuestCard({ q }: { q: QuestState }) {
  const [open, setOpen] = useState(false);
  const hasRewards = q.rewards && (q.rewards.xp || q.rewards.gold || (q.rewards.items && q.rewards.items.length > 0));

  return (
    <div className="bg-amber-900/20 rounded-lg border border-amber-800/30">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 w-full px-2 py-1.5 text-left"
      >
        <span className="transition-transform duration-150 text-[10px] text-gray-500" style={{ transform: open ? "rotate(90deg)" : "rotate(0deg)" }}>
          {"\u25B6"}
        </span>
        <span className="text-xs text-amber-300 flex-1 truncate">{q.title}</span>
        {q.objectives.length > 0 && (
          <span className="text-[9px] text-gray-500">
            {q.objectives.filter((o) => o.completed).length}/{q.objectives.length}
          </span>
        )}
      </button>
      {open && (
        <div className="px-2.5 pb-2 space-y-1.5">
          {q.description && (
            <div className="text-[10px] text-gray-400 italic">{q.description}</div>
          )}
          {q.objectives.length > 0 && (
            <div className="space-y-0.5">
              {q.objectives.map((obj, i) => {
                const text = obj.description || obj.text || `Objective ${i + 1}`;
                return (
                  <div key={i} className="flex items-start gap-1 text-[10px]">
                    <span className={obj.completed ? "text-green-400" : "text-gray-600"}>
                      {obj.completed ? "\u2611" : "\u2610"}
                    </span>
                    <span className={obj.completed ? "text-gray-500 line-through" : "text-gray-300"}>
                      {text}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
          {hasRewards && (
            <div className="flex flex-wrap gap-1.5 pt-0.5">
              {q.rewards.xp && (
                <span className="text-[9px] px-1.5 py-px rounded-full bg-purple-900/40 text-purple-300 border border-purple-700/30">
                  {q.rewards.xp} XP
                </span>
              )}
              {q.rewards.gold && (
                <span className="text-[9px] px-1.5 py-px rounded-full bg-yellow-900/40 text-yellow-300 border border-yellow-700/30">
                  {q.rewards.gold} GP
                </span>
              )}
              {q.rewards.items?.map((item) => (
                <span key={item} className="text-[9px] px-1.5 py-px rounded-full bg-sky-900/40 text-sky-300 border border-sky-700/30">
                  {item}
                </span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function NPCCard({ n }: { n: NPCState }) {
  const [open, setOpen] = useState(false);
  const dispStyle = DISPOSITION_COLORS[n.disposition] || DISPOSITION_COLORS.neutral;

  return (
    <div className="bg-purple-900/20 rounded-lg border border-purple-800/30">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 w-full px-2 py-1.5 text-left"
      >
        <span className="transition-transform duration-150 text-[10px] text-gray-500" style={{ transform: open ? "rotate(90deg)" : "rotate(0deg)" }}>
          {"\u25B6"}
        </span>
        <span className="text-xs text-purple-300 flex-1 truncate">{n.name}</span>
        <span className={`text-[9px] px-1.5 py-px rounded-full border capitalize ${dispStyle}`}>
          {n.disposition}
        </span>
      </button>
      {open && (
        <div className="px-2.5 pb-2 space-y-1">
          {n.description && (
            <div className="text-[10px] text-gray-400 italic">{n.description}</div>
          )}
          <div className="text-[10px] text-gray-500">
            Familiarity: <span className="text-gray-300 capitalize">{n.familiarity}</span>
          </div>
        </div>
      )}
    </div>
  );
}

export function GamePanel() {
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [loading, setLoading] = useState(false);
  const { activeConversationId, messages } = useChatStore();

  // Track message count to detect new tool results
  const messageCount = messages.length;
  const prevConvId = useRef<string | null>(null);

  useEffect(() => {
    if (!activeConversationId) {
      setGameState(null);
      return;
    }

    // Show loading spinner only on conversation switch
    const isConversationSwitch = prevConvId.current !== activeConversationId;
    prevConvId.current = activeConversationId;

    if (isConversationSwitch) {
      setLoading(true);
    }

    let cancelled = false;
    api.getGameState(activeConversationId).then((data) => {
      if (cancelled) return;
      setGameState(data as GameState | null);
      setLoading(false);
    }).catch(() => {
      if (cancelled) return;
      setGameState(null);
      setLoading(false);
    });

    return () => { cancelled = true; };
  }, [activeConversationId, messageCount]);

  const { continueCampaign } = useCampaignStore();
  const { selectConversation, loadConversations } = useChatStore();

  const handleContinue = async () => {
    if (!gameState?.campaign?.id) return;
    try {
      const newConvId = await continueCampaign(gameState.campaign.id);
      await loadConversations();
      selectConversation(newConvId);
    } catch (err) {
      console.error("Continue campaign failed:", err);
    }
  };

  const playerChars = gameState?.characters.filter(c => c.is_player) || [];
  const creatures = gameState?.characters.filter(c => !c.is_player) || [];

  return (
    <div className="w-80 bg-gray-900 border-l border-gray-800 flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <span className="text-lg drop-shadow-[0_0_6px_rgba(251,191,36,0.4)]">{"\uD83C\uDFF0"}</span>
          <h2 className="text-sm font-bold text-amber-200">RPG Dashboard</h2>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {loading ? (
          <div className="text-gray-500 text-sm text-center py-8">Loading...</div>
        ) : !gameState ? (
          <div className="text-center py-8 space-y-3">
            <div className="text-4xl opacity-40">{"\uD83C\uDFB2"}</div>
            <div className="h-px bg-gray-700 mx-8" />
            <div className="text-sm text-gray-400">No active game session</div>
            <div className="text-xs text-gray-600">
              Enable RPG tools for this conversation and ask the AI to
              &ldquo;start a game session&rdquo; to begin!
            </div>
          </div>
        ) : (
          <>
            {/* Campaign */}
            {gameState.campaign && (
              <section className="bg-amber-950/20 rounded-lg px-3 py-2.5 border border-amber-800/30">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold text-amber-200 flex-1 truncate">
                    {gameState.campaign.name}
                  </span>
                  <span className="text-[10px] px-1.5 py-px rounded-full bg-amber-900/40 text-amber-400 border border-amber-700/30">
                    Session {gameState.campaign.session_number}
                  </span>
                </div>
                {gameState.session_status === "ended" && (
                  <button
                    onClick={handleContinue}
                    className="mt-2 w-full py-1.5 text-xs bg-emerald-700 hover:bg-emerald-600 text-white rounded-md transition-colors"
                  >
                    Continue Campaign
                  </button>
                )}
              </section>
            )}

            {/* World */}
            <section>
              <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">World</h3>
              <div className="text-sm font-bold text-amber-200 mb-2">{gameState.world_name}</div>
              {/* Environment pills */}
              {gameState.environment && (
                <div className="flex flex-wrap gap-1.5">
                  <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-sky-900/30 text-sky-300 border border-sky-700/30">
                    {TIME_ICONS[gameState.environment.time_of_day] || "\uD83D\uDD50"} {capitalize(gameState.environment.time_of_day)}
                  </span>
                  <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-slate-800/50 text-slate-300 border border-slate-600/30">
                    {WEATHER_ICONS[gameState.environment.weather] || "\uD83C\uDF21\uFE0F"} {capitalize(gameState.environment.weather)}
                  </span>
                  <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-emerald-900/30 text-emerald-300 border border-emerald-700/30">
                    {SEASON_ICONS[gameState.environment.season] || "\uD83D\uDCC5"} {capitalize(gameState.environment.season)}
                  </span>
                </div>
              )}
            </section>

            {/* Location */}
            {gameState.current_location && (
              <section className="border-t border-gray-800/60 pt-3">
                <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">Location</h3>
                <div className="bg-gray-800/50 rounded-lg px-3 py-2 border border-gray-700/40">
                  <div className="flex items-center gap-1.5">
                    <span>{BIOME_ICONS[gameState.current_location.biome] || "\uD83D\uDDFA\uFE0F"}</span>
                    <span className="text-sm text-gray-200">{gameState.current_location.name}</span>
                  </div>
                  <div className="text-[10px] text-gray-500 capitalize mt-0.5">{gameState.current_location.biome}</div>
                </div>
              </section>
            )}

            {/* Combat indicator */}
            {gameState.in_combat && (
              <div className="bg-red-900/30 rounded-lg px-3 py-2 border border-red-700/40 text-center">
                <span className="text-sm font-bold text-red-300">{"\u2694\uFE0F"} Combat in Progress!</span>
              </div>
            )}

            {/* Player Characters */}
            {playerChars.length > 0 && (
              <section className="border-t border-gray-800/60 pt-3">
                <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
                  Party ({playerChars.length})
                </h3>
                <div className="space-y-2">
                  {playerChars.map((c) => (
                    <CharacterCard key={c.name} c={c} />
                  ))}
                </div>
              </section>
            )}

            {/* Creatures (non-player characters) */}
            {creatures.length > 0 && (
              <section className="border-t border-gray-800/60 pt-3">
                <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
                  Creatures ({creatures.length})
                </h3>
                <div className="space-y-2">
                  {creatures.map((c) => (
                    <CharacterCard key={c.name} c={c} />
                  ))}
                </div>
              </section>
            )}

            {/* Active Quests */}
            {gameState.active_quests.length > 0 && (
              <section className="border-t border-gray-800/60 pt-3">
                <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
                  Quests ({gameState.active_quests.length})
                </h3>
                <div className="space-y-1.5">
                  {gameState.active_quests.map((q) => (
                    <QuestCard key={q.title} q={q} />
                  ))}
                </div>
              </section>
            )}

            {/* NPCs */}
            {gameState.npcs.length > 0 && (
              <section className="border-t border-gray-800/60 pt-3">
                <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
                  NPCs ({gameState.npcs.length})
                </h3>
                <div className="space-y-1.5">
                  {gameState.npcs.map((n) => (
                    <NPCCard key={n.name} n={n} />
                  ))}
                </div>
              </section>
            )}
          </>
        )}
      </div>
    </div>
  );
}
