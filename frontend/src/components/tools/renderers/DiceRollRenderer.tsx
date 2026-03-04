import type { ToolRendererProps } from "./toolRendererRegistry";

interface DiceGroupData {
  dice: string;
  rolls: { value: number; kept: boolean; exploded: boolean; rerolled: boolean; original?: number }[];
  subtotal: number;
}

interface DiceRollData {
  notation: string;
  label: string;
  groups: DiceGroupData[];
  flat_modifier: number;
  total: number;
}

export function DiceRollRenderer({ data }: ToolRendererProps) {
  const { notation, label, groups, flat_modifier, total } =
    data as unknown as DiceRollData;

  return (
    <div className="mt-2 bg-gray-800/30 rounded-lg px-3 py-2.5 border border-gray-700/30 space-y-3">
      {/* Header */}
      <div className="flex items-center gap-2 text-sm text-gray-400">
        <span className="font-mono bg-gray-800 px-2 py-0.5 rounded">{notation}</span>
        {label && <span className="text-purple-400 italic">{label}</span>}
      </div>

      {/* Dice groups */}
      {groups.map((group, gi) => (
        <div key={gi}>
          <div className="text-xs text-gray-500 mb-1">{group.dice}</div>
          <div className="flex flex-wrap gap-1.5">
            {group.rolls.map((roll, ri) => {
              const sides = parseInt(group.dice.split("d")[1]) || 20;
              const isMax = roll.value === sides;
              const isMin = roll.value === 1;

              return (
                <div
                  key={ri}
                  className={`
                    relative w-10 h-10 rounded-lg flex items-center justify-center
                    text-sm font-bold border transition-all
                    animate-dice-pop
                    ${!roll.kept
                      ? "opacity-30 line-through bg-gray-800 border-gray-700 text-gray-500"
                      : isMax
                        ? "bg-gradient-to-br from-yellow-600 to-amber-800 border-yellow-400 ring-2 ring-yellow-400/50 text-yellow-200 shadow-[0_0_10px_rgba(250,204,21,0.3)]"
                        : isMin
                          ? "bg-gradient-to-br from-red-800 to-red-950 border-red-500/50 text-red-300"
                          : "bg-gradient-to-br from-indigo-700 to-indigo-900 border-indigo-500/50 text-white"
                    }
                  `}
                  style={{ animationDelay: `${ri * 60}ms` }}
                  title={
                    roll.rerolled
                      ? `Rerolled from ${roll.original}`
                      : roll.exploded
                        ? "Exploded!"
                        : undefined
                  }
                >
                  {roll.value}
                  {roll.exploded && (
                    <span className="absolute -top-1 -right-1 text-[10px] text-yellow-400">&#9889;</span>
                  )}
                  {roll.rerolled && (
                    <span className="absolute -top-1 -left-1 text-[10px] text-blue-400">&#8635;</span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}

      {/* Total */}
      <div className="flex items-baseline gap-3 pt-1 border-t border-gray-700/50">
        {flat_modifier !== 0 && (
          <span className="text-indigo-400 text-sm">
            {flat_modifier >= 0 ? "+" : ""}{flat_modifier}
          </span>
        )}
        <span className="text-white text-xl font-bold">
          Total: {total}
        </span>
      </div>
    </div>
  );
}
