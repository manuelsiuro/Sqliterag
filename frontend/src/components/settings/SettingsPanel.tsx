import { ModelSelector } from "./ModelSelector";
import { HuggingFaceSearch } from "./HuggingFaceSearch";
import { useChatStore } from "@/store/chatStore";
import { api } from "@/services/api";

interface SettingsPanelProps {
  onClose: () => void;
}

export function SettingsPanel({ onClose }: SettingsPanelProps) {
  const { activeConversationId, conversations } = useChatStore();
  const activeConv = conversations.find((c) => c.id === activeConversationId);
  const currentModel = activeConv?.model || "llama3.2";

  const handleModelChange = async (model: string) => {
    if (activeConversationId) {
      await api.updateConversation(activeConversationId, { model });
      useChatStore.getState().loadConversations();
    }
  };

  return (
    <div className="w-80 bg-gray-900 border-l border-gray-800 flex flex-col h-full">
      <div className="flex items-center justify-between p-4 border-b border-gray-800">
        <h2 className="text-lg font-semibold text-white">Settings</h2>
        <button onClick={onClose} className="text-gray-400 hover:text-white text-xl">&times;</button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        <ModelSelector selectedModel={currentModel} onSelect={handleModelChange} />
        <hr className="border-gray-800" />
        <HuggingFaceSearch />
      </div>
    </div>
  );
}
