import { useState } from "react";
import { ErrorBoundary, Toast } from "@/components/common";
import { Sidebar } from "@/components/sidebar";
import { ChatWindow } from "@/components/chat";
import { SettingsPanel } from "@/components/settings";
import { DocumentList } from "@/components/documents";
import { useChatStore } from "@/store/chatStore";
import { useSettingsStore } from "@/store/settingsStore";
import { useEffect } from "react";

function App() {
  const [showSettings, setShowSettings] = useState(false);
  const { error, clearError } = useChatStore();
  const { loadLocalModels } = useSettingsStore();

  useEffect(() => {
    loadLocalModels();
  }, [loadLocalModels]);

  return (
    <ErrorBoundary>
      <div className="flex h-screen bg-gray-950 text-white">
        <Sidebar onToggleSettings={() => setShowSettings((s) => !s)} />

        <main className="flex-1 flex flex-col min-w-0">
          <ChatWindow />
        </main>

        {showSettings && (
          <div className="flex flex-col border-l border-gray-800">
            <SettingsPanel onClose={() => setShowSettings(false)} />
            <div className="w-80 border-t border-gray-800 p-4 bg-gray-900">
              <h3 className="text-sm font-medium text-gray-300 mb-3">Documents (RAG)</h3>
              <DocumentList />
            </div>
          </div>
        )}
      </div>

      {error && <Toast message={error} type="error" onClose={clearError} />}
    </ErrorBoundary>
  );
}

export default App;
