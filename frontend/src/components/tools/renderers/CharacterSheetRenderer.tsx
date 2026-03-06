import type { ToolRendererProps } from "./toolRendererRegistry";
import { ABILITY_ORDER, ABILITY_ABBR, RACE_ICONS } from "@/constants/rpg";

interface AbilityScore {
  score: number;
  modifier: number;
}

interface CharacterData {
  name: string;
  race: string;
  class: string;
  level: number;
  xp: number;
  xp_next_level: number | null;
  proficiency_bonus: number;
  abilities: Record<string, AbilityScore>;
  max_hp: number;
  current_hp: number;
  temp_hp: number;
  armor_class: number;
  speed: number;
  conditions: string[];
  hit_die: string;
  is_player: boolean;
  is_alive: boolean;
  changes?: string[];
  error?: string;
}

export function CharacterSheetRenderer({ data }: ToolRendererProps) {
  const d = data as unknown as CharacterData;

  if (d.error) {
    return <div className="mt-2 text-red-400 text-sm">{d.error}</div>;
  }

  const hpPct = Math.max(0, Math.min(100, (d.current_hp / Math.max(d.max_hp, 1)) * 100));
  const hpColor = hpPct > 50 ? "from-emerald-500 to-emerald-400" : hpPct > 25 ? "from-yellow-500 to-amber-400" : "from-red-500 to-red-400";

  return (
    <div className="mt-2 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-lg font-bold text-white">{d.name}</span>
            <span className="text-[11px] px-2 py-0.5 rounded-full bg-amber-900/40 text-amber-300 border border-amber-700/30 font-medium">
              Lv {d.level}
            </span>
            {!d.is_alive && <span className="text-red-400 text-xs">(Dead)</span>}
          </div>
          <div className="text-xs text-gray-400 flex items-center gap-1 mt-0.5">
            <span>{RACE_ICONS[d.race.toLowerCase()] || "\uD83D\uDC64"}</span>
            <span>{d.race} {d.class}</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {/* AC Shield */}
          <div className="relative flex items-center justify-center w-12 h-14">
            <svg viewBox="0 0 40 48" className="w-full h-full">
              <path
                d="M20 2 L38 10 L38 24 C38 36 20 46 20 46 C20 46 2 36 2 24 L2 10 Z"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                className="text-blue-500/60"
              />
              <path
                d="M20 2 L38 10 L38 24 C38 36 20 46 20 46 C20 46 2 36 2 24 L2 10 Z"
                className="fill-blue-900/40"
              />
            </svg>
            <span className="absolute text-sm font-black text-blue-200">{d.armor_class}</span>
          </div>
          {/* Speed */}
          <div className="text-center">
            <div className="text-xs text-gray-500">SPD</div>
            <div className="text-sm font-bold text-gray-200">{d.speed}ft</div>
          </div>
        </div>
      </div>

      {/* HP Bar */}
      <div>
        <div className="flex justify-between text-xs mb-1">
          <span className="text-gray-400">HP</span>
          <span className="text-gray-300 font-medium">
            {d.current_hp}/{d.max_hp}
            {d.temp_hp > 0 && <span className="text-blue-400"> +{d.temp_hp} temp</span>}
          </span>
        </div>
        <div className="w-full h-3 bg-gray-800 rounded-full overflow-hidden border border-gray-700">
          <div
            className={`h-full rounded-full bg-gradient-to-r ${hpColor} transition-all duration-500`}
            style={{ width: `${hpPct}%` }}
          />
        </div>
      </div>

      {/* Ability Scores Grid */}
      <div className="grid grid-cols-6 gap-1.5">
        {ABILITY_ORDER.map((ab) => {
          const { score, modifier } = d.abilities[ab] || { score: 10, modifier: 0 };
          return (
            <div
              key={ab}
              className="text-center bg-gray-800/60 rounded-lg py-1.5 border border-gray-700/50"
            >
              <div className="text-[10px] text-gray-500 font-medium">{ABILITY_ABBR[ab]}</div>
              <div className="text-lg font-black text-white leading-tight">{score}</div>
              <div className={`text-xs font-medium ${modifier >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                {modifier >= 0 ? "+" : ""}{modifier}
              </div>
            </div>
          );
        })}
      </div>

      {/* Extra info row */}
      <div className="flex flex-wrap gap-2 text-xs">
        <span className="bg-purple-900/40 text-purple-300 px-2 py-0.5 rounded border border-purple-700/40">
          Prof +{d.proficiency_bonus}
        </span>
        <span className="bg-gray-800 text-gray-300 px-2 py-0.5 rounded border border-gray-700/40">
          {d.hit_die}
        </span>
        {d.xp_next_level && (
          <span className="bg-gray-800 text-gray-400 px-2 py-0.5 rounded border border-gray-700/40">
            XP: {d.xp}/{d.xp_next_level}
          </span>
        )}
      </div>

      {/* Conditions */}
      {d.conditions.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {d.conditions.map((c) => (
            <span key={c} className="px-2 py-0.5 rounded-full text-xs bg-red-900/40 text-red-300 border border-red-700/40">
              {c}
            </span>
          ))}
        </div>
      )}

      {/* Changes log */}
      {d.changes && d.changes.length > 0 && (
        <div className="text-xs space-y-0.5 border-t border-gray-700/50 pt-2">
          {d.changes.map((c, i) => (
            <div key={i} className={`${c.includes("LEVEL UP") ? "text-yellow-300 font-bold" : "text-gray-400"}`}>
              {c.includes("LEVEL UP") ? "\u2B50 " : "\u2022 "}{c}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
