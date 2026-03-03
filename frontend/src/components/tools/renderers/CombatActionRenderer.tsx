import type { ToolRendererProps } from "./toolRendererRegistry";

interface CombatActionData {
  character: string;
  action: string;
  description: string;
  stealth_roll?: number;
  stealth_total?: number;
  stealth_modifier?: number;
  error?: string;
}

const ACTION_ICONS: Record<string, string> = {
  dodge: "\uD83D\uDEE1\uFE0F",
  dash: "\uD83C\uDFC3",
  disengage: "\uD83D\uDEB6",
  help: "\uD83E\uDD1D",
  hide: "\uD83D\uDC7B",
};

export function CombatActionRenderer({ data }: ToolRendererProps) {
  const d = data as unknown as CombatActionData;

  if (d.error) {
    return <div className="mt-2 text-red-400 text-sm">{d.error}</div>;
  }

  return (
    <div className="mt-2 space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-lg">{ACTION_ICONS[d.action] || "\u2694\uFE0F"}</span>
        <div>
          <span className="text-sm font-medium text-amber-200">{d.character}</span>
          <span className="text-gray-400 text-sm"> uses </span>
          <span className="text-sm font-bold text-amber-300 capitalize">{d.action}</span>
        </div>
      </div>

      <div className="text-xs text-gray-400 bg-gray-800/40 rounded px-2 py-1.5 border border-gray-700/30 italic">
        {d.description}
      </div>

      {d.stealth_roll !== undefined && (
        <div className="flex items-center gap-2 text-xs">
          <span className="text-gray-500">Stealth:</span>
          <span className="w-7 h-7 rounded flex items-center justify-center text-xs font-bold bg-purple-800/50 text-purple-200 border border-purple-700/40">
            {d.stealth_roll}
          </span>
          <span className="text-gray-500">{d.stealth_modifier! >= 0 ? "+" : ""}{d.stealth_modifier}</span>
          <span className="text-gray-300 font-medium">= {d.stealth_total}</span>
        </div>
      )}
    </div>
  );
}
