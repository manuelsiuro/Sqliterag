import type { ToolRendererProps } from "./toolRendererRegistry";

interface RestData {
  rest_type: string;
  character: string;
  hit_dice_spent?: number;
  hit_die_type?: string;
  rolls?: number[];
  con_modifier?: number;
  hp_healed: number;
  hp_before: number;
  hp_after: number;
  max_hp: number;
  conditions_removed?: string[];
  spell_slots_restored?: boolean;
  error?: string;
}

export function RestResultRenderer({ data }: ToolRendererProps) {
  const d = data as unknown as RestData;

  if (d.error) {
    return <div className="mt-2 text-red-400 text-sm">{d.error}</div>;
  }

  const isLong = d.rest_type === "long";
  const beforePct = Math.max(0, (d.hp_before / Math.max(d.max_hp, 1)) * 100);
  const afterPct = Math.max(0, (d.hp_after / Math.max(d.max_hp, 1)) * 100);

  return (
    <div className="mt-2 space-y-2">
      {/* Header */}
      <div className="flex items-center gap-2">
        <span className="text-lg">{isLong ? "\uD83C\uDF19" : "\u2615"}</span>
        <div>
          <div className="text-sm font-medium text-blue-200">
            {d.character} — {isLong ? "Long Rest" : "Short Rest"}
          </div>
        </div>
      </div>

      {/* Hit dice spent (short rest only) */}
      {!isLong && d.rolls && d.rolls.length > 0 && (
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">Hit dice ({d.hit_die_type}):</span>
          <div className="flex gap-1">
            {d.rolls.map((r, i) => (
              <span
                key={i}
                className="w-7 h-7 rounded flex items-center justify-center text-xs font-bold bg-blue-800/50 text-blue-200 border border-blue-700/40"
              >
                {r}
              </span>
            ))}
          </div>
          {d.con_modifier !== undefined && d.con_modifier !== 0 && (
            <span className="text-xs text-gray-500">
              +{d.con_modifier} CON per die
            </span>
          )}
        </div>
      )}

      {/* HP before/after */}
      <div className="space-y-1">
        <div className="flex items-center gap-2 text-xs">
          <span className="text-gray-500 w-12">Before:</span>
          <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden border border-gray-700">
            <div className="h-full rounded-full bg-gray-500" style={{ width: `${beforePct}%` }} />
          </div>
          <span className="text-gray-400 w-16 text-right">{d.hp_before}/{d.max_hp}</span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="text-gray-500 w-12">After:</span>
          <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden border border-gray-700">
            <div className="h-full rounded-full bg-emerald-500" style={{ width: `${afterPct}%` }} />
          </div>
          <span className="text-emerald-300 w-16 text-right font-medium">{d.hp_after}/{d.max_hp}</span>
        </div>
      </div>

      {/* Healed amount */}
      {d.hp_healed > 0 && (
        <div className="text-sm text-emerald-400 font-medium">
          +{d.hp_healed} HP restored
        </div>
      )}

      {/* Extra effects for long rest */}
      {isLong && (
        <div className="flex flex-wrap gap-1.5 text-xs">
          {d.spell_slots_restored && (
            <span className="px-2 py-0.5 rounded bg-purple-900/30 text-purple-300 border border-purple-700/40">
              Spell slots restored
            </span>
          )}
          {d.conditions_removed && d.conditions_removed.length > 0 && (
            <span className="px-2 py-0.5 rounded bg-emerald-900/30 text-emerald-300 border border-emerald-700/40">
              Removed: {d.conditions_removed.join(", ")}
            </span>
          )}
          <span className="px-2 py-0.5 rounded bg-blue-900/30 text-blue-300 border border-blue-700/40">
            Death saves reset
          </span>
        </div>
      )}
    </div>
  );
}
