import { memo, useMemo } from "react";
import type { Message } from "@/types";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { CopyButton } from "@/components/common";
import { ToolCallBubble, ToolResultBubble } from "@/components/tools";
import { parseActionSuggestions } from "./parseActionSuggestions";
import { ActionSuggestionCards } from "./ActionSuggestionCards";
import { useChatStore } from "@/store/chatStore";

interface MessageBubbleProps {
  message: Message;
  isLatestAssistant?: boolean;
  isStreaming?: boolean;
}

function formatMetrics(metrics: Record<string, number>) {
  const parts: string[] = [];

  // Response time (total_duration is in nanoseconds)
  if (metrics.total_duration) {
    const ms = metrics.total_duration / 1e6;
    if (ms >= 1000) {
      parts.push(`${(ms / 1000).toFixed(1)}s`);
    } else {
      parts.push(`${Math.round(ms)}ms`);
    }
  }

  // Token count
  if (metrics.eval_count) {
    parts.push(`${metrics.eval_count} tokens`);
  }

  // Generation speed (tokens per second)
  if (metrics.eval_count && metrics.eval_duration) {
    const tokensPerSec = metrics.eval_count / (metrics.eval_duration / 1e9);
    parts.push(`${tokensPerSec.toFixed(1)} T/s`);
  }

  return parts;
}

export const MessageBubble = memo(
  function MessageBubble({ message, isLatestAssistant = false, isStreaming = false }: MessageBubbleProps) {
    // Tool call messages (assistant with tool_calls)
    if (message.role === "assistant" && message.tool_calls?.length) {
      return <ToolCallBubble message={message} />;
    }

    // Tool result messages
    if (message.role === "tool") {
      return <ToolResultBubble message={message} />;
    }

    const isUser = message.role === "user";
    const isStreamingMsg = message.id === "streaming";
    const isAssistant = message.role === "assistant";

    const parsed = useMemo(() => {
      if (isUser || isStreamingMsg || !message.content) return null;
      // Prefer structured actions from SSE over regex parsing
      if (message.actions?.length) {
        // Strip the action block from content for narrative display
        const fallback = parseActionSuggestions(message.content);
        return {
          narrative: fallback?.narrative ?? message.content,
          actions: message.actions,
        };
      }
      return parseActionSuggestions(message.content);
    }, [isUser, isStreamingMsg, message.content, message.actions]);

    const metricsParts = useMemo(() => {
      if (!isAssistant || !message.metrics) return null;
      return formatMetrics(message.metrics);
    }, [isAssistant, message.metrics]);

    const handleAction = (label: string) => {
      useChatStore.getState().setPendingInput(label);
    };

    return (
      <div
        className={`group relative flex ${isUser ? "justify-end" : "justify-start"} mb-4`}
      >
        <div
          className={`relative max-w-[80%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${isUser
            ? "bg-blue-600 text-white rounded-br-md"
            : "bg-gradient-to-br from-gray-900 to-gray-800/90 border border-gray-700/30 border-l-2 border-l-indigo-500/40 text-gray-100 rounded-bl-md"
            }`}
        >
          {/* Copy button — inside bubble */}
          <div className="absolute top-1.5 right-1.5 opacity-0 group-hover:opacity-100 transition-opacity z-10">
            <CopyButton text={message.content} size="sm" />
          </div>

          {message.images && message.images.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {message.images.map((img, i) => (
                <img
                  key={i}
                  src={`/api/${img}`}
                  alt="Attachment"
                  className="max-w-full sm:max-w-xs max-h-64 object-contain rounded-lg border border-gray-700/50 bg-black/20"
                />
              ))}
            </div>
          )}

          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : parsed ? (
            <>
              <MarkdownRenderer content={parsed.narrative} />
              <ActionSuggestionCards
                actions={parsed.actions}
                onAction={handleAction}
                disabled={isStreaming}
                isLatest={isLatestAssistant}
              />
            </>
          ) : (
            <MarkdownRenderer content={message.content} />
          )}

          {/* Metrics footer — discreet and polished */}
          {metricsParts && metricsParts.length > 0 && (
            <div className="mt-2 pt-1.5 border-t border-gray-700/20 flex items-center gap-2 text-[10px] text-gray-500 font-mono opacity-60 group-hover:opacity-100 transition-opacity">
              {metricsParts.map((part, i) => (
                <span key={i} className="flex items-center gap-1">
                  {i > 0 && <span className="text-gray-600">·</span>}
                  {part}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  },
  (prev, next) =>
    prev.message.id === next.message.id &&
    prev.message.content === next.message.content &&
    prev.message.metrics === next.message.metrics &&
    prev.isLatestAssistant === next.isLatestAssistant &&
    prev.isStreaming === next.isStreaming
);
