import type { ToolRendererProps } from "./toolRendererRegistry";

interface Combatant {
  name: string;
  roll: number;
  modifier: number;
  total: number;
  current_hp: number;
  max_hp: number;
  armor_class: number;
  conditions?: string[];
}

interface InitiativeData {
  round: number;
  current_turn: string;
  order: Combatant[];
  message?: string;
  error?: string;
}

export function InitiativeOrderRenderer({ data }: ToolRendererProps) {
  const d = data as unknown as InitiativeData;

  if (d.error) {
    return <div className="mt-2 text-red-400 text-sm">{d.error}</div>;
  }

  return (
    <div className="mt-2 space-y-2">
      {/* Round counter */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-red-400 text-lg">&#9876;</span>
          <span className="text-sm font-bold text-red-300">COMBAT</span>
        </div>
        <span className="text-xs bg-red-900/30 text-red-300 px-2 py-0.5 rounded border border-red-700/40">
          Round {d.round}
        </span>
      </div>

      {d.message && (
        <div className="text-xs text-gray-400 italic">{d.message}</div>
      )}

      {/* Turn tracker */}
      <div className="space-y-1">
        {d.order.map((c, i) => {
          const isActive = c.name === d.current_turn;
          const hpPct = Math.max(0, (c.current_hp / Math.max(c.max_hp, 1)) * 100);
          const hpColor = hpPct > 50 ? "bg-emerald-500" : hpPct > 25 ? "bg-yellow-500" : "bg-red-500";

          return (
            <div
              key={c.name}
              className={`flex items-center gap-2 rounded-lg px-3 py-1.5 border transition-all ${
                isActive
                  ? "bg-amber-900/30 border-amber-600/50 ring-1 ring-amber-500/30"
                  : "bg-gray-800/40 border-gray-700/30"
              }`}
            >
              {/* Initiative number */}
              <span className={`w-7 text-center text-sm font-bold ${isActive ? "text-amber-300" : "text-gray-500"}`}>
                {c.total}
              </span>

              {/* Active arrow */}
              <span className={`text-sm ${isActive ? "text-amber-400" : "text-transparent"}`}>&#9654;</span>

              {/* Name */}
              <span className={`flex-1 text-sm truncate ${isActive ? "text-white font-medium" : "text-gray-300"}`}>
                {c.name}
              </span>

              {/* Conditions */}
              {c.conditions && c.conditions.length > 0 && (
                <div className="flex gap-0.5">
                  {c.conditions.map((cond) => (
                    <span key={cond} className="text-[9px] px-1 py-0.5 rounded bg-red-900/40 text-red-400 border border-red-800/40">
                      {cond}
                    </span>
                  ))}
                </div>
              )}

              {/* HP */}
              <div className="w-16 text-right">
                <div className="text-[10px] text-gray-500">{c.current_hp}/{c.max_hp}</div>
                <div className="w-full h-1 bg-gray-700 rounded-full overflow-hidden">
                  <div className={`h-full rounded-full ${hpColor}`} style={{ width: `${hpPct}%` }} />
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
