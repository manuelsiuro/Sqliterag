import type { ToolRendererProps } from "./toolRendererRegistry";

interface HealData {
  healer: string;
  target: string;
  amount_healed: number;
  current_hp: number;
  max_hp: number;
  error?: string;
}

export function HealResultRenderer({ data }: ToolRendererProps) {
  const d = data as unknown as HealData;

  if (d.error) {
    return <div className="mt-2 text-red-400 text-sm">{d.error}</div>;
  }

  const hpPct = Math.max(0, (d.current_hp / Math.max(d.max_hp, 1)) * 100);

  return (
    <div className="mt-2 space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-lg">{"💚"}</span>
        <span className="text-sm">
          <span className="text-emerald-300 font-medium">{d.healer}</span>
          <span className="text-gray-400"> heals </span>
          <span className="text-blue-300 font-medium">{d.target}</span>
          <span className="text-gray-400"> for </span>
          <span className="text-emerald-400 font-bold">+{d.amount_healed} HP</span>
        </span>
      </div>

      {/* HP bar */}
      <div>
        <div className="flex justify-between text-xs mb-0.5">
          <span className="text-gray-500">HP</span>
          <span className="text-emerald-300 font-medium">{d.current_hp}/{d.max_hp}</span>
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
    </div>
  );
}
