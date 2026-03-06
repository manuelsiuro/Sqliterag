import { useState, useEffect, useRef } from "react";
import { useChatStore } from "@/store/chatStore";
import { useCampaignStore } from "@/store/campaignStore";
import { useUIStore } from "@/store/uiStore";
import { api } from "@/services/api";
import { MemoryBrowser } from "./MemoryBrowser";
import { InsightsPanel } from "./InsightsPanel";
import {
  BIOME_ICONS, TIME_ICONS, WEATHER_ICONS, SEASON_ICONS,
  RACE_ICONS, CLASS_ICONS, ABILITY_ABBR,
  RARITY_COLORS, RARITY_BORDER, TYPE_ICONS,
  DISPOSITION_COLORS, FAMILIARITY_ICONS, DIR_ARROWS,
  capitalize,
} from "@/constants/rpg";

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
  personality_traits?: string[];
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
  current_location: { name: string; description: string; biome: string; exits?: Record<string, string> } | null;
  active_quests: QuestState[];
  npcs: NPCState[];
  in_combat: boolean;
  combat: { encounter_difficulty?: { difficulty: string; adjusted_xp: number; multiplier: number } } | null;
  environment: { time_of_day: string; weather: string; season: string };
  campaign?: CampaignInfo | null;
  session_status?: string;
}

const DIFFICULTY_PILL_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  easy:   { bg: "bg-green-900/30",  text: "text-green-300",  border: "border-green-700/40" },
  medium: { bg: "bg-amber-900/30",  text: "text-amber-300",  border: "border-amber-700/40" },
  hard:   { bg: "bg-orange-900/30", text: "text-orange-300", border: "border-orange-700/40" },
  deadly: { bg: "bg-red-900/30",    text: "text-red-300",    border: "border-red-700/40" },
};

function CharacterCard({ c }: { c: CharacterState }) {
  const hpPct = Math.max(0, (c.current_hp / Math.max(c.max_hp, 1)) * 100);
  const hpGradient = hpPct > 50 ? "from-emerald-500 to-emerald-400" : hpPct > 25 ? "from-yellow-500 to-amber-400" : "from-red-500 to-red-400";
  const raceIcon = RACE_ICONS[c.race.toLowerCase()] || "\uD83D\uDC64";
  const classIcon = CLASS_ICONS[c.class.toLowerCase()] || "\u2694\uFE0F";
  const xpPct = c.xp_next_level ? Math.max(0, Math.min(100, (c.xp / c.xp_next_level) * 100)) : 0;

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

      {/* Row 3: AC + Speed + Prof + Hit Die */}
      <div className="flex items-center gap-2 mt-1.5 flex-wrap">
        <div className="flex items-center gap-1">
          <span className="text-[11px]">{"\uD83D\uDEE1\uFE0F"}</span>
          <span className="text-xs font-bold text-blue-300">{c.armor_class}</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-[10px] text-gray-500">SPD</span>
          <span className="text-xs font-medium text-gray-300">{c.speed}ft</span>
        </div>
        <span className="text-[9px] px-1.5 py-px rounded-full bg-purple-900/40 text-purple-300 border border-purple-700/30">
          Prof +{c.proficiency_bonus}
        </span>
        {c.hit_die && (
          <span className="text-[9px] px-1.5 py-px rounded-full bg-gray-800/60 text-gray-400 border border-gray-700/30">
            {c.hit_die}
          </span>
        )}
      </div>

      {/* Row 4: HP bar */}
      <div className="flex items-center gap-2 mt-1.5">
        <div className="flex-1 h-2.5 bg-gray-700 rounded-full overflow-hidden border border-gray-700">
          <div
            className={`h-full rounded-full bg-gradient-to-r ${hpGradient} transition-all duration-500`}
            style={{ width: `${hpPct}%` }}
          />
        </div>
        <span className="text-[10px] text-gray-500 whitespace-nowrap">
          {c.current_hp}/{c.max_hp}
          {c.temp_hp > 0 && <span className="text-blue-400"> +{c.temp_hp}</span>}
        </span>
      </div>

      {/* Row 4b: XP progress bar */}
      {c.xp_next_level != null && c.xp_next_level > 0 && (
        <div className="flex items-center gap-2 mt-1">
          <div className="flex-1 h-1 bg-gray-700/60 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-amber-500/70 transition-all duration-500"
              style={{ width: `${xpPct}%` }}
            />
          </div>
          <span className="text-[9px] text-amber-400/70 whitespace-nowrap">
            {c.xp}/{c.xp_next_level} XP
          </span>
        </div>
      )}

      {/* Row 5: Mini ability scores */}
      {c.abilities && (
        <div className="flex gap-1 mt-1.5">
          {Object.entries(ABILITY_ABBR).map(([key, abbr]) => {
            const ab = c.abilities[key];
            if (!ab) return null;
            return (
              <div key={key} className="text-center flex-1 bg-gray-800/40 rounded py-0.5">
                <div className="text-[9px] text-gray-500">{abbr}</div>
                <div className="text-sm font-bold text-white">{ab.score}</div>
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
  const completedCount = q.objectives.filter((o) => o.completed).length;
  const progressPct = q.objectives.length > 0 ? (completedCount / q.objectives.length) * 100 : 0;

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
            {completedCount}/{q.objectives.length}
          </span>
        )}
      </button>
      {/* Objective progress bar */}
      {q.objectives.length > 0 && (
        <div className="px-2 pb-1">
          <div className="h-1 bg-gray-700/40 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-emerald-500/70 transition-all duration-500"
              style={{ width: `${progressPct}%` }}
            />
          </div>
        </div>
      )}
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
                  <div key={i} className="flex items-start gap-1.5 text-[10px]">
                    <span className={`inline-block w-3 h-3 mt-px rounded border flex-shrink-0 ${
                      obj.completed
                        ? "bg-emerald-600/40 border-emerald-500/60 text-emerald-300"
                        : "bg-gray-800/40 border-gray-600/40"
                    } flex items-center justify-center text-[8px] leading-none`}>
                      {obj.completed ? "\u2713" : ""}
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
  const familiarityIcon = FAMILIARITY_ICONS[n.familiarity] || "\uD83D\uDC64";

  return (
    <div className="bg-purple-900/20 rounded-lg border border-purple-800/30">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 w-full px-2 py-1.5 text-left"
      >
        <span className="transition-transform duration-150 text-[10px] text-gray-500" style={{ transform: open ? "rotate(90deg)" : "rotate(0deg)" }}>
          {"\u25B6"}
        </span>
        <span className="text-[11px]">{familiarityIcon}</span>
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
          {n.personality_traits && n.personality_traits.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {n.personality_traits.map((trait, i) => (
                <span key={i} className="text-[9px] px-1.5 py-px rounded-full bg-purple-900/25 text-purple-300 border border-purple-700/25">
                  {trait}
                </span>
              ))}
            </div>
          )}
          <div className="text-[10px] text-gray-500">
            Familiarity: <span className="text-gray-300 capitalize">{n.familiarity?.replace("_", " ")}</span>
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
      await selectConversation(newConvId);
      // Inject recap after conversation loads
      try {
        const recap = await api.getSessionRecap(newConvId);
        if (recap && recap.recap) {
          useChatStore.getState().injectRecapMessage(recap);
        }
      } catch {
        // Silent — recap is optional
      }
    } catch (err) {
      console.error("Continue campaign failed:", err);
    }
  };

  const playerChars = gameState?.characters.filter(c => c.is_player) || [];
  const creatures = gameState?.characters.filter(c => !c.is_player) || [];

  const { gamePanelTab, setGamePanelTab } = useUIStore();
  const tabs = [
    { id: "game" as const, label: "Game" },
    { id: "memory" as const, label: "Memory" },
    { id: "insights" as const, label: "Insights" },
  ];

  return (
    <div className="w-80 bg-gray-900 border-l border-gray-800 flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <span className="text-lg drop-shadow-[0_0_6px_rgba(251,191,36,0.4)]">{"\uD83C\uDFF0"}</span>
          <h2 className="text-sm font-bold text-amber-200">RPG Dashboard</h2>
        </div>
      </div>

      {/* Tab bar — only when game state exists */}
      {gameState && (
        <div className="flex gap-1 px-3 py-2 border-b border-gray-800">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setGamePanelTab(tab.id)}
              className={`flex-1 text-[11px] py-1 rounded-md font-medium transition-colors ${
                gamePanelTab === tab.id
                  ? "bg-amber-900/40 text-amber-300 border border-amber-700/30"
                  : "text-gray-500 hover:text-gray-300 border border-transparent"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      )}

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
        ) : gamePanelTab === "memory" ? (
          <MemoryBrowser />
        ) : gamePanelTab === "insights" ? (
          <InsightsPanel />
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
                <div className="bg-gray-800/50 rounded-lg px-3 py-2 border border-gray-700/40 space-y-1.5">
                  <div className="flex items-center gap-1.5">
                    <span>{BIOME_ICONS[gameState.current_location.biome] || "\uD83D\uDDFA\uFE0F"}</span>
                    <span className="text-sm text-gray-200">{gameState.current_location.name}</span>
                    <span className="text-[10px] text-gray-500 capitalize ml-auto">{gameState.current_location.biome}</span>
                  </div>
                  {gameState.current_location.description && (
                    <div className="text-[10px] text-gray-400 italic line-clamp-2">
                      {gameState.current_location.description}
                    </div>
                  )}
                  {gameState.current_location.exits && Object.keys(gameState.current_location.exits).length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      <span className="text-[9px] text-gray-500 self-center">Exits:</span>
                      {Object.entries(gameState.current_location.exits).map(([dir, loc]) => (
                        <span
                          key={dir}
                          className="inline-flex items-center text-[10px] rounded-full bg-gray-800 border border-gray-700/50 overflow-hidden"
                        >
                          <span className="inline-flex items-center gap-0.5 bg-amber-900/30 text-amber-300 border-r border-amber-700/30 px-1.5 py-px">
                            {DIR_ARROWS[dir] || "\u2022"} {capitalize(dir)}
                          </span>
                          <span className="text-gray-300 px-1.5 py-px">{loc}</span>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </section>
            )}

            {/* Combat indicator */}
            {gameState.in_combat && (
              <div className="bg-red-900/30 rounded-lg px-3 py-2 border border-red-700/40 text-center flex items-center justify-center gap-2">
                <span className="text-sm font-bold text-red-300">{"\u2694\uFE0F"} Combat in Progress!</span>
                {gameState.combat?.encounter_difficulty && (() => {
                  const diff = gameState.combat.encounter_difficulty.difficulty;
                  const style = DIFFICULTY_PILL_STYLES[diff] || DIFFICULTY_PILL_STYLES.medium;
                  return (
                    <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${style.bg} ${style.text} border ${style.border} uppercase`}>
                      {diff}
                    </span>
                  );
                })()}
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
