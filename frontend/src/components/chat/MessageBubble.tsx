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

    const handleAction = (label: string) => {
      useChatStore.getState().setPendingInput(label);
    };

    return (
      <div
        className={`group relative flex ${isUser ? "justify-end" : "justify-start"} mb-4`}
      >
        <div
          className={`relative max-w-[80%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${
            isUser
              ? "bg-blue-600 text-white rounded-br-md"
              : "bg-gradient-to-br from-gray-900 to-gray-800/90 border border-gray-700/30 border-l-2 border-l-indigo-500/40 text-gray-100 rounded-bl-md"
          }`}
        >
          {/* Copy button — inside bubble */}
          <div className="absolute top-1.5 right-1.5 opacity-0 group-hover:opacity-100 transition-opacity z-10">
            <CopyButton text={message.content} size="sm" />
          </div>

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
        </div>
      </div>
    );
  },
  (prev, next) =>
    prev.message.id === next.message.id &&
    prev.message.content === next.message.content &&
    prev.isLatestAssistant === next.isLatestAssistant &&
    prev.isStreaming === next.isStreaming
);
