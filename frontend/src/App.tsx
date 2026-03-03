import { useEffect } from "react";
import { ErrorBoundary, Toast, Modal } from "@/components/common";
import { TopBar } from "@/components/layout";
import { Sidebar } from "@/components/sidebar";
import { ChatWindow } from "@/components/chat";
import { SettingsPanel } from "@/components/settings";
import { DatabasePanel } from "@/components/database";
import { ToolsPanel } from "@/components/tools";
import { DocumentList } from "@/components/documents";
import { GamePanel } from "@/components/rpg/GamePanel";
import { useChatStore } from "@/store/chatStore";
import { useSettingsStore } from "@/store/settingsStore";
import { useUIStore } from "@/store/uiStore";

const MODAL_TITLES: Record<string, string> = {
  settings: "Settings",
  tools: "Tools",
  database: "Database",
};

function App() {
  const { error, clearError } = useChatStore();
  const { loadLocalModels } = useSettingsStore();
  const { activeModal, closeModal } = useUIStore();

  useEffect(() => {
    loadLocalModels();
  }, [loadLocalModels]);

  return (
    <ErrorBoundary>
      <div className="flex flex-col h-screen bg-gray-950 text-white">
        <TopBar />
        <div className="flex flex-1 min-h-0">
          <Sidebar />
          <main className="flex-1 flex flex-col min-w-0">
            <ChatWindow />
          </main>
          <GamePanel />
        </div>
      </div>

      {activeModal && (
        <Modal
          open
          title={MODAL_TITLES[activeModal] ?? ""}
          onClose={closeModal}
        >
          {activeModal === "settings" && (
            <div className="grid grid-cols-1 md:grid-cols-[1fr_300px] gap-6">
              <SettingsPanel />
              <div className="space-y-3">
                <h3 className="text-sm font-medium text-gray-300">Documents (RAG)</h3>
                <DocumentList />
              </div>
            </div>
          )}
          {activeModal === "tools" && <ToolsPanel />}
          {activeModal === "database" && <DatabasePanel />}
        </Modal>
      )}

      {error && <Toast message={error} type="error" onClose={clearError} />}
    </ErrorBoundary>
  );
}

export default App;
