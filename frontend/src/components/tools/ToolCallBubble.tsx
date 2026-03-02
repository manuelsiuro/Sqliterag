import { useState } from "react";
import type { Message } from "@/types";

interface ToolCallBubbleProps {
  message: Message;
}

export function ToolCallBubble({ message }: ToolCallBubbleProps) {
  const [expanded, setExpanded] = useState(false);
  const toolCalls = message.tool_calls ?? [];

  return (
    <div className="flex justify-start mb-4">
      <div className="max-w-[80%] px-4 py-3 rounded-2xl rounded-bl-md bg-amber-900/40 border border-amber-700/50 text-amber-100 text-sm">
        {toolCalls.map((tc, i) => {
          const funcName = tc.function?.name ?? "unknown";
          const args = tc.function?.arguments ?? {};
          return (
            <div key={i}>
              <div className="flex items-center gap-2">
                <span className="text-base">&#128295;</span>
                <span className="font-medium">
                  Calling <code className="bg-amber-800/50 px-1.5 py-0.5 rounded text-amber-200">{funcName}</code>
                </span>
              </div>
              <button
                onClick={() => setExpanded(!expanded)}
                className="mt-1 text-xs text-amber-400 hover:text-amber-300 underline"
              >
                {expanded ? "Hide arguments" : "Show arguments"}
              </button>
              {expanded && (
                <pre className="mt-2 p-2 bg-gray-900/60 rounded text-xs text-gray-300 overflow-x-auto">
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
