import type { ToolRendererProps } from "./toolRendererRegistry";

interface LocationData {
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

const BIOME_ICONS: Record<string, string> = {
  town: "\uD83C\uDFD8\uFE0F",
  village: "\uD83C\uDFE1",
  forest: "\uD83C\uDF32",
  dungeon: "\uD83D\uDD73\uFE0F",
  cave: "\u26F0\uFE0F",
  mountain: "\uD83C\uDFD4\uFE0F",
  desert: "\uD83C\uDFDC\uFE0F",
  swamp: "\uD83E\uDEB9",
  ocean: "\uD83C\uDF0A",
  plains: "\uD83C\uDF3E",
  castle: "\uD83C\uDFF0",
  temple: "\u26EA",
  tavern: "\uD83C\uDF7A",
  shop: "\uD83D\uDED2",
};

const DIR_ARROWS: Record<string, string> = {
  north: "\u2191", south: "\u2193", east: "\u2192", west: "\u2190",
  up: "\u2197", down: "\u2199",
  northeast: "\u2197", northwest: "\u2196",
  southeast: "\u2198", southwest: "\u2199",
};

export function LocationRenderer({ data }: ToolRendererProps) {
  const d = data as unknown as LocationData;

  if (d.error) {
    return <div className="mt-2 text-red-400 text-sm">{d.error}</div>;
  }

  const exits = Object.entries(d.exits);

  return (
    <div className="mt-2 space-y-2">
      {/* Location header */}
      <div className="flex items-center gap-2">
        <span className="text-xl">{BIOME_ICONS[d.biome] || "\uD83D\uDDFA\uFE0F"}</span>
        <div>
          <div className="text-sm font-bold text-amber-200">{d.name}</div>
          <div className="text-[10px] text-gray-500 capitalize">{d.biome}</div>
        </div>
        {d.environment && (
          <div className="ml-auto text-[10px] text-gray-500 text-right">
            {d.environment.time_of_day} &middot; {d.environment.weather} &middot; {d.environment.season}
          </div>
        )}
      </div>

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
          {exits.map(([dir, loc]) => (
            <span
              key={dir}
              className="text-xs px-2 py-0.5 rounded bg-gray-800 text-gray-300 border border-gray-700/50"
            >
              {DIR_ARROWS[dir] || "\u2022"} {dir} &rarr; {loc}
            </span>
          ))}
        </div>
      )}

      {/* Who's here */}
      {(d.characters_here.length > 0 || d.npcs_here.length > 0) && (
        <div className="flex flex-wrap gap-1.5">
          <span className="text-[10px] text-gray-500 self-center">Present:</span>
          {d.characters_here.map((c) => (
            <span key={c} className="text-xs px-2 py-0.5 rounded bg-blue-900/30 text-blue-300 border border-blue-700/40">
              {c}
            </span>
          ))}
          {d.npcs_here.map((n) => {
            const name = typeof n === "string" ? n : n.name;
            return (
              <span key={name} className="text-xs px-2 py-0.5 rounded bg-purple-900/30 text-purple-300 border border-purple-700/40">
                {name}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
}
