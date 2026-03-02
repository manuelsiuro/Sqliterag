import { useEffect } from "react";
import { useChatStore } from "@/store/chatStore";
import { useSettingsStore } from "@/store/settingsStore";
import { ConversationList } from "./ConversationList";

interface SidebarProps {
  onToggleSettings: () => void;
  onToggleDatabase: () => void;
  onToggleTools: () => void;
}

export function Sidebar({ onToggleSettings, onToggleDatabase, onToggleTools }: SidebarProps) {
  const {
    conversations,
    activeConversationId,
    loadConversations,
    createConversation,
    selectConversation,
    deleteConversation,
  } = useChatStore();
  const { localModels } = useSettingsStore();

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const defaultModel = localModels[0]?.name;

  return (
    <aside className="w-64 bg-gray-900 border-r border-gray-800 flex flex-col h-full">
      <div className="p-3 border-b border-gray-800">
        <button
          onClick={() => createConversation(defaultModel)}
          className="w-full px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition-colors"
        >
          + New Chat
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2">
        <ConversationList
          conversations={conversations}
          activeId={activeConversationId}
          onSelect={selectConversation}
          onDelete={deleteConversation}
        />
      </div>

      <div className="p-3 border-t border-gray-800 space-y-2">
        <button
          onClick={onToggleTools}
          className="w-full px-3 py-2 text-gray-400 hover:text-white text-sm rounded-lg hover:bg-gray-800 transition-colors"
        >
          Tools
        </button>
        <button
          onClick={onToggleDatabase}
          className="w-full px-3 py-2 text-gray-400 hover:text-white text-sm rounded-lg hover:bg-gray-800 transition-colors"
        >
          Database
        </button>
        <button
          onClick={onToggleSettings}
          className="w-full px-3 py-2 text-gray-400 hover:text-white text-sm rounded-lg hover:bg-gray-800 transition-colors"
        >
          Settings
        </button>
      </div>
    </aside>
  );
}
