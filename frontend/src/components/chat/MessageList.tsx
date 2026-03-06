import { useEffect, useRef, useMemo } from "react";
import type { Message } from "@/types";
import { useChatStore } from "@/store/chatStore";
import { MessageBubble } from "./MessageBubble";

interface MessageListProps {
  messages: Message[];
  streamingContent: string;
  isStreaming: boolean;
}

export function MessageList({ messages, streamingContent, isStreaming }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const { isToolCalling } = useChatStore();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent, isToolCalling]);

  // Find the last assistant text message (not a tool-call message)
  const latestAssistantId = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const m = messages[i];
      if (m.role === "assistant" && !m.tool_calls?.length) return m.id;
    }
    return null;
  }, [messages]);

  if (messages.length === 0 && !isStreaming) {
    return (
      <div className="flex-1 flex items-center justify-center text-gray-500">
        <div className="text-center">
          <p className="text-lg mb-1">Start a conversation</p>
          <p className="text-sm">Send a message to begin chatting</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4">
      {messages.map((msg) => (
        <MessageBubble
          key={msg.id}
          message={msg}
          isLatestAssistant={msg.id === latestAssistantId}
          isStreaming={isStreaming}
        />
      ))}
      {/* Thinking indicator — shown while streaming but no content yet */}
      {isStreaming && !streamingContent && (
        <div className="flex justify-start mb-4">
          <div className="bg-gradient-to-br from-gray-900 to-gray-800 border-l-2 border-indigo-500/60 rounded-lg px-4 py-3 max-w-[80%]">
            {isToolCalling ? (
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-amber-400 animate-thinking-pulse" />
                <span className="text-sm text-amber-300/80">Executing tools...</span>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 py-0.5">
                <span className="w-2 h-2 rounded-full bg-indigo-400 animate-thinking-dot-1" />
                <span className="w-2 h-2 rounded-full bg-indigo-400 animate-thinking-dot-2" />
                <span className="w-2 h-2 rounded-full bg-indigo-400 animate-thinking-dot-3" />
              </div>
            )}
          </div>
        </div>
      )}
      {isStreaming && streamingContent && (
        <MessageBubble
          message={{
            id: "streaming",
            conversation_id: "",
            role: "assistant",
            content: streamingContent,
            created_at: new Date().toISOString(),
          }}
        />
      )}
      <div ref={bottomRef} />
    </div>
  );
}
