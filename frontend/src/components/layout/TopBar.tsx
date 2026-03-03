import { useEffect } from "react";
import { useChatStore } from "@/store/chatStore";
import { useSettingsStore } from "@/store/settingsStore";
import { useUIStore } from "@/store/uiStore";
import { SessionDropdown } from "./SessionDropdown";

export function TopBar() {
  const {
    conversations,
    activeConversationId,
    loadConversations,
    createConversation,
  } = useChatStore();
  const { localModels } = useSettingsStore();
  const { sessionDropdownOpen, setSessionDropdownOpen } = useUIStore();

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const activeConv = conversations.find((c) => c.id === activeConversationId);
  const defaultModel = localModels[0]?.name;

  return (
    <header className="h-12 bg-gray-900 border-b border-gray-800 shrink-0 flex items-center px-4 gap-4 z-30">
      {/* App name */}
      <span className="text-sm font-bold text-gray-300 tracking-wide select-none">
        sqliteRAG
      </span>

      {/* Session selector */}
      <div className="relative">
        <button
          onClick={() => setSessionDropdownOpen(!sessionDropdownOpen)}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 border border-gray-700 text-sm text-gray-200 transition-colors max-w-xs"
        >
          <span className="truncate">
            {activeConv ? activeConv.title : "No session selected"}
          </span>
          {/* Chevron */}
          <svg
            className={`w-3.5 h-3.5 text-gray-400 shrink-0 transition-transform ${sessionDropdownOpen ? "rotate-180" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {sessionDropdownOpen && <SessionDropdown />}
      </div>

      {/* New session button */}
      <button
        onClick={() => createConversation(defaultModel)}
        className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition-colors"
      >
        + New
      </button>
    </header>
  );
}
