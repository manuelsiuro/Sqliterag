import { fetchEventSource } from "@microsoft/fetch-event-source";
import type {
  ActionSuggestion,
  Campaign,
  CampaignDetail,
  Conversation,
  ConversationWithMessages,
  DatabaseInfo,
  Document,
  DocumentUploadResponse,
  LocalModel,
  ModelDetail,
  ModelParameters,
  ModelSearchResult,
  ToolCallEvent,
  ToolCreate,
  ToolDefinition,
  ToolResultEvent,
} from "@/types";

const BASE_URL = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// Conversations
export const api = {
  listConversations: () => request<Conversation[]>("/conversations"),

  createConversation: (data: { title?: string; model?: string }) =>
    request<Conversation>("/conversations", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getConversation: (id: string) => request<ConversationWithMessages>(`/conversations/${id}`),

  updateConversation: (id: string, data: { title?: string; model?: string }) =>
    request<Conversation>(`/conversations/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deleteConversation: (id: string) =>
    request<void>(`/conversations/${id}`, { method: "DELETE" }),

  // Chat (SSE)
  streamChat: (
    conversationId: string,
    message: string,
    onToken: (token: string) => void,
    onDone: (messageId: string, actions?: ActionSuggestion[]) => void,
    onError: (err: Error) => void,
    parameters?: ModelParameters,
    onToolCall?: (data: ToolCallEvent) => void,
    onToolResult?: (data: ToolResultEvent) => void,
  ) => {
    const ctrl = new AbortController();
    fetchEventSource(`${BASE_URL}/chat/${conversationId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, parameters }),
      signal: ctrl.signal,
      onmessage(ev) {
        if (ev.event === "token") {
          const data = JSON.parse(ev.data);
          onToken(data.token);
        } else if (ev.event === "done") {
          const data = JSON.parse(ev.data);
          onDone(data.message_id, data.actions);
        } else if (ev.event === "tool_calls") {
          const data = JSON.parse(ev.data) as ToolCallEvent;
          onToolCall?.(data);
        } else if (ev.event === "tool_result") {
          const data = JSON.parse(ev.data) as ToolResultEvent;
          onToolResult?.(data);
        } else if (ev.event === "agent_start") {
          console.debug("Agent started:", JSON.parse(ev.data));
        } else if (ev.event === "self_correction") {
          console.debug("PALADIN self-correction:", JSON.parse(ev.data));
        } else if (ev.event === "agent_done") {
          console.debug("Agent done:", JSON.parse(ev.data));
        } else if (ev.event === "error") {
          const data = JSON.parse(ev.data);
          onError(new Error(data.error || "Stream failed"));
          ctrl.abort();
        }
      },
      onerror(err) {
        onError(err instanceof Error ? err : new Error(String(err)));
        ctrl.abort();
      },
    });
    return ctrl;
  },

  // Models
  listLocalModels: () => request<LocalModel[]>("/models/local"),

  pullModel: (
    name: string,
    onStatus: (status: Record<string, unknown>) => void,
    onError: (err: Error) => void,
  ) => {
    const ctrl = new AbortController();
    fetchEventSource(`${BASE_URL}/models/pull`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
      signal: ctrl.signal,
      onmessage(ev) {
        onStatus(JSON.parse(ev.data));
      },
      onerror(err) {
        onError(err instanceof Error ? err : new Error(String(err)));
        ctrl.abort();
      },
    });
    return ctrl;
  },

  getModelDetails: (name: string) =>
    request<ModelDetail>(`/models/${encodeURIComponent(name)}/details`),

  searchModels: (q: string) => request<ModelSearchResult[]>(`/models/search?q=${encodeURIComponent(q)}`),

  // Documents
  listDocuments: () => request<Document[]>("/documents"),

  uploadDocument: async (file: File): Promise<DocumentUploadResponse> => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${BASE_URL}/documents/upload`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Upload failed");
    }
    return res.json();
  },

  deleteDocument: (id: string) =>
    request<void>(`/documents/${id}`, { method: "DELETE" }),

  // Settings
  getSettings: () => request<Record<string, string>>("/settings"),

  updateSettings: (settings: Record<string, string>) =>
    request<{ status: string }>("/settings", {
      method: "PUT",
      body: JSON.stringify({ settings }),
    }),

  // Database
  getDatabaseInfo: () => request<DatabaseInfo>("/database/info"),

  vacuumDatabase: () =>
    request<{ status: string; file_size_bytes: number }>("/database/vacuum", {
      method: "POST",
    }),

  clearConversations: () =>
    request<{ deleted: number }>("/database/clear-conversations", {
      method: "POST",
    }),

  clearDocuments: () =>
    request<{ deleted: number }>("/database/clear-documents", {
      method: "POST",
    }),

  exportDatabase: async () => {
    const res = await fetch(`${BASE_URL}/database/export`);
    if (!res.ok) throw new Error("Export failed");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "sqliterag.db";
    a.click();
    URL.revokeObjectURL(url);
  },

  // Tools
  listTools: () => request<ToolDefinition[]>("/tools"),

  createTool: (data: ToolCreate) =>
    request<ToolDefinition>("/tools", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateTool: (id: string, data: Partial<ToolCreate> & { is_enabled?: boolean }) =>
    request<ToolDefinition>(`/tools/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deleteTool: (id: string) =>
    request<void>(`/tools/${id}`, { method: "DELETE" }),

  getConversationTools: (conversationId: string) =>
    request<ToolDefinition[]>(`/tools/conversations/${conversationId}`),

  setConversationTools: (conversationId: string, toolIds: string[]) =>
    request<{ status: string; tool_ids: string[] }>(`/tools/conversations/${conversationId}`, {
      method: "PUT",
      body: JSON.stringify({ tool_ids: toolIds }),
    }),

  // RPG
  getGameState: (conversationId: string) =>
    request<Record<string, unknown> | null>(`/conversations/${conversationId}/rpg/state`),

  // Campaigns
  listCampaigns: (status?: string) =>
    request<Campaign[]>(`/campaigns${status ? `?status=${status}` : ""}`),

  getCampaign: (id: string) => request<CampaignDetail>(`/campaigns/${id}`),

  createCampaign: (data: { name: string; description?: string }) =>
    request<Campaign>("/campaigns", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateCampaign: (id: string, data: { name?: string; description?: string; status?: string }) =>
    request<Campaign>(`/campaigns/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deleteCampaign: (id: string) =>
    request<void>(`/campaigns/${id}`, { method: "DELETE" }),

  continueCampaign: (campaignId: string) =>
    request<{ conversation_id: string; session_number: number; campaign_name: string }>(
      `/campaigns/${campaignId}/continue`,
      { method: "POST" },
    ),
};
