import { create } from "zustand";
import type { MemoryItem, GraphNode, GraphEdge, TokenBudgetSnapshot } from "@/types";
import { api } from "@/services/api";

interface VisualizationState {
  memories: MemoryItem[];
  memoriesTotal: number;
  memoriesLoading: boolean;
  memoryTypeSummary: Record<string, number>;
  memoryFilter: string | null;

  graphNodes: GraphNode[];
  graphEdges: GraphEdge[];
  graphLoading: boolean;

  budget: TokenBudgetSnapshot | null;

  loadMemories: (conversationId: string, filter?: string | null, offset?: number) => Promise<void>;
  loadGraph: (conversationId: string, minStrength?: number) => Promise<void>;
  setBudget: (data: TokenBudgetSnapshot) => void;
  setMemoryFilter: (filter: string | null) => void;
  clear: () => void;
}

export const useVisualizationStore = create<VisualizationState>((set, get) => ({
  memories: [],
  memoriesTotal: 0,
  memoriesLoading: false,
  memoryTypeSummary: {},
  memoryFilter: null,

  graphNodes: [],
  graphEdges: [],
  graphLoading: false,

  budget: null,

  loadMemories: async (conversationId, filter, offset = 0) => {
    set({ memoriesLoading: true });
    try {
      const params: { type?: string; offset?: number } = {};
      const f = filter ?? get().memoryFilter;
      if (f) params.type = f;
      if (offset > 0) params.offset = offset;
      const data = await api.getMemories(conversationId, params);
      set((s) => ({
        memories: offset > 0 ? [...s.memories, ...data.memories] : data.memories,
        memoriesTotal: data.total,
        memoryTypeSummary: data.types_summary,
        memoriesLoading: false,
      }));
    } catch {
      set({ memoriesLoading: false });
    }
  },

  loadGraph: async (conversationId, minStrength) => {
    set({ graphLoading: true });
    try {
      const data = await api.getGraph(conversationId, minStrength ? { min_strength: minStrength } : undefined);
      set({ graphNodes: data.nodes, graphEdges: data.edges, graphLoading: false });
    } catch {
      set({ graphLoading: false });
    }
  },

  setBudget: (data) => set({ budget: data }),

  setMemoryFilter: (filter) => set({ memoryFilter: filter }),

  clear: () =>
    set({
      memories: [],
      memoriesTotal: 0,
      memoryTypeSummary: {},
      memoryFilter: null,
      graphNodes: [],
      graphEdges: [],
      graphLoading: false,
      budget: null,
    }),
}));
