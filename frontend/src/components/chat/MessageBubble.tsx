import { memo } from "react";
import type { Message } from "@/types";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { CopyButton } from "@/components/common";

interface MessageBubbleProps {
  message: Message;
}

export const MessageBubble = memo(
  function MessageBubble({ message }: MessageBubbleProps) {
    const isUser = message.role === "user";

    return (
      <div
        className={`group relative flex ${isUser ? "justify-end" : "justify-start"} mb-4`}
      >
        {/* Copy button for assistant messages — appears on left */}
        {!isUser && (
          <div className="absolute -right-10 top-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <CopyButton text={message.content} size="sm" />
          </div>
        )}

        <div
          className={`max-w-[80%] px-4 py-3 rounded-2xl text-sm leading-relaxed ${
            isUser
              ? "bg-blue-600 text-white rounded-br-md"
              : "bg-gray-800 text-gray-100 rounded-bl-md"
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <MarkdownRenderer content={message.content} />
          )}
        </div>

        {/* Copy button for user messages — appears on right */}
        {isUser && (
          <div className="absolute -left-10 top-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <CopyButton text={message.content} size="sm" />
          </div>
        )}
      </div>
    );
  },
  (prev, next) =>
    prev.message.id === next.message.id &&
    prev.message.content === next.message.content
);
