import type { ToolRendererProps } from "./toolRendererRegistry";

interface DamageData {
  character: string;
  damage: number;
  damage_type: string;
  current_hp: number;
  max_hp: number;
  dropped_to_zero: boolean;
  needs_death_saves: boolean;
  error?: string;
}

export function DamageResultRenderer({ data }: ToolRendererProps) {
  const d = data as unknown as DamageData;

  if (d.error) {
    return <div className="mt-2 text-red-400 text-sm">{d.error}</div>;
  }

  const hpPct = Math.max(0, (d.current_hp / Math.max(d.max_hp, 1)) * 100);

  return (
    <div className="mt-2 space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-lg">{d.dropped_to_zero ? "\uD83D\uDCA5" : "\uD83E\uDE78"}</span>
        <span className="text-sm">
          <span className="text-red-300 font-medium">{d.character}</span>
          <span className="text-gray-400"> takes </span>
          <span className="text-red-400 font-bold">{d.damage}</span>
          <span className="text-gray-500"> {d.damage_type} damage</span>
        </span>
      </div>

      {/* HP bar */}
      <div>
        <div className="flex justify-between text-xs mb-0.5">
          <span className="text-gray-500">HP</span>
          <span className="text-gray-300">{d.current_hp}/{d.max_hp}</span>
        </div>
        <div className="w-full h-2.5 bg-gray-800 rounded-full overflow-hidden border border-gray-700">
          <div
            className={`h-full rounded-full transition-all ${
              hpPct > 50 ? "bg-emerald-500" : hpPct > 25 ? "bg-yellow-500" : "bg-red-500"
            }`}
            style={{ width: `${hpPct}%` }}
          />
        </div>
      </div>

      {d.dropped_to_zero && (
        <div className="text-xs bg-red-900/30 text-red-300 px-2 py-1 rounded border border-red-700/40 font-medium">
          {d.character} drops to 0 HP! Death saves required!
        </div>
      )}
    </div>
  );
}
