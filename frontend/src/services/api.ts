import { fetchEventSource } from "@microsoft/fetch-event-source";
import type {
  Conversation,
  ConversationWithMessages,
  Document,
  DocumentUploadResponse,
  LocalModel,
  ModelSearchResult,
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
    onDone: (messageId: string) => void,
    onError: (err: Error) => void,
  ) => {
    const ctrl = new AbortController();
    fetchEventSource(`${BASE_URL}/chat/${conversationId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
      signal: ctrl.signal,
      onmessage(ev) {
        if (ev.event === "token") {
          const data = JSON.parse(ev.data);
          onToken(data.token);
        } else if (ev.event === "done") {
          const data = JSON.parse(ev.data);
          onDone(data.message_id);
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
};
