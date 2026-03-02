import { create } from "zustand";
import { api } from "@/services/api";
import type { DatabaseInfo } from "@/types";

interface DatabaseState {
  info: DatabaseInfo | null;
  isLoading: boolean;
  actionStatus: string;

  loadInfo: () => Promise<void>;
  vacuum: () => Promise<void>;
  clearConversations: () => Promise<number>;
  clearDocuments: () => Promise<number>;
  exportDatabase: () => Promise<void>;
}

export const useDatabaseStore = create<DatabaseState>((set) => ({
  info: null,
  isLoading: false,
  actionStatus: "",

  loadInfo: async () => {
    set({ isLoading: true });
    try {
      const info = await api.getDatabaseInfo();
      set({ info, isLoading: false });
    } catch {
      set({ isLoading: false, actionStatus: "Failed to load database info" });
    }
  },

  vacuum: async () => {
    set({ actionStatus: "Running VACUUM..." });
    try {
      const result = await api.vacuumDatabase();
      set((s) => ({
        actionStatus: `VACUUM complete — ${formatBytes(result.file_size_bytes)}`,
        info: s.info ? { ...s.info, file_size_bytes: result.file_size_bytes } : s.info,
      }));
    } catch {
      set({ actionStatus: "VACUUM failed" });
    }
  },

  clearConversations: async () => {
    set({ actionStatus: "Clearing conversations..." });
    try {
      const result = await api.clearConversations();
      set({ actionStatus: `Deleted ${result.deleted} rows` });
      return result.deleted;
    } catch {
      set({ actionStatus: "Failed to clear conversations" });
      return 0;
    }
  },

  clearDocuments: async () => {
    set({ actionStatus: "Clearing documents..." });
    try {
      const result = await api.clearDocuments();
      set({ actionStatus: `Deleted ${result.deleted} rows` });
      return result.deleted;
    } catch {
      set({ actionStatus: "Failed to clear documents" });
      return 0;
    }
  },

  exportDatabase: async () => {
    set({ actionStatus: "Exporting..." });
    try {
      await api.exportDatabase();
      set({ actionStatus: "Export downloaded" });
    } catch {
      set({ actionStatus: "Export failed" });
    }
  },
}));

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
