import { useEffect, useState } from "react";
import { useChatStore } from "@/store/chatStore";
import { useVisualizationStore } from "@/store/visualizationStore";

const TYPE_STYLES: Record<string, { bg: string; text: string; border: string }> = {
  episodic:   { bg: "bg-blue-900/30",   text: "text-blue-300",   border: "border-blue-700/30" },
  semantic:   { bg: "bg-green-900/30",   text: "text-green-300",  border: "border-green-700/30" },
  procedural: { bg: "bg-purple-900/30",  text: "text-purple-300", border: "border-purple-700/30" },
  summary:    { bg: "bg-amber-900/30",   text: "text-amber-300",  border: "border-amber-700/30" },
  recall:     { bg: "bg-cyan-900/30",    text: "text-cyan-300",   border: "border-cyan-700/30" },
};

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function importanceColor(score: number): string {
  if (score >= 0.8) return "bg-red-500";
  if (score >= 0.5) return "bg-amber-500";
  return "bg-green-500";
}

export function MemoryBrowser() {
  const { activeConversationId, messages } = useChatStore();
  const {
    memories, memoriesTotal, memoriesLoading, memoryTypeSummary,
    memoryFilter, loadMemories, setMemoryFilter,
  } = useVisualizationStore();
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const messageCount = messages.length;

  useEffect(() => {
    if (activeConversationId) {
      loadMemories(activeConversationId);
    }
  }, [activeConversationId, messageCount, loadMemories]);

  const handleFilterClick = (type: string) => {
    const newFilter = memoryFilter === type ? null : type;
    setMemoryFilter(newFilter);
    if (activeConversationId) {
      loadMemories(activeConversationId, newFilter);
    }
  };

  const handleLoadMore = () => {
    if (activeConversationId) {
      loadMemories(activeConversationId, undefined, memories.length);
    }
  };

  const allTypes = Object.keys(TYPE_STYLES);

  return (
    <div className="space-y-3">
      {/* Filter pills */}
      <div className="flex flex-wrap gap-1.5">
        {allTypes.map((type) => {
          const count = memoryTypeSummary[type] || 0;
          if (count === 0 && !memoryFilter) return null;
          const style = TYPE_STYLES[type] || TYPE_STYLES.episodic;
          const active = memoryFilter === type;
          return (
            <button
              key={type}
              onClick={() => handleFilterClick(type)}
              className={`text-[10px] px-2 py-0.5 rounded-full border transition-colors ${
                active
                  ? `${style.bg} ${style.text} ${style.border} ring-1 ring-white/20`
                  : `bg-gray-800/50 text-gray-500 border-gray-700/30 hover:text-gray-300`
              }`}
            >
              {type} {count > 0 && `(${count})`}
            </button>
          );
        })}
      </div>

      {/* Memory list */}
      {memoriesLoading && memories.length === 0 ? (
        <div className="text-[11px] text-gray-600 text-center py-4">Loading memories...</div>
      ) : memories.length === 0 ? (
        <div className="text-center py-6 space-y-2">
          <div className="text-2xl opacity-30">{"\uD83E\uDDE0"}</div>
          <div className="text-[11px] text-gray-600 italic">
            No memories yet — play the game to build memory
          </div>
        </div>
      ) : (
        <div className="space-y-1.5">
          {memories.map((m) => {
            const style = TYPE_STYLES[m.memory_type] || TYPE_STYLES.episodic;
            const expanded = expandedId === m.id;
            return (
              <div
                key={m.id}
                className="bg-gray-800/30 rounded-lg px-3 py-2 border border-gray-700/30 cursor-pointer hover:border-gray-600/40 transition-colors"
                onClick={() => setExpandedId(expanded ? null : m.id)}
              >
                {/* Top row: type pill + importance + time */}
                <div className="flex items-center gap-2">
                  <span className={`text-[9px] px-1.5 py-px rounded-full ${style.bg} ${style.text} border ${style.border}`}>
                    {m.memory_type}
                  </span>
                  <div className="flex-1 h-1 bg-gray-700/50 rounded-full overflow-hidden max-w-[40px]">
                    <div
                      className={`h-full rounded-full ${importanceColor(m.importance_score)}`}
                      style={{ width: `${m.importance_score * 100}%` }}
                    />
                  </div>
                  <span className="text-[9px] text-gray-600 ml-auto">
                    {m.created_at ? relativeTime(m.created_at) : ""}
                  </span>
                </div>

                {/* Content */}
                <div className={`text-[11px] text-gray-300 mt-1 ${expanded ? "" : "line-clamp-3"}`}>
                  {m.content}
                </div>

                {/* Entity names */}
                {m.entity_names.length > 0 && (
                  <div className="flex flex-wrap gap-1 mt-1.5">
                    {m.entity_names.map((name) => (
                      <span
                        key={name}
                        className="text-[9px] px-1.5 py-px rounded-full bg-gray-700/50 text-gray-400 border border-gray-600/20"
                      >
                        {name}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            );
          })}

          {/* Load more */}
          {memories.length < memoriesTotal && (
            <button
              onClick={handleLoadMore}
              disabled={memoriesLoading}
              className="w-full py-1.5 text-[11px] text-gray-500 hover:text-gray-300 bg-gray-800/30 rounded-lg border border-gray-700/30 transition-colors disabled:opacity-50"
            >
              {memoriesLoading ? "Loading..." : `Load more (${memoriesTotal - memories.length} remaining)`}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
