import type { ToolRendererProps } from "./toolRendererRegistry";

interface DeathSaveData {
  character: string;
  roll: number;
  successes: number;
  failures: number;
  stabilized: boolean;
  dead: boolean;
  message: string;
  error?: string;
}

export function DeathSaveRenderer({ data }: ToolRendererProps) {
  const d = data as unknown as DeathSaveData;

  if (d.error) {
    return <div className="mt-2 text-red-400 text-sm">{d.error}</div>;
  }

  const isNat20 = d.roll === 20;
  const isNat1 = d.roll === 1;

  return (
    <div className="mt-2 space-y-3">
      {/* Header */}
      <div className="flex items-center gap-2">
        <span className="text-lg">{d.dead ? "\uD83D\uDC80" : d.stabilized ? "\uD83D\uDC9A" : "\u2620\uFE0F"}</span>
        <span className="text-sm font-medium text-gray-300">{d.character} — Death Save</span>
      </div>

      {/* Roll */}
      <div className="flex items-center gap-3">
        <div
          className={`
            w-14 h-14 rounded-xl flex items-center justify-center
            text-xl font-black border-2 animate-dice-pop
            ${isNat20
              ? "bg-gradient-to-br from-yellow-500 to-amber-700 border-yellow-300 text-yellow-100 shadow-[0_0_16px_rgba(250,204,21,0.5)]"
              : isNat1
                ? "bg-gradient-to-br from-red-700 to-red-900 border-red-400 text-red-200 shadow-[0_0_12px_rgba(239,68,68,0.5)]"
                : d.roll >= 10
                  ? "bg-gradient-to-br from-emerald-600 to-emerald-800 border-emerald-400 text-emerald-100"
                  : "bg-gradient-to-br from-gray-600 to-gray-800 border-gray-500 text-gray-200"
            }
          `}
        >
          {d.roll}
        </div>
        <span className="text-sm text-gray-400">{d.message}</span>
      </div>

      {/* Success / Failure circles */}
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-gray-500">Saves:</span>
          {[0, 1, 2].map((i) => (
            <div
              key={`s${i}`}
              className={`w-5 h-5 rounded-full border-2 ${
                i < d.successes
                  ? "bg-emerald-500 border-emerald-400"
                  : "bg-gray-800 border-gray-600"
              }`}
            />
          ))}
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-xs text-gray-500">Fails:</span>
          {[0, 1, 2].map((i) => (
            <div
              key={`f${i}`}
              className={`w-5 h-5 rounded-full border-2 ${
                i < d.failures
                  ? "bg-red-500 border-red-400"
                  : "bg-gray-800 border-gray-600"
              }`}
            />
          ))}
        </div>
      </div>

      {/* Status */}
      {d.dead && (
        <div className="text-center py-2 bg-red-900/30 rounded border border-red-700/40 text-red-300 font-bold text-sm">
          {d.character} has died.
        </div>
      )}
      {d.stabilized && !d.dead && (
        <div className="text-center py-2 bg-emerald-900/30 rounded border border-emerald-700/40 text-emerald-300 font-bold text-sm">
          {d.character} is stabilized!
        </div>
      )}
    </div>
  );
}
