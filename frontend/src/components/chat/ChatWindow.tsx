import { useChatStore } from "@/store/chatStore";
import { MessageList } from "./MessageList";
import { ChatInput } from "./ChatInput";
import { LoadingSpinner } from "@/components/common";

export function ChatWindow() {
  const { messages, streamingContent, isStreaming, isLoading, activeConversationId, sendMessage, stopStreaming } =
    useChatStore();

  if (!activeConversationId) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-950 text-gray-500">
        <div className="text-center">
          <h2 className="text-2xl font-semibold mb-2">sqliteRAG</h2>
          <p className="text-sm">Select or create a conversation to get started</p>
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-950">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col min-h-0 bg-gray-950">
      <MessageList messages={messages} streamingContent={streamingContent} isStreaming={isStreaming} />
      <ChatInput onSend={sendMessage} disabled={isStreaming} isStreaming={isStreaming} onStop={stopStreaming} />
    </div>
  );
}
