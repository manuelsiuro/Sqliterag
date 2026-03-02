export interface Conversation {
  id: string;
  title: string;
  model: string;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  created_at: string;
}

export interface ConversationWithMessages extends Conversation {
  messages: Message[];
}

export interface Document {
  id: string;
  filename: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
}

export interface DocumentUploadResponse {
  document: Document;
  chunks_created: number;
}

export interface LocalModel {
  name: string;
  size: number;
  parameter_size: string | null;
  quantization_level: string | null;
}

export interface ModelSearchResult {
  id: string;
  author: string | null;
  downloads: number;
  likes: number;
  tags: string[];
}

export interface ChatTokenEvent {
  token: string;
}

export interface ChatDoneEvent {
  message_id: string;
}
