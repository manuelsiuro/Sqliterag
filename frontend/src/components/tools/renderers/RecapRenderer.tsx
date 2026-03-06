import { useState } from "react";
import type { ToolRendererProps } from "./toolRendererRegistry";

interface SessionRecapData {
  type: "session_recap";
  campaign_name?: string;
  session_number?: number;
  recap?: string;
  narrative?: boolean;
  previous_sessions?: Array<{ session_number: number; summary: string }>;
  error?: string;
}

export function RecapRenderer({ data }: ToolRendererProps) {
  const d = data as SessionRecapData;
  const [expanded, setExpanded] = useState(false);

  if (d.error) {
    return <div className="mt-2 text-red-400 text-sm">{d.error}</div>;
  }

  if (!d.recap) return null;

  return (
    <div className="bg-gray-800/30 rounded-lg px-3 py-2.5 border border-amber-700/30 space-y-2">
      {/* Header */}
      <div className="flex items-center gap-2">
        <span className="text-amber-400/80 text-sm">{"\uD83D\uDCDC"}</span>
        <span className="text-amber-300 text-sm font-bold italic">
          Previously on {d.campaign_name || "your campaign"}...
        </span>
        {d.session_number != null && (
          <span className="text-[10px] px-1.5 py-px rounded-full bg-amber-900/40 text-amber-300 border border-amber-700/30 ml-auto">
            Session #{d.session_number}
          </span>
        )}
      </div>

      {/* Narrative recap */}
      <div className="text-sm text-gray-300 italic leading-relaxed pl-1 border-l-2 border-amber-700/30 ml-1">
        {d.recap}
      </div>

      {/* Collapsible previous sessions */}
      {d.previous_sessions && d.previous_sessions.length > 0 && (
        <div>
          <button
            onClick={() => setExpanded(!expanded)}
            className="text-[10px] text-amber-400/60 hover:text-amber-300 transition-colors"
          >
            {expanded ? "\u25BC" : "\u25B6"} Session summaries ({d.previous_sessions.length})
          </button>
          {expanded && (
            <div className="mt-1 space-y-1 pl-2">
              {d.previous_sessions.map((s) => (
                <div key={s.session_number} className="text-xs text-gray-500">
                  <span className="text-amber-400/50 font-medium">#{s.session_number}</span>{" "}
                  {s.summary}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
