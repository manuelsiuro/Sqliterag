import { useState, useEffect, useRef } from "react";
import { useChatStore } from "@/store/chatStore";
import { api } from "@/services/api";

interface GameState {
  world_name: string;
  characters: { name: string; class: string; level: number; current_hp: number; max_hp: number; is_alive: boolean }[];
  current_location: { name: string; description: string; biome: string } | null;
  active_quests: { title: string; objectives: unknown[] }[];
  npcs: { name: string; disposition: string; familiarity: string }[];
  in_combat: boolean;
  combat: unknown;
  environment: { time_of_day: string; weather: string; season: string };
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

function capitalize(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
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

            {/* Party */}
            {gameState.characters.length > 0 && (
              <section className="border-t border-gray-800/60 pt-3">
                <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
                  Party ({gameState.characters.length})
                </h3>
                <div className="space-y-1.5">
                  {gameState.characters.map((c) => {
                    const hpPct = Math.max(0, (c.current_hp / Math.max(c.max_hp, 1)) * 100);
                    return (
                      <div
                        key={c.name}
                        className={`bg-gray-800/50 rounded-lg px-3 py-1.5 border ${
                          !c.is_alive ? "border-red-800/40 opacity-50" : "border-gray-700/40"
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-sm text-gray-200">{c.name}</span>
                          <span className="text-[10px] text-gray-500">L{c.level} {c.class}</span>
                        </div>
                        <div className="flex items-center gap-2 mt-1">
                          <div className="flex-1 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full transition-all ${
                                hpPct > 50 ? "bg-emerald-500" : hpPct > 25 ? "bg-yellow-500" : "bg-red-500"
                              }`}
                              style={{ width: `${hpPct}%` }}
                            />
                          </div>
                          <span className="text-[10px] text-gray-500">{c.current_hp}/{c.max_hp}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </section>
            )}

            {/* Active Quests */}
            {gameState.active_quests.length > 0 && (
              <section className="border-t border-gray-800/60 pt-3">
                <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-1">
                  Quests ({gameState.active_quests.length})
                </h3>
                <div className="space-y-1">
                  {gameState.active_quests.map((q) => (
                    <div key={q.title} className="text-xs text-amber-300 bg-amber-900/20 px-2 py-1 rounded border border-amber-800/30">
                      {q.title}
                    </div>
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
                <div className="flex flex-wrap gap-1">
                  {gameState.npcs.map((n) => (
                    <span
                      key={n.name}
                      className="text-[10px] px-1.5 py-0.5 rounded bg-purple-900/30 text-purple-300 border border-purple-700/40 capitalize"
                    >
                      {n.name} ({n.disposition})
                    </span>
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
