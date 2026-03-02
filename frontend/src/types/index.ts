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

export interface ModelDetail {
  name: string;
  family: string | null;
  families: string[];
  parameter_size: string | null;
  quantization_level: string | null;
  context_length: number | null;
  format: string | null;
  parent_model: string | null;
}

export interface ModelParameters {
  temperature: number | null;
  top_p: number | null;
  top_k: number | null;
  num_ctx: number | null;
  repeat_penalty: number | null;
  seed: number | null;
}

export interface ModelSearchResult {
  id: string;
  author: string | null;
  downloads: number;
  likes: number;
  tags: string[];
  last_modified: string | null;
  pipeline_tag: string | null;
  url: string | null;
}

export interface TableInfo {
  name: string;
  row_count: number;
}

export interface DatabaseInfo {
  file_path: string;
  file_size_bytes: number;
  sqlite_version: string;
  table_count: number;
  tables: TableInfo[];
}

export interface ChatTokenEvent {
  token: string;
}

export interface ChatDoneEvent {
  message_id: string;
}
