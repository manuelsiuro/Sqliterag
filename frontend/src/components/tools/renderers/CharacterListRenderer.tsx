import type { ToolRendererProps } from "./toolRendererRegistry";
import { RACE_ICONS } from "@/constants/rpg";

interface CharSummary {
  name: string;
  race: string;
  class: string;
  level: number;
  current_hp: number;
  max_hp: number;
  armor_class: number;
  is_alive: boolean;
  conditions: string[];
}

interface CharListData {
  characters: CharSummary[];
  count: number;
}

export function CharacterListRenderer({ data }: ToolRendererProps) {
  const { characters, count } = data as unknown as CharListData;

  if (count === 0) {
    return (
      <div className="mt-2 text-gray-400 text-sm italic">
        No characters yet. Create one with create_character.
      </div>
    );
  }

  return (
    <div className="mt-2 space-y-2">
      <div className="text-xs text-gray-500">{count} character{count !== 1 ? "s" : ""}</div>
      {characters.map((c, i) => {
        const hpPct = Math.max(0, (c.current_hp / Math.max(c.max_hp, 1)) * 100);
        const raceIcon = RACE_ICONS[c.race.toLowerCase()] || "\uD83D\uDC64";
        return (
          <div
            key={c.name}
            className={`flex items-center gap-3 bg-gray-800/50 rounded-lg px-4 py-3 border animate-item-appear ${
              !c.is_alive ? "border-red-800/40 opacity-60" : "border-gray-700/40"
            }`}
            style={{ animationDelay: `${i * 40}ms` }}
          >
            {/* Name, level badge, race+class */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-white truncate">
                  {c.name}
                  {!c.is_alive && <span className="text-red-400 text-xs ml-1">(Dead)</span>}
                </span>
                <span className="text-[10px] px-1.5 py-px rounded-full bg-amber-900/40 text-amber-300 border border-amber-700/30 font-medium shrink-0">
                  Lv {c.level}
                </span>
              </div>
              <div className="flex items-center gap-1 text-xs text-gray-500 mt-0.5">
                <span>{raceIcon}</span>
                <span>{c.race}</span>
                <span className="text-gray-600">{"\u00B7"}</span>
                <span>{c.class}</span>
              </div>
              {/* Conditions */}
              {c.conditions && c.conditions.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {c.conditions.map((cond) => (
                    <span key={cond} className="text-[9px] px-1.5 py-px rounded-full bg-red-900/40 text-red-300 border border-red-700/30">
                      {cond}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Mini HP bar */}
            <div className="w-20">
              <div className="text-[10px] text-gray-500 text-right">{c.current_hp}/{c.max_hp}</div>
              <div className="w-full h-1.5 bg-gray-700 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${
                    hpPct > 50 ? "bg-emerald-500" : hpPct > 25 ? "bg-yellow-500" : "bg-red-500"
                  }`}
                  style={{ width: `${hpPct}%` }}
                />
              </div>
            </div>

            {/* AC */}
            <div className="text-center min-w-[2rem]">
              <div className="text-[10px] text-gray-500">AC</div>
              <div className="text-sm font-bold text-blue-300">{c.armor_class}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
