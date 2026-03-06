export interface Conversation {
  id: string;
  title: string;
  model: string;
  created_at: string;
  updated_at: string;
  campaign_id?: string | null;
  campaign_name?: string | null;
  session_number?: number | null;
  session_status?: string | null;
}

export interface Campaign {
  id: string;
  name: string;
  world_name: string;
  description: string;
  status: "active" | "completed";
  session_count: number;
  created_at: string;
  updated_at: string;
}

export interface CampaignSession {
  conversation_id: string;
  session_number: number;
  status: "active" | "ended";
  world_name: string;
  summary: string | null;
  created_at: string;
}

export interface CampaignDetail extends Campaign {
  sessions: CampaignSession[];
}

export interface ActionSuggestion {
  label: string;
  description: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system" | "tool";
  content: string;
  tool_calls?: Array<{ function: { name: string; arguments: Record<string, unknown> } }> | null;
  tool_name?: string | null;
  actions?: ActionSuggestion[];
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
  presence_penalty: number | null;
  num_predict: number | null;
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
  actions?: ActionSuggestion[];
}

// Tool types
export interface ToolParameterProperty {
  type: string;
  description?: string;
  enum?: string[];
}

export interface ToolParametersSchema {
  type: string;
  required: string[];
  properties: Record<string, ToolParameterProperty>;
}

export interface ToolDefinition {
  id: string;
  name: string;
  description: string;
  parameters_schema: ToolParametersSchema;
  execution_type: "http" | "mock" | "builtin";
  execution_config: Record<string, unknown>;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface ToolCreate {
  name: string;
  description: string;
  parameters_schema: ToolParametersSchema;
  execution_type: string;
  execution_config: Record<string, unknown>;
}

export interface ToolCallEvent {
  tool_calls: Array<{ function: { name: string; arguments: Record<string, unknown> } }>;
  message_id: string;
  agent?: string;
}

export interface ToolResultEvent {
  tool_name: string;
  arguments: Record<string, unknown>;
  result: string;
  message_id: string;
  agent?: string;
}

// Phase 5.6 — Visualization types
export interface MemoryItem {
  id: string;
  memory_type: string;
  entity_type: string | null;
  content: string;
  importance_score: number;
  entity_names: string[];
  session_number: number | null;
  created_at: string;
}

export interface GraphNode {
  id: string;
  name: string;
  type: string;
  entity_id: string;
}

export interface GraphEdge {
  source_id: string;
  target_id: string;
  relationship: string;
  strength: number;
  source_type: string;
  target_type: string;
}

export interface TokenBudgetSnapshot {
  num_ctx: number;
  system_prompt_tokens: number;
  rag_context_tokens: number;
  tool_definitions_tokens: number;
  conversation_history_tokens: number;
  response_reserve: number;
  safety_buffer: number;
  total_input_tokens: number;
  input_budget: number;
  utilization_pct: number;
  tokens_remaining: number;
  summarized_message_count: number;
  truncated_message_count: number;
}
