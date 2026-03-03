import type { ToolRendererProps } from "./toolRendererRegistry";

interface DiceData {
  rolls: number[];
  modifier: number;
  total: number;
}

export function DiceResultRenderer({ data }: ToolRendererProps) {
  const { rolls, modifier, total } = data as unknown as DiceData;

  if (!rolls?.length) {
    return <div className="mt-2 text-gray-500 text-sm">No rolls</div>;
  }

  return (
    <div className="mt-2">
      {/* Dice row */}
      <div className="flex flex-wrap gap-2">
        {rolls.map((roll, i) => {
          const isNat20 = roll === 20;
          const isNat1 = roll === 1;

          return (
            <div
              key={i}
              className={`
                w-12 h-12 rounded-lg flex items-center justify-center
                text-lg font-bold border
                animate-dice-pop
                ${
                  isNat20
                    ? "bg-gradient-to-br from-yellow-600 to-yellow-800 border-yellow-400 ring-2 ring-yellow-400/60 text-yellow-300 shadow-[0_0_12px_rgba(250,204,21,0.4)]"
                    : isNat1
                      ? "bg-gradient-to-br from-green-700 to-green-900 border-red-500/50 text-red-300 opacity-70"
                      : "bg-gradient-to-br from-green-700 to-green-900 border-green-500/50 text-white"
                }
              `}
              style={{ animationDelay: `${i * 80}ms` }}
            >
              {roll}
            </div>
          );
        })}
      </div>

      {/* Modifier + Total */}
      <div className="mt-3 flex items-baseline gap-3">
        {modifier !== 0 && (
          <span className="text-green-400 text-sm">
            Modifier: {modifier >= 0 ? `+${modifier}` : modifier}
          </span>
        )}
        <span className="text-white text-xl font-bold">
          Total: {total}
        </span>
      </div>
    </div>
  );
}
