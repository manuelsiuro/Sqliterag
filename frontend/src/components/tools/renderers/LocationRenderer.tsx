import type { ToolRendererProps } from "./toolRendererRegistry";
import { BIOME_ICONS, TIME_ICONS, WEATHER_ICONS, SEASON_ICONS, DIR_ARROWS, capitalize } from "@/constants/rpg";

interface LocationData {
  type?: string;
  name: string;
  description: string;
  biome: string;
  exits: Record<string, string>;
  characters_here: string[];
  npcs_here: Array<string | { name: string; disposition: string }>;
  environment?: { time_of_day: string; weather: string; season: string };
  moved_by?: string;
  error?: string;
}

interface LocationConnectedData {
  type: "location_connected";
  location1: string;
  location2: string;
  direction: string;
  reverse_direction: string;
  error?: string;
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

export function LocationRenderer({ data }: ToolRendererProps) {
  const raw = data as unknown as Record<string, unknown>;

  if (raw.error) {
    return <div className="mt-2 text-red-400 text-sm">{raw.error as string}</div>;
  }

  // Location connected card
  if (raw.type === "location_connected") {
    const c = raw as unknown as LocationConnectedData;
    const arrow = DIR_ARROWS[c.direction] || "\u2194";
    return (
      <div className="mt-2 bg-gray-800/30 rounded-lg px-3 py-2.5 border border-gray-700/30">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-base">{"\uD83D\uDD17"}</span>
          <span className="text-gray-200">{c.location1}</span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-amber-900/30 text-amber-300 border border-amber-700/30">
            {arrow} {capitalize(c.direction)}
          </span>
          <span className="text-gray-200">{c.location2}</span>
        </div>
      </div>
    );
  }

  // Environment update card
  if (raw.type === "environment") {
    const env = raw as unknown as { time_of_day: string; weather: string; season: string };
    return (
      <div className="mt-2 bg-gray-800/30 rounded-lg px-3 py-2.5 border border-gray-700/30 space-y-2">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-base">{"\uD83C\uDF0D"}</span>
          <span className="font-medium text-sky-200">Environment Updated</span>
        </div>
        <EnvironmentPills env={env} />
      </div>
    );
  }

  const d = raw as unknown as LocationData;

  const exits = d.exits ? Object.entries(d.exits) : [];
  const charsHere = d.characters_here ?? [];
  const npcsHere = d.npcs_here ?? [];

  return (
    <div className="mt-2 bg-gray-800/30 rounded-lg px-3 py-2.5 border border-gray-700/30 space-y-2">
      {/* Location header */}
      <div className="flex items-center gap-2">
        <span className="text-xl">{BIOME_ICONS[d.biome] || "\uD83D\uDDFA\uFE0F"}</span>
        <div>
          <div className="text-sm font-bold text-amber-200">{d.name}</div>
          <div className="text-[10px] text-gray-500 capitalize">{d.biome}</div>
        </div>
      </div>

      {/* Environment pills */}
      {d.environment && <EnvironmentPills env={d.environment} />}

      {d.moved_by && (
        <div className="text-xs text-blue-400 italic">{d.moved_by} arrives here.</div>
      )}

      {/* Description */}
      {d.description && (
        <div className="text-xs text-gray-400 bg-gray-800/40 rounded px-2 py-1.5 border border-gray-700/30 italic">
          {d.description}
        </div>
      )}

      {/* Exits */}
      {exits.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          <span className="text-[10px] text-gray-500 self-center">Exits:</span>
          {exits.map(([dir, loc], i) => (
            <span
              key={dir}
              className="inline-flex items-center gap-1.5 text-xs rounded-full bg-gray-800 border border-gray-700/50 animate-item-appear overflow-hidden"
              style={{ animationDelay: `${i * 40}ms` }}
            >
              <span className="inline-flex items-center gap-0.5 bg-amber-900/30 text-amber-300 border-r border-amber-700/30 px-2 py-0.5 text-[11px]">
                {DIR_ARROWS[dir] || "\u2022"} {capitalize(dir)}
              </span>
              <span className="text-gray-300 pr-2 py-0.5">{loc}</span>
            </span>
          ))}
        </div>
      )}

      {/* Who's here */}
      {(charsHere.length > 0 || npcsHere.length > 0) && (
        <div className="flex flex-wrap gap-1.5">
          <span className="text-[10px] text-gray-500 self-center">Present:</span>
          {charsHere.map((c, i) => (
            <span key={c} className="text-xs px-2 py-0.5 rounded bg-blue-900/30 text-blue-300 border border-blue-700/40 animate-item-appear" style={{ animationDelay: `${i * 40}ms` }}>
              {c}
            </span>
          ))}
          {npcsHere.map((n, i) => {
            const name = typeof n === "string" ? n : n.name;
            return (
              <span key={name} className="text-xs px-2 py-0.5 rounded bg-purple-900/30 text-purple-300 border border-purple-700/40 animate-item-appear" style={{ animationDelay: `${(charsHere.length + i) * 40}ms` }}>
                {name}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}
