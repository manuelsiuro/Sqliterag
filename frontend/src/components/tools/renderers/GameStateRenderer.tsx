import type { ToolRendererProps } from "./toolRendererRegistry";

interface GameStateData {
  world_name: string;
  characters: { name: string; class: string; level: number; current_hp: number; max_hp: number }[];
  current_location: { name: string; description: string; biome: string } | null;
  active_quests: { title: string; objectives: unknown[] }[];
  npcs: { name: string; disposition: string; familiarity: string }[];
  in_combat: boolean;
  environment: { time_of_day: string; weather: string; season: string };
}

interface GameSessionData {
  world_name: string;
  session_id: string;
  message: string;
}

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
const BIOME_ICONS: Record<string, string> = {
  town: "\uD83C\uDFD8\uFE0F", village: "\uD83C\uDFE1", forest: "\uD83C\uDF32",
  dungeon: "\uD83D\uDD73\uFE0F", cave: "\u26F0\uFE0F", mountain: "\uD83C\uDFD4\uFE0F",
  desert: "\uD83C\uDFDC\uFE0F", swamp: "\uD83E\uDEB9", ocean: "\uD83C\uDF0A",
  plains: "\uD83C\uDF3E", castle: "\uD83C\uDFF0", temple: "\u26EA",
  tavern: "\uD83C\uDF7A", shop: "\uD83D\uDED2",
};

function capitalize(s: string) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function EnvironmentPills({ env }: { env: { time_of_day: string; weather: string; season: string } }) {
  return (
    <div className="flex flex-wrap gap-1.5">
      <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-sky-900/30 text-sky-300 border border-sky-700/30">
        {TIME_ICONS[env.time_of_day] || "\uD83D\uDD50"} {capitalize(env.time_of_day)}
      </span>
      <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-slate-800/50 text-slate-300 border border-slate-600/30">
        {WEATHER_ICONS[env.weather] || "\uD83C\uDF21\uFE0F"} {capitalize(env.weather)}
      </span>
      <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-emerald-900/30 text-emerald-300 border border-emerald-700/30">
        {SEASON_ICONS[env.season] || "\uD83D\uDCC5"} {capitalize(env.season)}
      </span>
    </div>
  );
}

export function GameStateRenderer({ data }: ToolRendererProps) {
  const d = data as unknown as Record<string, unknown>;

  // Session init
  if (d.message && d.session_id) {
    const s = d as unknown as GameSessionData;
    return (
      <div className="mt-2 space-y-2">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{"\uD83C\uDFF0"}</span>
          <div>
            <div className="text-lg font-bold text-amber-200">{s.world_name}</div>
            <div className="text-xs text-gray-500">Game session initialized</div>
          </div>
        </div>
        <div className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-amber-900/30 text-amber-300 border border-amber-700/30">
          {"\u2728"} New adventure begins
        </div>
        <div className="text-sm text-gray-300">{s.message}</div>
      </div>
    );
  }

  // Full game state
  const gs = d as unknown as GameStateData;

  return (
    <div className="mt-2 space-y-3">
      {/* World header */}
      <div className="flex items-center gap-2">
        <span className="text-lg">{"\uD83C\uDF0D"}</span>
        <span className="text-sm font-bold text-amber-200">{gs.world_name}</span>
      </div>

      {/* Environment pills */}
      {gs.environment && <EnvironmentPills env={gs.environment} />}

      {gs.in_combat && (
        <div className="text-xs bg-red-900/30 text-red-300 px-2 py-1 rounded border border-red-700/40 font-medium">
          {"\u2694\uFE0F"} Combat in progress!
        </div>
      )}

      {/* Location */}
      {gs.current_location && (
        <div className="bg-gray-800/40 rounded-lg px-3 py-2 border border-gray-700/30">
          <div className="flex items-center gap-1.5">
            <span>{BIOME_ICONS[gs.current_location.biome] || "\uD83D\uDDFA\uFE0F"}</span>
            <div>
              <div className="text-sm text-gray-200">{gs.current_location.name}</div>
              <div className="text-[10px] text-gray-500 capitalize">{gs.current_location.biome}</div>
            </div>
          </div>
        </div>
      )}

      {/* Party */}
      {gs.characters.length > 0 && (
        <div>
          <div className="text-xs text-gray-500 mb-1.5">Party ({gs.characters.length})</div>
          <div className="space-y-1.5">
            {gs.characters.map((c) => {
              const hpPct = Math.max(0, (c.current_hp / Math.max(c.max_hp, 1)) * 100);
              return (
                <div
                  key={c.name}
                  className="bg-gray-800/40 rounded-lg px-3 py-1.5 border border-gray-700/30"
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
        </div>
      )}

      {/* Active quests */}
      {gs.active_quests.length > 0 && (
        <div>
          <div className="text-xs text-gray-500 mb-1">Active Quests ({gs.active_quests.length})</div>
          {gs.active_quests.map((q) => (
            <div key={q.title} className="text-xs text-amber-300 pl-2 border-l border-amber-700/40">
              {q.title}
            </div>
          ))}
        </div>
      )}

      {/* NPCs */}
      {gs.npcs.length > 0 && (
        <div>
          <div className="text-xs text-gray-500 mb-1">NPCs ({gs.npcs.length})</div>
          <div className="flex flex-wrap gap-1.5">
            {gs.npcs.map((n) => (
              <span key={n.name} className="text-xs px-2 py-0.5 rounded bg-purple-900/30 text-purple-300 border border-purple-700/40 capitalize">
                {n.name} ({n.disposition})
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
