import { useEffect, useRef, useMemo } from "react";
import type { Message } from "@/types";
import { MessageBubble } from "./MessageBubble";

interface MessageListProps {
  messages: Message[];
  streamingContent: string;
  isStreaming: boolean;
}

export function MessageList({ messages, streamingContent, isStreaming }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent]);

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
