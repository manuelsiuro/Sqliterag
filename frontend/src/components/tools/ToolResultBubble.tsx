import { useState } from "react";
import type { Message } from "@/types";
import { tryParseToolResult, getToolRenderer } from "./renderers";
import { TOOL_ICONS, DEFAULT_TOOL_ICON } from "./toolIcons";

interface ToolResultBubbleProps {
  message: Message;
}

export function ToolResultBubble({ message }: ToolResultBubbleProps) {
  const [expanded, setExpanded] = useState(false);
  const isLong = message.content.length > 200;

  const parsed = tryParseToolResult(message.content);
  const Renderer = parsed ? getToolRenderer(parsed.type) : null;

  const toolName = message.tool_name ?? "Tool";
  const icon = TOOL_ICONS[toolName] || DEFAULT_TOOL_ICON;

  return (
    <div className="flex justify-start mb-4">
      <div className="max-w-[80%] px-4 py-3 rounded-2xl rounded-bl-md bg-gray-900/60 border border-gray-700/40 text-gray-100 text-sm">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-base">{icon}</span>
          <span className="text-[10px] uppercase tracking-wider text-gray-400 font-medium">{toolName}</span>
          <span className="text-[10px] text-gray-600">result</span>
        </div>

        {Renderer ? (
          <Renderer data={parsed!} rawContent={message.content} />
        ) : (
          <div className="mt-1">
            <div className="text-[11px] text-gray-500 italic mb-1.5">
              Raw output from <span className="font-mono">{toolName}</span>
            </div>
            {isLong && !expanded ? (
              <>
                <pre className="p-2 bg-gray-950/60 rounded-lg border border-gray-700/30 text-xs text-gray-300 overflow-x-auto whitespace-pre-wrap">
                  {message.content.slice(0, 200)}...
                </pre>
                <button
                  onClick={() => setExpanded(true)}
                  className="mt-1 text-xs text-gray-400 hover:text-gray-300 underline"
                >
                  Show full result
                </button>
              </>
            ) : (
              <>
                <pre className="p-2 bg-gray-950/60 rounded-lg border border-gray-700/30 text-xs text-gray-300 overflow-x-auto whitespace-pre-wrap">
                  {message.content}
                </pre>
                {isLong && (
                  <button
                    onClick={() => setExpanded(false)}
                    className="mt-1 text-xs text-gray-400 hover:text-gray-300 underline"
                  >
                    Collapse
                  </button>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
