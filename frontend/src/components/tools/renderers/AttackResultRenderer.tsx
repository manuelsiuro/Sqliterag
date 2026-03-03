import type { ToolRendererProps } from "./toolRendererRegistry";

interface AttackData {
  attacker: string;
  target: string;
  weapon: string;
  attack_rolls: number[];
  chosen_roll: number;
  attack_modifier: number;
  attack_total: number;
  target_ac: number;
  hit: boolean;
  critical: boolean;
  fumble: boolean;
  damage: number;
  damage_rolls: number[];
  damage_modifier: number;
  target_hp: string;
  error?: string;
}

export function AttackResultRenderer({ data }: ToolRendererProps) {
  const d = data as unknown as AttackData;

  if (d.error) {
    return <div className="mt-2 text-red-400 text-sm">{d.error}</div>;
  }

  return (
    <div className="mt-2 space-y-3">
      {/* Header */}
      <div className="text-sm">
        <span className="text-red-300 font-medium">{d.attacker}</span>
        <span className="text-gray-500"> attacks </span>
        <span className="text-blue-300 font-medium">{d.target}</span>
        <span className="text-gray-600 text-xs ml-1">({d.weapon})</span>
      </div>

      {/* Attack roll */}
      <div className="flex items-center gap-3">
        <div
          className={`
            w-12 h-12 rounded-xl flex items-center justify-center
            text-lg font-black border-2 animate-dice-pop
            ${d.critical
              ? "bg-gradient-to-br from-yellow-500 to-amber-700 border-yellow-300 text-yellow-100 shadow-[0_0_16px_rgba(250,204,21,0.5)]"
              : d.fumble
                ? "bg-gradient-to-br from-red-700 to-red-900 border-red-400 text-red-200"
                : d.hit
                  ? "bg-gradient-to-br from-emerald-600 to-emerald-800 border-emerald-400 text-emerald-100"
                  : "bg-gradient-to-br from-gray-600 to-gray-800 border-gray-500 text-gray-300"
            }
          `}
        >
          {d.chosen_roll}
        </div>
        <div className="flex flex-col">
          <span className="text-sm text-gray-300">
            {d.chosen_roll} + {d.attack_modifier} = <strong className="text-white">{d.attack_total}</strong>
            <span className="text-gray-500"> vs AC {d.target_ac}</span>
          </span>
          {d.attack_rolls.length > 1 && (
            <span className="text-xs text-gray-500">Rolls: [{d.attack_rolls.join(", ")}]</span>
          )}
        </div>
      </div>

      {/* Hit/Miss badge */}
      {d.critical ? (
        <div className="flex items-center gap-2">
          <span className="px-3 py-1 rounded-full text-sm font-black bg-yellow-500/20 text-yellow-300 border border-yellow-500/40 animate-pulse">
            CRITICAL HIT!
          </span>
        </div>
      ) : d.fumble ? (
        <span className="px-3 py-1 rounded-full text-sm font-bold bg-red-500/20 text-red-300 border border-red-500/40">
          FUMBLE!
        </span>
      ) : d.hit ? (
        <span className="px-3 py-1 rounded-full text-sm font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
          HIT
        </span>
      ) : (
        <span className="px-3 py-1 rounded-full text-sm font-bold bg-gray-500/20 text-gray-400 border border-gray-500/40">
          MISS
        </span>
      )}

      {/* Damage */}
      {d.hit && d.damage > 0 && (
        <div className="flex items-center gap-3 bg-red-900/20 rounded-lg px-3 py-2 border border-red-800/30">
          <div className="flex gap-1">
            {d.damage_rolls?.length > 0 && d.damage_rolls.map((r, i) => (
              <span
                key={i}
                className="w-7 h-7 rounded flex items-center justify-center text-xs font-bold bg-red-800/60 text-red-200 border border-red-700/50"
              >
                {r}
              </span>
            ))}
          </div>
          <span className="text-xs text-gray-500">+{d.damage_modifier}</span>
          <span className="text-lg font-black text-red-300">
            {d.damage} dmg
            {d.critical && <span className="text-yellow-400 text-xs font-bold ml-1">(Critical - 2x dice)</span>}
          </span>
          <span className="text-xs text-gray-500 ml-auto">{d.target}: {d.target_hp}</span>
        </div>
      )}
    </div>
  );
}
