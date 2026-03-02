import { useState, type KeyboardEvent } from "react";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled: boolean;
  isStreaming?: boolean;
  onStop?: () => void;
}

export function ChatInput({ onSend, disabled, isStreaming, onStop }: ChatInputProps) {
  const [input, setInput] = useState("");

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setInput("");
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-gray-800 p-4">
      <div className="flex gap-2 items-end max-w-4xl mx-auto">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message... (Shift+Enter for new line)"
          disabled={disabled}
          rows={1}
          className="flex-1 bg-gray-800 text-white border border-gray-700 rounded-xl px-4 py-3 text-sm resize-none focus:outline-none focus:border-blue-500 disabled:opacity-50 placeholder:text-gray-500"
          style={{ minHeight: "44px", maxHeight: "200px" }}
          onInput={(e) => {
            const target = e.target as HTMLTextAreaElement;
            target.style.height = "auto";
            target.style.height = Math.min(target.scrollHeight, 200) + "px";
          }}
        />
        {isStreaming ? (
          <button
            onClick={onStop}
            className="px-4 py-3 bg-red-600 hover:bg-red-500 text-white rounded-xl text-sm transition-colors"
          >
            Stop
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={disabled || !input.trim()}
            className="px-4 py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-xl text-sm transition-colors"
          >
            Send
          </button>
        )}
      </div>
    </div>
  );
}
