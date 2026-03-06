import type { ToolRendererProps } from "./toolRendererRegistry";

const DIFFICULTY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  easy:   { bg: "bg-green-900/30",  text: "text-green-300",  border: "border-green-700/40" },
  medium: { bg: "bg-amber-900/30",  text: "text-amber-300",  border: "border-amber-700/40" },
  hard:   { bg: "bg-orange-900/30", text: "text-orange-300", border: "border-orange-700/40" },
  deadly: { bg: "bg-red-900/30",    text: "text-red-300",    border: "border-red-700/40" },
};

interface EncounterBalanceData {
  type: "encounter_balance";
  difficulty: string;
  adjusted_xp: number;
  raw_xp: number;
  multiplier: number;
  thresholds: Record<string, number>;
  enemies: { cr: string; xp: number }[];
  party_levels: number[];
  recommendation: string;
  error?: string;
}

interface MonsterGeneratedData {
  type: "monster_generated";
  name: string;
  cr: string;
  xp_value: number;
  creature_type: string;
  race: string;
  class: string;
  level: number;
  max_hp: number;
  current_hp: number;
  armor_class: number;
  attack_bonus: number;
  damage_per_round: string;
  save_dc: number;
  abilities: Record<string, { score: number; modifier: number }>;
  error?: string;
}

interface XPRewardData {
  type: "xp_reward";
  total_xp: number;
  xp_per_character: number;
  characters: {
    name: string;
    xp_gained: number;
    total_xp: number;
    level: number;
    leveled_up: boolean;
    old_level: number | null;
  }[];
  defeated_enemies: { name: string; cr: string; xp: number }[];
  error?: string;
}

type EncounterData = EncounterBalanceData | MonsterGeneratedData | XPRewardData;

const ABILITY_SHORT: Record<string, string> = {
  strength: "STR", dexterity: "DEX", constitution: "CON",
  intelligence: "INT", wisdom: "WIS", charisma: "CHA",
};

const CREATURE_ICONS: Record<string, string> = {
  beast: "\uD83D\uDC3E", humanoid: "\uD83E\uDDD1", undead: "\uD83D\uDC80",
  fiend: "\uD83D\uDD25", dragon: "\uD83D\uDC32", construct: "\u2699\uFE0F",
  aberration: "\uD83D\uDC7E", elemental: "\uD83C\uDF0A", monstrosity: "\uD83D\uDC79",
  giant: "\uD83E\uDDBE", fey: "\u2728", celestial: "\uD83D\uDE07",
  plant: "\uD83C\uDF3F", ooze: "\uD83E\uDDA0",
};

function DifficultyBadge({ difficulty }: { difficulty: string }) {
  const colors = DIFFICULTY_COLORS[difficulty] || DIFFICULTY_COLORS.medium;
  return (
    <span className={`text-xs font-bold px-2 py-0.5 rounded ${colors.bg} ${colors.text} border ${colors.border} uppercase`}>
      {difficulty}
    </span>
  );
}

function EncounterBalanceView({ d }: { d: EncounterBalanceData }) {
  const colors = DIFFICULTY_COLORS[d.difficulty] || DIFFICULTY_COLORS.medium;
  const maxThreshold = d.thresholds.deadly || 1;
  const xpPct = Math.min(100, (d.adjusted_xp / maxThreshold) * 100);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-lg">{"\u2696\uFE0F"}</span>
          <span className="text-sm font-bold text-gray-200">ENCOUNTER BALANCE</span>
        </div>
        <DifficultyBadge difficulty={d.difficulty} />
      </div>

      {/* XP bar */}
      <div>
        <div className="flex justify-between text-[10px] text-gray-500 mb-0.5">
          <span>Adjusted XP: {d.adjusted_xp.toLocaleString()}</span>
          <span>x{d.multiplier} multiplier</span>
        </div>
        <div className="w-full h-2 bg-gray-700 rounded-full overflow-hidden relative">
          <div className={`h-full rounded-full ${colors.bg.replace("/30", "")} opacity-70`} style={{ width: `${xpPct}%` }} />
          {/* Threshold markers */}
          {(["easy", "medium", "hard", "deadly"] as const).map((diff) => {
            const pct = Math.min(100, (d.thresholds[diff] / maxThreshold) * 100);
            return (
              <div
                key={diff}
                className="absolute top-0 h-full w-px bg-gray-500/60"
                style={{ left: `${pct}%` }}
                title={`${diff}: ${d.thresholds[diff]} XP`}
              />
            );
          })}
        </div>
        <div className="flex justify-between text-[9px] text-gray-600 mt-0.5">
          <span>Easy {d.thresholds.easy}</span>
          <span>Medium {d.thresholds.medium}</span>
          <span>Hard {d.thresholds.hard}</span>
          <span>Deadly {d.thresholds.deadly}</span>
        </div>
      </div>

      {/* Enemy CR pills */}
      <div className="flex flex-wrap gap-1">
        {d.enemies.map((e, i) => (
          <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-gray-700/50 text-gray-300 border border-gray-600/30">
            CR {e.cr} ({e.xp} XP)
          </span>
        ))}
      </div>

      {/* Party info */}
      <div className="text-[10px] text-gray-500">
        Party: {d.party_levels.length} characters (levels {d.party_levels.join(", ")}) | Raw XP: {d.raw_xp.toLocaleString()}
      </div>

      {d.recommendation && (
        <div className={`text-xs italic ${colors.text} opacity-80`}>{d.recommendation}</div>
      )}
    </div>
  );
}

function MonsterGeneratedView({ d }: { d: MonsterGeneratedData }) {
  const icon = CREATURE_ICONS[d.creature_type] || "\uD83D\uDC79";
  const abilities = d.abilities || {};

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-lg">{icon}</span>
          <span className="text-sm font-bold text-gray-200">{d.name}</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-900/30 text-purple-300 border border-purple-700/30">
            {d.creature_type}
          </span>
        </div>
        <span className="text-xs font-bold px-2 py-0.5 rounded bg-red-900/30 text-red-300 border border-red-700/40">
          CR {d.cr}
        </span>
      </div>

      {/* Stats row */}
      <div className="flex gap-3 text-xs">
        <div className="flex items-center gap-1">
          <span className="text-red-400">{"\u2764\uFE0F"}</span>
          <span className="text-gray-300 font-bold">{d.max_hp}</span>
          <span className="text-gray-500">HP</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-blue-400">{"\uD83D\uDEE1\uFE0F"}</span>
          <span className="text-gray-300 font-bold">{d.armor_class}</span>
          <span className="text-gray-500">AC</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-amber-400">{"\u2694\uFE0F"}</span>
          <span className="text-gray-300 font-bold">+{d.attack_bonus}</span>
          <span className="text-gray-500">atk</span>
        </div>
        <div className="flex items-center gap-1">
          <span className="text-orange-400">{"\uD83D\uDCA5"}</span>
          <span className="text-gray-300 font-bold">{d.damage_per_round}</span>
          <span className="text-gray-500">dmg</span>
        </div>
        <div className="flex items-center gap-1 text-gray-500">
          DC {d.save_dc}
        </div>
      </div>

      {/* Ability scores grid */}
      <div className="grid grid-cols-6 gap-1">
        {Object.entries(abilities).map(([key, val]) => (
          <div key={key} className="text-center bg-gray-800/50 rounded px-1 py-0.5 border border-gray-700/30">
            <div className="text-[9px] text-gray-500 uppercase">{ABILITY_SHORT[key] || key}</div>
            <div className="text-xs text-gray-300 font-bold">{val.score}</div>
            <div className="text-[9px] text-gray-500">
              {val.modifier >= 0 ? "+" : ""}{val.modifier}
            </div>
          </div>
        ))}
      </div>

      <div className="text-[10px] text-gray-500">
        {d.xp_value} XP | Level {d.level}
      </div>
    </div>
  );
}

function XPRewardView({ d }: { d: XPRewardData }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-lg">{"\u2B50"}</span>
          <span className="text-sm font-bold text-amber-200">XP REWARD</span>
        </div>
        <span className="text-xs font-bold px-2 py-0.5 rounded bg-amber-900/30 text-amber-300 border border-amber-700/40">
          {d.total_xp.toLocaleString()} XP
        </span>
      </div>

      {/* Per-character breakdown */}
      <div className="space-y-1">
        {d.characters.map((c) => (
          <div
            key={c.name}
            className={`flex items-center justify-between rounded-lg px-3 py-1.5 border ${
              c.leveled_up
                ? "bg-green-900/20 border-green-600/40 ring-1 ring-green-500/20"
                : "bg-gray-800/40 border-gray-700/30"
            }`}
          >
            <div className="flex items-center gap-2">
              <span className={`text-sm ${c.leveled_up ? "text-green-300 font-medium" : "text-gray-300"}`}>
                {c.name}
              </span>
              {c.leveled_up && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-900/40 text-green-300 border border-green-700/40 font-bold">
                  LEVEL UP! {c.old_level} {"\u2192"} {c.level}
                </span>
              )}
            </div>
            <div className="text-right">
              <div className="text-xs text-amber-300 font-bold">+{c.xp_gained} XP</div>
              <div className="text-[10px] text-gray-500">Total: {c.total_xp.toLocaleString()}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Defeated enemies */}
      {d.defeated_enemies && d.defeated_enemies.length > 0 && (
        <div className="flex flex-wrap gap-1">
          <span className="text-[10px] text-gray-500">Defeated:</span>
          {d.defeated_enemies.map((e, i) => (
            <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-gray-700/50 text-gray-400 border border-gray-600/30">
              {e.name} (CR {e.cr}, {e.xp} XP)
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export function EncounterRenderer({ data }: ToolRendererProps) {
  const d = data as unknown as EncounterData;

  if ("error" in d && d.error) {
    return <div className="mt-2 text-red-400 text-sm">{d.error}</div>;
  }

  return (
    <div className="mt-2 bg-gray-800/30 rounded-lg px-3 py-2.5 border border-gray-700/30 space-y-2">
      {d.type === "encounter_balance" && <EncounterBalanceView d={d as EncounterBalanceData} />}
      {d.type === "monster_generated" && <MonsterGeneratedView d={d as MonsterGeneratedData} />}
      {d.type === "xp_reward" && <XPRewardView d={d as XPRewardData} />}
    </div>
  );
}
