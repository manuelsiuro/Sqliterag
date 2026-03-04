import { ModelSelector } from "./ModelSelector";
import { ModelDetailCard } from "./ModelDetailCard";
import { ModelParametersForm } from "./ModelParametersForm";
import { HuggingFaceSearch } from "./HuggingFaceSearch";
import { useChatStore } from "@/store/chatStore";
import { api } from "@/services/api";

export function SettingsPanel() {
  const { activeConversationId, conversations } = useChatStore();
  const activeConv = conversations.find((c) => c.id === activeConversationId);
  const currentModel = activeConv?.model || "qwen3.5:9b";

  const handleModelChange = async (model: string) => {
    if (activeConversationId) {
      await api.updateConversation(activeConversationId, { model });
      useChatStore.getState().loadConversations();
    }
  };

  return (
    <div className="space-y-6">
      <ModelSelector selectedModel={currentModel} onSelect={handleModelChange} />
      <ModelDetailCard />
      <ModelParametersForm />
      <hr className="border-gray-800" />
      <HuggingFaceSearch />
    </div>
  );
}
