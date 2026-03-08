import { create } from "zustand";
import type { Conversation, Message, ModelParameters } from "@/types";
import { api } from "@/services/api";
import { useSettingsStore } from "@/store/settingsStore";
import { useToolStore } from "@/store/toolStore";
import { useVisualizationStore } from "@/store/visualizationStore";

interface ChatState {
  conversations: Conversation[];
  activeConversationId: string | null;
  messages: Message[];
  streamingContent: string;
  isStreaming: boolean;
  isToolCalling: boolean;
  isLoading: boolean;
  error: string | null;
  abortController: AbortController | null;
  pendingInput: string | null;

  loadConversations: () => Promise<void>;
  createConversation: (model?: string) => Promise<Conversation>;
  selectConversation: (id: string) => Promise<void>;
  deleteConversation: (id: string) => Promise<void>;
  updateConversationTitle: (id: string, title: string) => Promise<void>;
  sendMessage: (message: string, images?: string[]) => void;
  stopStreaming: () => void;
  clearError: () => void;
  setPendingInput: (text: string | null) => void;
  injectRecapMessage: (recap: Record<string, unknown>) => void;
  startDnDGame: () => Promise<void>;
}

export const useChatStore = create<ChatState>((set, get) => ({
  conversations: [],
  activeConversationId: null,
  messages: [],
  streamingContent: "",
  isStreaming: false,
  isToolCalling: false,
  isLoading: false,
  error: null,
  abortController: null,
  pendingInput: null,

  loadConversations: async () => {
    try {
      const conversations = await api.listConversations();
      set({ conversations });
    } catch (err) {
      set({ error: err instanceof Error ? err.message : "Failed to load conversations" });
    }
  },

  createConversation: async (model?: string) => {
    const conv = await api.createConversation({ model });
    set((s) => ({ conversations: [conv, ...s.conversations] }));
    await get().selectConversation(conv.id);
    return conv;
  },

  selectConversation: async (id: string) => {
    set({ isLoading: true, activeConversationId: id });
    try {
      const data = await api.getConversation(id);
      let msgs = data.messages;

      // Auto-inject recap for empty campaign sessions
      if (msgs.length === 0) {
        try {
          const recap = await api.getSessionRecap(id);
          if (recap && recap.recap) {
            const recapMsg: Message = {
              id: "recap-" + id,
              conversation_id: id,
              role: "tool",
              content: JSON.stringify(recap),
              tool_name: "session_recap",
              created_at: new Date().toISOString(),
            };
            msgs = [recapMsg, ...msgs];
          }
        } catch {
          // Silent — recap is optional
        }
      }

      set({ messages: msgs, isLoading: false });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Failed to load conversation",
        isLoading: false,
      });
    }
  },

  deleteConversation: async (id: string) => {
    await api.deleteConversation(id);
    set((s) => {
      const conversations = s.conversations.filter((c) => c.id !== id);
      const isActive = s.activeConversationId === id;
      return {
        conversations,
        ...(isActive ? { activeConversationId: null, messages: [] } : {}),
      };
    });
  },

  updateConversationTitle: async (id: string, title: string) => {
    await api.updateConversation(id, { title });
    set((s) => ({
      conversations: s.conversations.map((c) => (c.id === id ? { ...c, title } : c)),
    }));
  },

  sendMessage: (message: string, images?: string[]) => {
    const { activeConversationId, messages, conversations } = get();
    if (!activeConversationId || get().isStreaming) return;

    // Auto-name conversation on first message
    if (messages.length === 0) {
      const conv = conversations.find((c) => c.id === activeConversationId);
      if (conv && conv.title === "New Chat") {
        const autoTitle = message.length > 40 ? message.slice(0, 40) + "..." : message;
        get().updateConversationTitle(activeConversationId, autoTitle);
      }
    }

    const userMsg: Message = {
      id: crypto.randomUUID(),
      conversation_id: activeConversationId,
      role: "user",
      content: message,
      ...(images?.length ? { images } : {}),
      created_at: new Date().toISOString(),
    };

    set((s) => ({
      messages: [...s.messages, userMsg],
      isStreaming: true,
      streamingContent: "",
    }));

    // Read model parameters from settings, pass if any are set
    const { modelParameters } = useSettingsStore.getState();
    const hasParams = Object.values(modelParameters).some((v) => v !== null);
    const parameters: ModelParameters | undefined = hasParams ? modelParameters : undefined;

    const ctrl = api.streamChat(
      activeConversationId,
      message,
      images,
      (token) => {
        set((s) => ({ streamingContent: s.streamingContent + token }));
      },
      (messageId, actions, metrics) => {
        const content = get().streamingContent;
        const assistantMsg: Message = {
          id: messageId,
          conversation_id: activeConversationId,
          role: "assistant",
          content,
          ...(actions?.length ? { actions } : {}),
          ...(metrics ? { metrics } : {}),
          created_at: new Date().toISOString(),
        };
        set((s) => ({
          messages: [...s.messages, assistantMsg],
          streamingContent: "",
          isStreaming: false,
          isToolCalling: false,
          abortController: null,
        }));
        // Refresh conversations to update timestamps
        get().loadConversations();
      },
      (err) => {
        set({ error: err.message, isStreaming: false, isToolCalling: false, streamingContent: "", abortController: null });
      },
      parameters,
      // onToolCall
      (data) => {
        const toolCallMsg: Message = {
          id: data.message_id,
          conversation_id: activeConversationId,
          role: "assistant",
          content: "",
          tool_calls: data.tool_calls,
          created_at: new Date().toISOString(),
        };
        set((s) => ({
          messages: [...s.messages, toolCallMsg],
          isToolCalling: true,
        }));
      },
      // onToolResult
      (data) => {
        const toolResultMsg: Message = {
          id: data.message_id,
          conversation_id: activeConversationId,
          role: "tool",
          content: data.result,
          tool_name: data.tool_name,
          created_at: new Date().toISOString(),
        };
        set((s) => ({
          messages: [...s.messages, toolResultMsg],
        }));
      },
      // onBudget (Phase 5.6)
      (data) => {
        useVisualizationStore.getState().setBudget(data);
      },
    );
    set({ abortController: ctrl });
  },

  stopStreaming: () => {
    const { abortController, streamingContent, activeConversationId } = get();
    if (abortController) {
      abortController.abort();
    }
    // If there's partial content, keep it as a message
    if (streamingContent && activeConversationId) {
      const partialMsg: Message = {
        id: crypto.randomUUID(),
        conversation_id: activeConversationId,
        role: "assistant",
        content: streamingContent,
        created_at: new Date().toISOString(),
      };
      set((s) => ({
        messages: [...s.messages, partialMsg],
        streamingContent: "",
        isStreaming: false,
        abortController: null,
      }));
    } else {
      set({ streamingContent: "", isStreaming: false, abortController: null });
    }
  },

  clearError: () => set({ error: null }),

  setPendingInput: (text: string | null) => set({ pendingInput: text }),

  injectRecapMessage: (recap: Record<string, unknown>) => {
    const { activeConversationId, messages } = get();
    if (!activeConversationId || !recap.recap) return;
    // Avoid duplicates
    if (messages.some((m) => m.id === "recap-" + activeConversationId)) return;
    const recapMsg: Message = {
      id: "recap-" + activeConversationId,
      conversation_id: activeConversationId,
      role: "tool",
      content: JSON.stringify(recap),
      tool_name: "session_recap",
      created_at: new Date().toISOString(),
    };
    set((s) => ({ messages: [recapMsg, ...s.messages] }));
  },

  startDnDGame: async () => {
    const defaultModel = useSettingsStore.getState().localModels[0]?.name;
    if (!defaultModel) {
      set({ error: "No models available. Install a model in Ollama first." });
      return;
    }

    try {
      const conv = await get().createConversation(defaultModel);
      await get().updateConversationTitle(conv.id, "D&D Adventure");

      // Enable all tools for this conversation
      const toolStore = useToolStore.getState();
      if (toolStore.tools.length === 0) {
        await toolStore.loadTools();
      }
      const allToolIds = useToolStore.getState().tools.map((t) => t.id);
      if (allToolIds.length > 0) {
        await toolStore.setConversationToolsBatch(conv.id, allToolIds);
      }

      const prompt = `Start a new D&D 5e adventure for me. Use tools in this order — batch calls when possible:

1. init_game_session — create a world with a creative fantasy name
2. create_character — level 1 hero, interesting race/class, standard array stats (15,14,13,12,10,8)
3. create_item (2-3x) — class-appropriate weapon, armor, and one adventuring item
4. give_item for each item, then equip_item for weapon and armor
5. create_location — evocative starting location
6. set_environment — time, weather, season
7. create_quest — compelling hook, 2-3 objectives, XP/gold rewards

After setup, write an immersive intro: world, character backstory, scene, quest hook. End with 2-3 choices.`;

      get().sendMessage(prompt);
    } catch (err) {
      set({ error: err instanceof Error ? err.message : "Failed to start D&D game" });
    }
  },
}));
