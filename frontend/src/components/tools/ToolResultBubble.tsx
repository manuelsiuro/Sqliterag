import { useState } from "react";
import type { Message } from "@/types";

interface ToolResultBubbleProps {
  message: Message;
}

export function ToolResultBubble({ message }: ToolResultBubbleProps) {
  const [expanded, setExpanded] = useState(false);
  const isLong = message.content.length > 200;

  return (
    <div className="flex justify-start mb-4">
      <div className="max-w-[80%] px-4 py-3 rounded-2xl rounded-bl-md bg-green-900/30 border border-green-700/40 text-green-100 text-sm">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-base">&#9989;</span>
          <span className="font-medium text-green-300">
            {message.tool_name ?? "Tool"} result
          </span>
        </div>
        <div className="mt-1">
          {isLong && !expanded ? (
            <>
              <pre className="p-2 bg-gray-900/60 rounded text-xs text-gray-300 overflow-x-auto whitespace-pre-wrap">
                {message.content.slice(0, 200)}...
              </pre>
              <button
                onClick={() => setExpanded(true)}
                className="mt-1 text-xs text-green-400 hover:text-green-300 underline"
              >
                Show full result
              </button>
            </>
          ) : (
            <>
              <pre className="p-2 bg-gray-900/60 rounded text-xs text-gray-300 overflow-x-auto whitespace-pre-wrap">
                {message.content}
              </pre>
              {isLong && (
                <button
                  onClick={() => setExpanded(false)}
                  className="mt-1 text-xs text-green-400 hover:text-green-300 underline"
                >
                  Collapse
                </button>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
