import type { ToolRendererProps } from "./toolRendererRegistry";

interface NPCData {
  name: string;
  description: string;
  disposition: string;
  familiarity: string;
  location?: string;
  topic?: string;
  memory: string[];
  memory_added?: string;
  total_memories?: number;
  roleplay_hint?: string;
  changes?: string[];
  error?: string;
}

const DISPOSITION_SCALE = ["hostile", "unfriendly", "neutral", "friendly", "helpful"];
const DISPOSITION_COLORS: Record<string, string> = {
  hostile: "bg-red-500",
  unfriendly: "bg-orange-500",
  neutral: "bg-gray-400",
  friendly: "bg-emerald-500",
  helpful: "bg-blue-500",
};

const FAMILIARITY_ICONS: Record<string, string> = {
  stranger: "\uD83D\uDC64",
  acquaintance: "\uD83D\uDC4B",
  friend: "\uD83E\uDD1D",
  close_friend: "\u2764\uFE0F",
};

export function NPCRenderer({ data }: ToolRendererProps) {
  const d = data as unknown as NPCData;

  if (d.error) {
    return <div className="mt-2 text-red-400 text-sm">{d.error}</div>;
  }

  const dispIndex = DISPOSITION_SCALE.indexOf(d.disposition);
  const dispPct = ((dispIndex + 1) / DISPOSITION_SCALE.length) * 100;

  return (
    <div className="mt-2 space-y-2">
      {/* Header */}
      <div className="flex items-center gap-2">
        <span className="text-lg">{FAMILIARITY_ICONS[d.familiarity] || "\uD83D\uDC64"}</span>
        <div>
          <div className="text-sm font-bold text-purple-200">{d.name}</div>
          <div className="text-[10px] text-gray-500 capitalize">
            {d.familiarity.replace("_", " ")}
            {d.location && <> &middot; {d.location}</>}
          </div>
        </div>
      </div>

      {d.description && (
        <div className="text-xs text-gray-400 italic">{d.description}</div>
      )}

      {/* Disposition meter */}
      <div>
        <div className="flex justify-between text-[10px] text-gray-500 mb-0.5">
          <span>Hostile</span>
          <span className="capitalize font-medium text-gray-300">{d.disposition}</span>
          <span>Helpful</span>
        </div>
        <div className="w-full h-2.5 bg-gray-800 rounded-full overflow-hidden border border-gray-700 relative">
          <div
            className="absolute inset-0 bg-gradient-to-r from-red-500 via-gray-400 to-blue-500 opacity-20"
          />
          <div
            className={`h-full rounded-full transition-all ${DISPOSITION_COLORS[d.disposition] || "bg-gray-400"}`}
            style={{ width: `${dispPct}%` }}
          />
        </div>
      </div>

      {/* Topic */}
      {d.topic && (
        <div className="text-xs text-gray-400">
          Topic: <span className="text-gray-300">{d.topic}</span>
        </div>
      )}

      {/* Memory */}
      {d.memory && d.memory.length > 0 && (
        <div className="space-y-0.5">
          <div className="text-[10px] text-gray-500">Memories ({d.memory.length}):</div>
          {d.memory.slice(-3).map((m, i) => (
            <div key={i} className="text-xs text-gray-400 pl-2 border-l border-gray-700 animate-item-appear" style={{ animationDelay: `${i * 40}ms` }}>
              {m}
            </div>
          ))}
        </div>
      )}

      {d.memory_added && (
        <div className="text-xs text-green-400">Remembered: &ldquo;{d.memory_added}&rdquo;</div>
      )}

      {/* Changes */}
      {d.changes && d.changes.length > 0 && (
        <div className="text-xs text-gray-400 border-t border-gray-700/50 pt-1">
          {d.changes.map((c, i) => (
            <div key={i}>&bull; {c}</div>
          ))}
        </div>
      )}
    </div>
  );
}
