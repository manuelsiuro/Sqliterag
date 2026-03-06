import type { ToolRendererProps } from "./toolRendererRegistry";

interface MemoryArchivedData {
  type: "memory_archived";
  description: string;
  importance: number;
  entities: string[];
  memory_type: string;
  error?: string;
}

interface MemoryEntry {
  content: string;
  importance: number;
  memory_type: string;
  entities: string[];
  created_at: string | null;
}

interface MemoryResultsData {
  type: "memory_results";
  query: string;
  memories: MemoryEntry[];
  count: number;
  error?: string;
}

interface SessionSummaryData {
  type: "session_summary";
  session_number: number;
  events: MemoryEntry[];
  count: number;
  summary: string;
  narrative?: boolean;
  error?: string;
}

interface RecallResultsData {
  type: "recall_results";
  query: string;
  memories: MemoryEntry[];
  count: number;
  message?: string;
  error?: string;
}

interface SessionEndedData {
  type: "session_ended";
  session_number: number;
  world_name?: string;
  summary: string;
  status: string;
  campaign_id?: string;
  campaign_name?: string;
  error?: string;
}

const MEMORY_TYPE_COLORS: Record<string, string> = {
  episodic: "bg-blue-900/40 text-blue-300 border-blue-700/40",
  semantic: "bg-purple-900/40 text-purple-300 border-purple-700/40",
  procedural: "bg-amber-900/40 text-amber-300 border-amber-700/40",
};

function getTypeStyle(memoryType: string): string {
  return MEMORY_TYPE_COLORS[memoryType] || "bg-gray-700/40 text-gray-300 border-gray-600/40";
}

function ImportanceDot({ importance }: { importance: number }) {
  const color =
    importance >= 8 ? "bg-red-400" : importance >= 5 ? "bg-yellow-400" : "bg-green-400";
  return (
    <span
      className={`inline-block w-2 h-2 rounded-full ${color}`}
      title={`Importance: ${importance}/10`}
    />
  );
}

function TypeBadge({ memoryType }: { memoryType: string }) {
  return (
    <span
      className={`text-xs px-1.5 py-0.5 rounded border ${getTypeStyle(memoryType)}`}
    >
      {memoryType}
    </span>
  );
}

function EntityPills({ entities }: { entities: string[] }) {
  if (!entities.length) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {entities.map((name, i) => (
        <span
          key={i}
          className="text-xs px-1.5 py-0.5 rounded-full bg-gray-700/50 text-gray-300 border border-gray-600/30"
        >
          {name}
        </span>
      ))}
    </div>
  );
}

function MemoryEntryCard({ entry }: { entry: MemoryEntry }) {
  return (
    <div className="bg-gray-800/20 rounded px-2.5 py-2 border border-gray-700/20 space-y-1">
      <div className="flex items-center gap-2 flex-wrap">
        <TypeBadge memoryType={entry.memory_type} />
        <ImportanceDot importance={entry.importance} />
        {entry.created_at && (
          <span className="text-xs text-gray-500">
            {new Date(entry.created_at).toLocaleString()}
          </span>
        )}
      </div>
      <p className="text-sm text-gray-200">{entry.content}</p>
      <EntityPills entities={entry.entities} />
    </div>
  );
}

function ArchivedView({ d }: { d: MemoryArchivedData }) {
  return (
    <div className="bg-gray-800/30 rounded-lg px-3 py-2.5 border border-gray-700/30 space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-base">🧠</span>
        <span className="text-sm font-medium text-gray-200">Memory Archived</span>
        <TypeBadge memoryType={d.memory_type} />
        <ImportanceDot importance={d.importance} />
      </div>
      <p className="text-sm text-gray-300">{d.description}</p>
      <EntityPills entities={d.entities} />
    </div>
  );
}

function ResultsView({ d }: { d: MemoryResultsData }) {
  return (
    <div className="bg-gray-800/30 rounded-lg px-3 py-2.5 border border-gray-700/30 space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-base">🔍</span>
        <span className="text-sm font-medium text-gray-200">Memory Search</span>
        <span className="text-xs text-gray-500">"{d.query}"</span>
        <span className="text-xs text-gray-500">({d.count} result{d.count !== 1 ? "s" : ""})</span>
      </div>
      {d.memories.length === 0 ? (
        <p className="text-sm text-gray-500 italic">No matching memories found.</p>
      ) : (
        <div className="space-y-1.5">
          {d.memories.map((entry, i) => (
            <MemoryEntryCard key={i} entry={entry} />
          ))}
        </div>
      )}
    </div>
  );
}

function SummaryView({ d }: { d: SessionSummaryData }) {
  return (
    <div className="bg-gray-800/30 rounded-lg px-3 py-2.5 border border-gray-700/30 space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-base">{d.narrative ? "📜" : "📋"}</span>
        <span className="text-sm font-medium text-gray-200">Session Summary</span>
        {d.narrative && (
          <span className="text-xs px-1.5 py-0.5 rounded border bg-amber-900/40 text-amber-300 border-amber-700/40">
            narrative
          </span>
        )}
        {d.count > 0 && (
          <span className="text-xs text-gray-500">({d.count} memor{d.count !== 1 ? "ies" : "y"})</span>
        )}
      </div>
      <p className={`text-sm ${d.narrative ? "text-gray-200 italic" : "text-gray-400"}`}>
        {d.summary}
      </p>
      {d.events.length > 0 && (
        <div className="space-y-1.5">
          {d.events.map((entry, i) => (
            <MemoryEntryCard key={i} entry={entry} />
          ))}
        </div>
      )}
    </div>
  );
}

function RecallView({ d }: { d: RecallResultsData }) {
  return (
    <div className="bg-gray-800/30 rounded-lg px-3 py-2.5 border border-gray-700/30 space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-base">&#x267B;&#xFE0F;</span>
        <span className="text-sm font-medium text-gray-200">Recalled Context</span>
        <span className="text-xs text-gray-500">&quot;{d.query}&quot;</span>
        <span className="text-xs text-gray-500">({d.count} result{d.count !== 1 ? "s" : ""})</span>
      </div>
      {d.message && d.memories.length === 0 ? (
        <p className="text-sm text-gray-500 italic">{d.message}</p>
      ) : d.memories.length === 0 ? (
        <p className="text-sm text-gray-500 italic">No recalled context found.</p>
      ) : (
        <div className="space-y-1.5">
          {d.memories.map((entry, i) => (
            <MemoryEntryCard key={i} entry={entry} />
          ))}
        </div>
      )}
    </div>
  );
}

function EndedView({ d }: { d: SessionEndedData }) {
  return (
    <div className="bg-gray-800/30 rounded-lg px-3 py-2.5 border border-amber-700/30 space-y-2">
      <div className="flex items-center gap-2">
        <span className="text-base">📖</span>
        <span className="text-sm font-medium text-amber-200">Session Ended</span>
        {d.session_number && (
          <span className="text-xs text-gray-400">#{d.session_number}</span>
        )}
        {d.world_name && (
          <span className="text-xs text-gray-500">{d.world_name}</span>
        )}
      </div>
      <p className="text-sm text-gray-200 italic">{d.summary}</p>
      {d.campaign_name && (
        <div className="flex items-center gap-1.5 pt-1 border-t border-amber-800/20">
          <span className="text-[10px] text-amber-400/70">Campaign:</span>
          <span className="text-xs text-amber-300">{d.campaign_name}</span>
          <span className="text-[10px] text-gray-500 ml-auto">Continue in a new session</span>
        </div>
      )}
    </div>
  );
}

export function MemoryRenderer({ data }: ToolRendererProps) {
  const d = data as MemoryArchivedData | MemoryResultsData | RecallResultsData | SessionSummaryData | SessionEndedData;

  if (d.error) {
    return <div className="mt-2 text-red-400 text-sm">{d.error}</div>;
  }

  switch (d.type) {
    case "memory_archived":
      return <ArchivedView d={d as MemoryArchivedData} />;
    case "memory_results":
      return <ResultsView d={d as MemoryResultsData} />;
    case "recall_results":
      return <RecallView d={d as RecallResultsData} />;
    case "session_summary":
      return <SummaryView d={d as SessionSummaryData} />;
    case "session_ended":
      return <EndedView d={d as SessionEndedData} />;
    default:
      return null;
  }
}
