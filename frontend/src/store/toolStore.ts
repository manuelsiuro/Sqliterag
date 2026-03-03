import { create } from "zustand";
import type { ToolCreate, ToolDefinition } from "@/types";
import { api } from "@/services/api";

interface ToolState {
  tools: ToolDefinition[];
  conversationToolIds: string[];
  isLoading: boolean;

  loadTools: () => Promise<void>;
  createTool: (data: ToolCreate) => Promise<ToolDefinition>;
  updateTool: (id: string, data: Partial<ToolCreate> & { is_enabled?: boolean }) => Promise<void>;
  deleteTool: (id: string) => Promise<void>;
  loadConversationTools: (conversationId: string) => Promise<void>;
  toggleConversationTool: (conversationId: string, toolId: string) => Promise<void>;
  setConversationToolsBatch: (conversationId: string, toolIds: string[]) => Promise<void>;
  toggleConversationToolGroup: (conversationId: string, groupToolIds: string[], enable: boolean) => Promise<void>;
}

export const useToolStore = create<ToolState>((set, get) => ({
  tools: [],
  conversationToolIds: [],
  isLoading: false,

  loadTools: async () => {
    set({ isLoading: true });
    try {
      const tools = await api.listTools();
      set({ tools, isLoading: false });
    } catch {
      set({ isLoading: false });
    }
  },

  createTool: async (data: ToolCreate) => {
    const tool = await api.createTool(data);
    set((s) => ({ tools: [tool, ...s.tools] }));
    return tool;
  },

  updateTool: async (id, data) => {
    const updated = await api.updateTool(id, data);
    set((s) => ({
      tools: s.tools.map((t) => (t.id === id ? updated : t)),
    }));
  },

  deleteTool: async (id) => {
    await api.deleteTool(id);
    set((s) => ({
      tools: s.tools.filter((t) => t.id !== id),
      conversationToolIds: s.conversationToolIds.filter((tid) => tid !== id),
    }));
  },

  loadConversationTools: async (conversationId) => {
    try {
      const tools = await api.getConversationTools(conversationId);
      set({ conversationToolIds: tools.map((t) => t.id) });
    } catch {
      set({ conversationToolIds: [] });
    }
  },

  toggleConversationTool: async (conversationId, toolId) => {
    const { conversationToolIds } = get();
    const newIds = conversationToolIds.includes(toolId)
      ? conversationToolIds.filter((id) => id !== toolId)
      : [...conversationToolIds, toolId];

    await api.setConversationTools(conversationId, newIds);
    set({ conversationToolIds: newIds });
  },

  setConversationToolsBatch: async (conversationId, toolIds) => {
    set({ conversationToolIds: toolIds });
    await api.setConversationTools(conversationId, toolIds);
  },

  toggleConversationToolGroup: async (conversationId, groupToolIds, enable) => {
    const { conversationToolIds } = get();
    let newIds: string[];
    if (enable) {
      const toAdd = groupToolIds.filter((id) => !conversationToolIds.includes(id));
      newIds = [...conversationToolIds, ...toAdd];
    } else {
      const removeSet = new Set(groupToolIds);
      newIds = conversationToolIds.filter((id) => !removeSet.has(id));
    }
    set({ conversationToolIds: newIds });
    await api.setConversationTools(conversationId, newIds);
  },
}));
