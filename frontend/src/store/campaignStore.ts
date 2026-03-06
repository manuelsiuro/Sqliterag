import { create } from "zustand";
import { api } from "@/services/api";
import type { Campaign, CampaignDetail } from "@/types";

interface CampaignState {
  campaigns: Campaign[];
  activeCampaignId: string | null;
  activeCampaignDetail: CampaignDetail | null;
  isLoading: boolean;

  loadCampaigns: () => Promise<void>;
  selectCampaign: (id: string) => Promise<void>;
  createCampaign: (name: string, description?: string) => Promise<Campaign>;
  continueCampaign: (campaignId: string) => Promise<string>;
  clearSelection: () => void;
  refresh: () => Promise<void>;
}

export const useCampaignStore = create<CampaignState>((set, get) => ({
  campaigns: [],
  activeCampaignId: null,
  activeCampaignDetail: null,
  isLoading: false,

  loadCampaigns: async () => {
    try {
      const campaigns = await api.listCampaigns();
      set({ campaigns });
    } catch {
      // silent
    }
  },

  selectCampaign: async (id: string) => {
    set({ activeCampaignId: id, isLoading: true });
    try {
      const detail = await api.getCampaign(id);
      set({ activeCampaignDetail: detail, isLoading: false });
    } catch {
      set({ isLoading: false });
    }
  },

  createCampaign: async (name: string, description?: string) => {
    const campaign = await api.createCampaign({ name, description });
    await get().loadCampaigns();
    return campaign;
  },

  continueCampaign: async (campaignId: string) => {
    const result = await api.continueCampaign(campaignId);
    await get().loadCampaigns();
    return result.conversation_id;
  },

  clearSelection: () => {
    set({ activeCampaignId: null, activeCampaignDetail: null });
  },

  refresh: async () => {
    await get().loadCampaigns();
    const { activeCampaignId } = get();
    if (activeCampaignId) {
      await get().selectCampaign(activeCampaignId);
    }
  },
}));
