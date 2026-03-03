import { useState } from "react";
import type { Message } from "@/types";
import { TOOL_ICONS, DEFAULT_TOOL_ICON } from "./toolIcons";

interface ToolCallBubbleProps {
  message: Message;
}

export function ToolCallBubble({ message }: ToolCallBubbleProps) {
  const [expandedSet, setExpandedSet] = useState<Set<number>>(new Set());
  const toolCalls = message.tool_calls ?? [];

  const toggle = (i: number) => {
    setExpandedSet((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  };

  return (
    <div className="flex justify-start mb-4">
      <div className="max-w-[80%] px-4 py-3 rounded-2xl rounded-bl-md bg-amber-950/50 border border-amber-800/40 text-amber-100 text-sm">
        {toolCalls.map((tc, i) => {
          const funcName = tc.function?.name ?? "unknown";
          const args = tc.function?.arguments ?? {};
          const icon = TOOL_ICONS[funcName] || DEFAULT_TOOL_ICON;
          const isExpanded = expandedSet.has(i);
          return (
            <div key={i}>
              {i > 0 && <div className="border-t border-amber-800/30 my-2" />}
              <div className="flex items-center gap-2">
                <span className="text-base">{icon}</span>
                <span className="text-[10px] uppercase tracking-wider text-amber-400/70 font-medium">Action</span>
              </div>
              <div className="mt-0.5">
                <span className="font-medium text-amber-200 font-mono text-xs">{funcName}</span>
              </div>
              <button
                onClick={() => toggle(i)}
                className="mt-1.5 flex items-center gap-1 text-xs text-amber-400 hover:text-amber-300 transition-colors"
              >
                <span className={`inline-block transition-transform duration-200 text-[10px] ${isExpanded ? "rotate-90" : ""}`}>
                  {"\u25B6"}
                </span>
                <span>{isExpanded ? "Hide arguments" : "Show arguments"}</span>
              </button>
              {isExpanded && (
                <pre className="mt-2 p-2 bg-gray-950/60 rounded-lg border border-gray-700/30 text-xs text-gray-300 overflow-x-auto">
                  {JSON.stringify(args, null, 2)}
                </pre>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
