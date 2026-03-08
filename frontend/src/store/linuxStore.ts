import { create } from "zustand";
import { v86Service } from "@/services/v86Service";

interface LinuxState {
    isPanelVisible: boolean;
    isVMBooting: boolean;
    isVMReady: boolean;

    togglePanel: () => void;
    bootVM: () => Promise<void>;
    shutdownVM: () => void;
    /** Wait for the VM to be ready, auto-booting if needed. Rejects on timeout. */
    waitForReady: (timeoutMs?: number) => Promise<void>;
}

export const useLinuxStore = create<LinuxState>((set, get) => ({
    isPanelVisible: false,
    isVMBooting: false,
    isVMReady: false,

    togglePanel: () => {
        const { isPanelVisible, isVMReady, isVMBooting } = get();
        const newVisible = !isPanelVisible;
        set({ isPanelVisible: newVisible });

        // Auto-boot on first open
        if (newVisible && !isVMReady && !isVMBooting) {
            get().bootVM();
        }
    },

    bootVM: async () => {
        if (get().isVMBooting || get().isVMReady) return;
        set({ isVMBooting: true });
        try {
            await v86Service.boot();
            set({ isVMReady: true, isVMBooting: false });
        } catch (err) {
            console.error("Failed to boot VM:", err);
            set({ isVMBooting: false });
        }
    },

    shutdownVM: () => {
        v86Service.shutdown();
        set({ isVMReady: false, isVMBooting: false });
    },

    waitForReady: async (timeoutMs = 35000) => {
        const { isVMReady, isVMBooting } = get();
        if (isVMReady) return;

        // Auto-boot if not already booting
        if (!isVMBooting) {
            get().bootVM();
        }

        // Poll until ready or timeout
        const start = Date.now();
        return new Promise<void>((resolve, reject) => {
            const check = () => {
                if (get().isVMReady) {
                    resolve();
                    return;
                }
                if (Date.now() - start > timeoutMs) {
                    reject(new Error("VM boot timed out"));
                    return;
                }
                setTimeout(check, 250);
            };
            check();
        });
    },
}));
