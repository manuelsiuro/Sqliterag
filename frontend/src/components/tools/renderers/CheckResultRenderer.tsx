import type { ToolRendererProps } from "./toolRendererRegistry";

interface CheckData {
  character: string;
  ability: string;
  check_type?: string;
  rolls: number[];
  chosen: number;
  modifier: number;
  total: number;
  dc: number;
  success: boolean;
  nat20: boolean;
  nat1: boolean;
  advantage?: boolean;
  disadvantage?: boolean;
  error?: string;
}

export function CheckResultRenderer({ data }: ToolRendererProps) {
  const d = data as unknown as CheckData;

  if (d.error) {
    return <div className="mt-2 text-red-400 text-sm">{d.error}</div>;
  }

  const pct = Math.min(100, Math.max(0, (d.total / Math.max(d.dc, 1)) * 100));
  const isCheckType = d.check_type === "saving_throw" ? "Saving Throw" : "Ability Check";

  return (
    <div className="mt-2 bg-gray-800/30 rounded-lg px-3 py-2.5 border border-gray-700/30 space-y-2">
      {/* Header */}
      <div className="flex items-center gap-2 text-sm">
        <span className="text-purple-300 font-medium">{d.character}</span>
        <span className="text-gray-500">&mdash;</span>
        <span className="capitalize text-gray-300">{d.ability} {isCheckType}</span>
        {d.advantage && <span className="text-green-400 text-xs bg-green-900/40 px-1.5 rounded">ADV</span>}
        {d.disadvantage && <span className="text-red-400 text-xs bg-red-900/40 px-1.5 rounded">DIS</span>}
      </div>

      {/* D20 roll display */}
      <div className="flex items-center gap-3">
        <div
          className={`
            w-14 h-14 rounded-xl flex items-center justify-center
            text-xl font-black border-2 animate-dice-pop
            ${d.nat20
              ? "bg-gradient-to-br from-yellow-500 to-amber-700 border-yellow-300 text-yellow-100 shadow-[0_0_16px_rgba(250,204,21,0.5)] ring-2 ring-yellow-400/60"
              : d.nat1
                ? "bg-gradient-to-br from-red-700 to-red-900 border-red-400 text-red-200 shadow-[0_0_12px_rgba(239,68,68,0.4)]"
                : d.success
                  ? "bg-gradient-to-br from-emerald-600 to-emerald-800 border-emerald-400 text-emerald-100"
                  : "bg-gradient-to-br from-gray-600 to-gray-800 border-gray-500 text-gray-200"
            }
          `}
        >
          {d.chosen}
        </div>

        {/* Breakdown */}
        <div className="flex flex-col gap-1">
          <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-gray-800/60 text-gray-400 border border-gray-700/40 w-fit">
            {d.rolls.length > 1
              ? <>🎲 [{d.rolls.join(", ")}] → <span className="text-gray-200 font-medium">{d.chosen}</span></>
              : <>🎲 d20: <span className="text-gray-200 font-medium">{d.chosen}</span></>
            }
          </span>
          <span className="text-sm text-gray-300">
            {d.chosen} {d.modifier >= 0 ? "+" : ""}{d.modifier} = <strong className="text-white">{d.total}</strong>
          </span>
        </div>
      </div>

      {/* DC bar */}
      <div className="relative">
        <div className="w-full h-3 bg-gray-800 rounded-full overflow-hidden border border-gray-700">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              d.success
                ? "bg-gradient-to-r from-emerald-500 to-emerald-400"
                : "bg-gradient-to-r from-red-600 to-red-500"
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className="flex justify-between text-xs mt-0.5">
          <span className="text-gray-500">Total: {d.total}</span>
          <span className="text-gray-500">DC {d.dc}</span>
        </div>
      </div>

      {/* Result badge */}
      <div className="flex items-center gap-2">
        {d.nat20 ? (
          <span className="px-3 py-1 rounded-full text-sm font-bold bg-yellow-500/20 text-yellow-300 border border-yellow-500/40">
            NATURAL 20!
          </span>
        ) : d.nat1 ? (
          <span className="px-3 py-1 rounded-full text-sm font-bold bg-red-500/20 text-red-300 border border-red-500/40">
            NATURAL 1!
          </span>
        ) : d.success ? (
          <span className="px-3 py-1 rounded-full text-sm font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
            SUCCESS
          </span>
        ) : (
          <span className="px-3 py-1 rounded-full text-sm font-bold bg-red-500/20 text-red-300 border border-red-500/40">
            FAILURE
          </span>
        )}
      </div>
    </div>
  );
}
