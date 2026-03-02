import { useDatabaseStore } from "@/store/databaseStore";
import { useChatStore } from "@/store/chatStore";

export function DatabaseActions() {
  const { actionStatus, vacuum, clearConversations, clearDocuments, exportDatabase, loadInfo } =
    useDatabaseStore();
  const { loadConversations } = useChatStore();

  const handleVacuum = async () => {
    await vacuum();
    await loadInfo();
  };

  const handleClearConversations = async () => {
    if (!window.confirm("Delete ALL conversations and messages? This cannot be undone.")) return;
    await clearConversations();
    await loadInfo();
    await loadConversations();
  };

  const handleClearDocuments = async () => {
    if (!window.confirm("Delete ALL documents and vector data? This cannot be undone.")) return;
    await clearDocuments();
    await loadInfo();
  };

  return (
    <div className="space-y-3">
      <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
        Actions
      </h3>

      <button
        onClick={handleVacuum}
        className="w-full px-3 py-2 bg-gray-800 hover:bg-gray-700 text-gray-200 text-sm rounded-lg transition-colors text-left"
      >
        Vacuum Database
        <span className="block text-xs text-gray-500">Reclaim unused disk space</span>
      </button>

      <button
        onClick={handleClearConversations}
        className="w-full px-3 py-2 bg-gray-800 hover:bg-gray-700 text-red-400 text-sm rounded-lg transition-colors text-left"
      >
        Clear Conversations
        <span className="block text-xs text-gray-500">Delete all chats and messages</span>
      </button>

      <button
        onClick={handleClearDocuments}
        className="w-full px-3 py-2 bg-gray-800 hover:bg-gray-700 text-red-400 text-sm rounded-lg transition-colors text-left"
      >
        Clear Documents
        <span className="block text-xs text-gray-500">Delete all documents and vectors</span>
      </button>

      <button
        onClick={exportDatabase}
        className="w-full px-3 py-2 bg-gray-800 hover:bg-gray-700 text-gray-200 text-sm rounded-lg transition-colors text-left"
      >
        Export Database
        <span className="block text-xs text-gray-500">Download .db file</span>
      </button>

      {actionStatus && (
        <p className="text-xs text-gray-400 pt-1">{actionStatus}</p>
      )}
    </div>
  );
}
