import { create } from "zustand";

type ModalId = "settings" | "tools" | "database" | "knowledge-graph" | null;

interface UIState {
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  activeModal: ModalId;
  openModal: (id: Exclude<ModalId, null>) => void;
  closeModal: () => void;
  sessionDropdownOpen: boolean;
  setSessionDropdownOpen: (open: boolean) => void;
  gamePanelTab: "game" | "memory" | "insights";
  setGamePanelTab: (tab: "game" | "memory" | "insights") => void;
}

const SIDEBAR_KEY = "sidebar-collapsed";

export const useUIStore = create<UIState>((set, get) => ({
  sidebarCollapsed: localStorage.getItem(SIDEBAR_KEY) === "true",

  toggleSidebar: () => {
    const next = !get().sidebarCollapsed;
    localStorage.setItem(SIDEBAR_KEY, String(next));
    set({ sidebarCollapsed: next });
  },

  activeModal: null,

  openModal: (id) => {
    set((s) => ({ activeModal: s.activeModal === id ? null : id }));
  },

  closeModal: () => set({ activeModal: null }),

  sessionDropdownOpen: false,
  setSessionDropdownOpen: (open) => set({ sessionDropdownOpen: open }),

  gamePanelTab: "game",
  setGamePanelTab: (tab) => set({ gamePanelTab: tab }),
}));
