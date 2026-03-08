import { useEffect, useState } from "react";
import { useChatStore } from "@/store/chatStore";
import { useCampaignStore } from "@/store/campaignStore";
import { useSettingsStore } from "@/store/settingsStore";
import { useUIStore } from "@/store/uiStore";
import { useLinuxStore } from "@/store/linuxStore";
import { SessionDropdown } from "./SessionDropdown";
import { api } from "@/services/api";

export function TopBar() {
  const {
    conversations,
    activeConversationId,
    loadConversations,
    createConversation,
    selectConversation,
    startDnDGame,
    isStreaming,
    setPendingInput,
  } = useChatStore();
  const { continueCampaign, loadCampaigns } = useCampaignStore();
  const { localModels } = useSettingsStore();
  const { sessionDropdownOpen, setSessionDropdownOpen } = useUIStore();
  const { isPanelVisible, isVMBooting, togglePanel } = useLinuxStore();

  useEffect(() => {
    loadConversations();
    loadCampaigns();
  }, [loadConversations, loadCampaigns]);

  const [isStartingGame, setIsStartingGame] = useState(false);

  const activeConv = conversations.find((c) => c.id === activeConversationId);
  const defaultModel = localModels[0]?.name;

  const handleStartDnD = async () => {
    setIsStartingGame(true);
    try {
      await startDnDGame();
    } finally {
      setIsStartingGame(false);
    }
  };

  const hasCampaign = activeConv?.campaign_id && activeConv?.campaign_name;
  const isEnded = activeConv?.session_status === "ended";

  const handleContinue = async () => {
    if (!activeConv?.campaign_id) return;
    try {
      const newConvId = await continueCampaign(activeConv.campaign_id);
      await loadConversations();
      await selectConversation(newConvId);
      try {
        const recap = await api.getSessionRecap(newConvId);
        if (recap && recap.recap) {
          useChatStore.getState().injectRecapMessage(recap);
        }
      } catch {
        // Silent
      }
    } catch (err) {
      console.error("Continue campaign failed:", err);
    }
  };

  const handleEditorSetup = () => {
    const editorPrompt = `You are an expert web developer and game designer. I want you to create a tiny, self-contained HTML mini-game.

CRITICAL INSTRUCTIONS BEFORE WE BEGIN:
1. DO NOT GENERATE ANY CODE YET. 
2. Reply ONLY with an acknowledgment of these rules and ask me what kind of game I would like to build.
3. When you DO write code later, it MUST be constrained to 2500 tokens or less. Keep logic extremely simple so it doesn't get cut off.
4. Future code must be exactly ONE markdown code block starting with \`\`\`html and ending with \`\`\`.
5. Future code must use ONLY vanilla JS, CSS, and HTML5 (like <canvas>). No external dependencies.
6. Code must be minified to fit in the token limit.
7. No comments in the code.
8. If the code is too long, it will be cut off, so keep it extremely concise and compact whithout comments.
9. If the user asks for a game that is too complex for the 2500 tokens limit, ask them if they would like a simpler version of the game.`;
    setPendingInput(editorPrompt);
  };

  return (
    <header className="h-12 bg-gray-900 border-b border-gray-800 shrink-0 flex items-center px-4 gap-3 z-30">
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

      {/* Campaign badge */}
      {hasCampaign && (
        <span className="text-[11px] px-2 py-1 rounded-full bg-amber-900/30 text-amber-300 border border-amber-700/30 whitespace-nowrap">
          {activeConv.campaign_name}
          {activeConv.session_number != null && (
            <span className="text-amber-500/70"> &gt; Session #{activeConv.session_number}</span>
          )}
        </span>
      )}

      {/* Continue campaign button */}
      {hasCampaign && isEnded && (
        <button
          onClick={handleContinue}
          className="px-3 py-1.5 bg-emerald-700 hover:bg-emerald-600 text-white text-sm rounded-lg transition-colors whitespace-nowrap"
        >
          Continue Campaign
        </button>
      )}

      {/* Linux button */}
      <button
        title={isPanelVisible ? "Hide Linux Terminal" : "Open Linux Terminal"}
        onClick={togglePanel}
        className={`px-3 py-1.5 text-white text-sm rounded-lg transition-colors ml-auto flex items-center gap-1.5 ${isPanelVisible
            ? "bg-green-600 hover:bg-green-500 ring-1 ring-green-400/50"
            : "bg-green-700 hover:bg-green-600"
          }`}
      >
        {isVMBooting ? (
          <>
            <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Booting...
          </>
        ) : (
          <>
            <span className="text-base leading-none">🐧</span>
            Linux
          </>
        )}
      </button>

      {/* Editor button */}
      <button
        title="Insert Editor Setup Prompt"
        onClick={handleEditorSetup}
        className="px-3 py-1.5 bg-purple-700 hover:bg-purple-600 text-white text-sm rounded-lg transition-colors flex items-center gap-1.5"
      >
        <span className="text-base leading-none">✨</span>
        Editor
      </button>

      {/* Start D&D game button */}
      <button
        onClick={handleStartDnD}
        disabled={isStartingGame || isStreaming}
        className="px-3 py-1.5 bg-amber-700 hover:bg-amber-600 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm rounded-lg transition-colors flex items-center gap-1.5"
      >
        {isStartingGame ? (
          <>
            <svg className="w-3.5 h-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Starting...
          </>
        ) : (
          <>
            <span className="text-base leading-none">&#9876;</span>
            Start D&D
          </>
        )}
      </button>

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
