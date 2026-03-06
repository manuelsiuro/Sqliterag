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
  is_party_member?: boolean;
  error?: string;
  // Phase 5.3
  personality?: {
    traits?: string[];
    voice?: string;
    motivation?: string;
    secrets?: string[];
  };
  backstory?: string;
  relationships?: string[];
}

const DISPOSITION_SCALE = ["hostile", "unfriendly", "neutral", "friendly", "helpful"];
const DISPOSITION_COLORS: Record<string, string> = {
  hostile: "from-red-600 to-red-500",
  unfriendly: "from-orange-600 to-orange-500",
  neutral: "from-gray-500 to-gray-400",
  friendly: "from-emerald-600 to-emerald-500",
  helpful: "from-blue-500 to-blue-400",
};
const DISPOSITION_LABEL_COLORS: Record<string, string> = {
  hostile: "text-red-400",
  unfriendly: "text-orange-400",
  neutral: "text-gray-400",
  friendly: "text-emerald-400",
  helpful: "text-blue-400",
};

const FAMILIARITY_ICONS: Record<string, string> = {
  stranger: "\uD83D\uDC64",
  acquaintance: "\uD83D\uDC4B",
  friend: "\uD83E\uDD1D",
  close_friend: "\u2764\uFE0F",
};

const FAMILIARITY_BADGE: Record<string, string> = {
  stranger: "bg-gray-800/60 text-gray-400 border-gray-700/40",
  acquaintance: "bg-slate-800/50 text-slate-300 border-slate-600/30",
  friend: "bg-emerald-900/30 text-emerald-300 border-emerald-700/30",
  close_friend: "bg-rose-900/30 text-rose-300 border-rose-700/30",
};

import { capitalize } from "@/constants/rpg";

export function NPCRenderer({ data }: ToolRendererProps) {
  const d = data as unknown as NPCData;

  if (d.error) {
    return <div className="mt-2 text-red-400 text-sm">{d.error}</div>;
  }

  const dispIndex = DISPOSITION_SCALE.indexOf(d.disposition);
  const dispPct = ((dispIndex + 1) / DISPOSITION_SCALE.length) * 100;
  const familiarityLabel = d.familiarity?.replace("_", " ") || "stranger";

  return (
    <div className="mt-2 bg-gray-800/30 rounded-lg px-3 py-2.5 border border-gray-700/30 space-y-2">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xl">{FAMILIARITY_ICONS[d.familiarity] || "\uD83D\uDC64"}</span>
          <div>
            <div className="text-sm font-bold text-purple-200">{d.name}</div>
            {d.location && (
              <div className="text-[10px] text-gray-500">{d.location}</div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          {d.is_party_member && (
            <span className="text-[11px] px-2 py-0.5 rounded-full bg-blue-900/30 text-blue-300 border border-blue-700/30">
              Party Member
            </span>
          )}
          <span className={`text-[11px] px-2 py-0.5 rounded-full border ${FAMILIARITY_BADGE[d.familiarity] || FAMILIARITY_BADGE.stranger}`}>
            {FAMILIARITY_ICONS[d.familiarity] || "\uD83D\uDC64"} {capitalize(familiarityLabel)}
          </span>
        </div>
      </div>

      {/* Description */}
      {d.description && (
        <div className="text-xs text-gray-400 bg-gray-800/40 rounded px-2 py-1.5 border border-gray-700/30 italic">
          {d.description}
        </div>
      )}

      {/* Personality Traits */}
      {d.personality?.traits && d.personality.traits.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {d.personality.traits.slice(0, 5).map((trait, i) => (
            <span key={i} className="text-[10px] px-1.5 py-0.5 rounded-full bg-purple-900/25 text-purple-300 border border-purple-700/25">
              {trait}
            </span>
          ))}
          {d.personality.voice && (
            <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-indigo-900/25 text-indigo-300 border border-indigo-700/25">
              {d.personality.voice}
            </span>
          )}
        </div>
      )}

      {/* Backstory */}
      {d.backstory && (
        <div className="text-[10px] text-gray-500 bg-gray-800/30 rounded px-2 py-1 border border-gray-700/20">
          {d.backstory.length > 120 ? d.backstory.slice(0, 117) + "..." : d.backstory}
        </div>
      )}

      {/* Disposition meter */}
      <div>
        <div className="flex justify-between text-[10px] text-gray-500 mb-0.5">
          <span>Hostile</span>
          <span className={`capitalize font-medium ${DISPOSITION_LABEL_COLORS[d.disposition] || "text-gray-300"}`}>
            {d.disposition}
          </span>
          <span>Helpful</span>
        </div>
        <div className="w-full h-2.5 bg-gray-800 rounded-full overflow-hidden border border-gray-700 relative">
          <div className="absolute inset-0 bg-gradient-to-r from-red-500/15 via-gray-400/10 to-blue-500/15" />
          <div
            className={`h-full rounded-full transition-all duration-500 bg-gradient-to-r ${DISPOSITION_COLORS[d.disposition] || "from-gray-500 to-gray-400"}`}
            style={{ width: `${dispPct}%` }}
          />
        </div>
      </div>

      {/* Topic */}
      {d.topic && (
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-gray-500">Topic:</span>
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-amber-900/30 text-amber-300 border border-amber-700/30">
            {d.topic}
          </span>
        </div>
      )}

      {/* Relationships */}
      {d.relationships && d.relationships.length > 0 && (
        <div className="space-y-0.5">
          <div className="text-[10px] text-gray-500 font-medium">Relationships</div>
          {d.relationships.slice(0, 4).map((r, i) => (
            <div key={i} className="text-[11px] text-cyan-300/70 pl-2 border-l-2 border-cyan-700/30">
              {r}
            </div>
          ))}
        </div>
      )}

      {/* Memory */}
      {d.memory && d.memory.length > 0 && (
        <div className="space-y-1">
          <div className="text-[10px] text-gray-500 font-medium">Memories ({d.memory.length})</div>
          {d.memory.slice(-3).map((m, i) => (
            <div
              key={i}
              className="text-xs text-gray-400 pl-2 border-l-2 border-purple-700/40 bg-purple-900/10 rounded-r px-2 py-0.5 animate-item-appear"
              style={{ animationDelay: `${i * 40}ms` }}
            >
              {m}
            </div>
          ))}
        </div>
      )}

      {d.memory_added && (
        <div className="text-xs text-green-400 bg-green-900/15 rounded px-2 py-1 border border-green-700/20">
          Remembered: &ldquo;{d.memory_added}&rdquo;
        </div>
      )}

      {/* Changes */}
      {d.changes && d.changes.length > 0 && (
        <div className="space-y-0.5 border-t border-gray-700/30 pt-1.5">
          {d.changes.map((c, i) => (
            <div key={i} className="text-xs text-amber-300/80 flex items-center gap-1.5 animate-item-appear" style={{ animationDelay: `${i * 40}ms` }}>
              <span className="text-amber-500">&#x25B8;</span> {c}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
