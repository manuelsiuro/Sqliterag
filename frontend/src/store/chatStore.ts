import { create } from "zustand";
import type { Conversation, Message, ModelParameters } from "@/types";
import { api } from "@/services/api";
import { useSettingsStore } from "@/store/settingsStore";

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
  sendMessage: (message: string) => void;
  stopStreaming: () => void;
  clearError: () => void;
  setPendingInput: (text: string | null) => void;
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
      set({ messages: data.messages, isLoading: false });
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

  sendMessage: (message: string) => {
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
      (token) => {
        set((s) => ({ streamingContent: s.streamingContent + token }));
      },
      (messageId, actions) => {
        const content = get().streamingContent;
        const assistantMsg: Message = {
          id: messageId,
          conversation_id: activeConversationId,
          role: "assistant",
          content,
          ...(actions?.length ? { actions } : {}),
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
}));
