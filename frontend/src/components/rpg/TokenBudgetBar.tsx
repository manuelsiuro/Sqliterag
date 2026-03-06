import type { TokenBudgetSnapshot } from "@/types";

const SEGMENTS = [
  { key: "system_prompt_tokens", label: "System Prompt", color: "bg-purple-500" },
  { key: "rag_context_tokens", label: "RAG / Memories", color: "bg-green-500" },
  { key: "tool_definitions_tokens", label: "Tool Definitions", color: "bg-blue-500" },
  { key: "conversation_history_tokens", label: "History", color: "bg-amber-500" },
] as const;

const DOT_COLORS: Record<string, string> = {
  system_prompt_tokens: "bg-purple-500",
  rag_context_tokens: "bg-green-500",
  tool_definitions_tokens: "bg-blue-500",
  conversation_history_tokens: "bg-amber-500",
};

function fmt(n: number): string {
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
}

export function TokenBudgetBar({ budget }: { budget: TokenBudgetSnapshot }) {
  const total = budget.input_budget || 1;
  const isHigh = budget.utilization_pct > 90;

  return (
    <div className="space-y-2">
      {/* Stacked bar */}
      <div className={`h-3 rounded-full overflow-hidden flex ${isHigh ? "ring-1 ring-red-500/50" : ""}`}
        style={{ backgroundColor: "rgba(55,65,81,0.5)" }}
      >
        {SEGMENTS.map(({ key, color }) => {
          const val = budget[key];
          if (val <= 0) return null;
          const pct = (val / total) * 100;
          return (
            <div
              key={key}
              className={`${color} ${isHigh ? "opacity-80" : ""} transition-all`}
              style={{ width: `${Math.min(pct, 100)}%` }}
              title={`${key}: ${fmt(val)}`}
            />
          );
        })}
      </div>

      {/* Summary line */}
      <div className="flex items-center justify-between text-[11px]">
        <span className={isHigh ? "text-red-400 font-medium" : "text-gray-400"}>
          {fmt(budget.total_input_tokens)} / {fmt(budget.input_budget)} tokens
          ({budget.utilization_pct}%)
        </span>
        <span className="text-gray-600">
          {fmt(budget.tokens_remaining)} remaining
        </span>
      </div>

      {/* Breakdown rows */}
      <div className="space-y-0.5">
        {SEGMENTS.map(({ key, label }) => {
          const val = budget[key];
          return (
            <div key={key} className="flex items-center gap-2 text-[10px]">
              <span className={`w-1.5 h-1.5 rounded-full ${DOT_COLORS[key]}`} />
              <span className="text-gray-500 flex-1">{label}</span>
              <span className="text-gray-400 tabular-nums">{fmt(val)}</span>
            </div>
          );
        })}
      </div>

      {/* Extra stats */}
      {(budget.summarized_message_count > 0 || budget.truncated_message_count > 0) && (
        <div className="flex gap-3 pt-1 border-t border-gray-800/50 text-[10px] text-gray-600">
          {budget.summarized_message_count > 0 && (
            <span>Summarized: {budget.summarized_message_count} msgs</span>
          )}
          {budget.truncated_message_count > 0 && (
            <span>Truncated: {budget.truncated_message_count} msgs</span>
          )}
        </div>
      )}
    </div>
  );
}
