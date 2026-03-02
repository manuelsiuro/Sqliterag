import { create } from "zustand";
import { api } from "@/services/api";
import type { LocalModel, ModelDetail, ModelParameters, ModelSearchResult } from "@/types";

interface SettingsState {
  settings: Record<string, string>;
  localModels: LocalModel[];
  searchResults: ModelSearchResult[];
  isSearching: boolean;
  isPulling: boolean;
  pullStatus: string;
  selectedModelDetail: ModelDetail | null;
  isLoadingModelDetail: boolean;
  modelParameters: ModelParameters;

  loadSettings: () => Promise<void>;
  updateSettings: (settings: Record<string, string>) => Promise<void>;
  loadLocalModels: () => Promise<void>;
  searchModels: (query: string) => Promise<void>;
  pullModel: (name: string) => void;
  loadModelDetail: (modelName: string) => Promise<void>;
  updateModelParameters: (params: Partial<ModelParameters>) => void;
}

export const useSettingsStore = create<SettingsState>((set) => ({
  settings: {},
  localModels: [],
  searchResults: [],
  isSearching: false,
  isPulling: false,
  pullStatus: "",
  selectedModelDetail: null,
  isLoadingModelDetail: false,
  modelParameters: {
    temperature: null,
    top_p: null,
    top_k: null,
    num_ctx: null,
    repeat_penalty: null,
    seed: null,
  },

  loadSettings: async () => {
    const settings = await api.getSettings();
    set({ settings });
  },

  updateSettings: async (newSettings) => {
    await api.updateSettings(newSettings);
    set((s) => ({ settings: { ...s.settings, ...newSettings } }));
  },

  loadLocalModels: async () => {
    try {
      const localModels = await api.listLocalModels();
      set({ localModels });
    } catch {
      set({ localModels: [] });
    }
  },

  searchModels: async (query: string) => {
    set({ isSearching: true });
    try {
      const searchResults = await api.searchModels(query);
      set({ searchResults, isSearching: false });
    } catch {
      set({ searchResults: [], isSearching: false });
    }
  },

  pullModel: (name: string) => {
    set({ isPulling: true, pullStatus: "Starting download..." });
    api.pullModel(
      name,
      (status) => {
        const msg = (status.status as string) || "Downloading...";
        const pct = status.completed && status.total
          ? ` (${Math.round((Number(status.completed) / Number(status.total)) * 100)}%)`
          : "";
        set({ pullStatus: `${msg}${pct}` });
        if (msg === "success") {
          set({ isPulling: false, pullStatus: "Download complete!" });
        }
      },
      () => {
        set({ isPulling: false, pullStatus: "Pull failed" });
      },
    );
  },

  loadModelDetail: async (modelName: string) => {
    set({ isLoadingModelDetail: true, selectedModelDetail: null });
    try {
      const detail = await api.getModelDetails(modelName);
      set({ selectedModelDetail: detail, isLoadingModelDetail: false });
    } catch {
      set({ selectedModelDetail: null, isLoadingModelDetail: false });
    }
  },

  updateModelParameters: (params: Partial<ModelParameters>) => {
    set((s) => ({ modelParameters: { ...s.modelParameters, ...params } }));
  },
}));
