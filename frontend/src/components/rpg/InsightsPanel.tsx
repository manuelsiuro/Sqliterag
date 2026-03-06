import { useEffect } from "react";
import { useChatStore } from "@/store/chatStore";
import { useVisualizationStore } from "@/store/visualizationStore";
import { useUIStore } from "@/store/uiStore";
import { TokenBudgetBar } from "./TokenBudgetBar";

const ENTITY_TYPE_COLORS: Record<string, string> = {
  character: "text-blue-400",
  npc: "text-purple-400",
  location: "text-amber-400",
  quest: "text-green-400",
  item: "text-gray-400",
};

export function InsightsPanel() {
  const { activeConversationId } = useChatStore();
  const { budget, graphNodes, graphEdges, graphLoading, loadGraph } =
    useVisualizationStore();
  const { openModal } = useUIStore();

  useEffect(() => {
    if (activeConversationId) {
      loadGraph(activeConversationId);
    }
  }, [activeConversationId, loadGraph]);

  // Entity type breakdown
  const typeBreakdown: Record<string, number> = {};
  for (const n of graphNodes) {
    typeBreakdown[n.type] = (typeBreakdown[n.type] || 0) + 1;
  }

  return (
    <div className="space-y-4">
      {/* Token Budget */}
      <section>
        <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
          Token Budget
        </h3>
        {budget ? (
          <div className="bg-gray-800/30 rounded-lg px-3 py-2.5 border border-gray-700/30">
            <TokenBudgetBar budget={budget} />
          </div>
        ) : (
          <div className="text-[11px] text-gray-600 italic">
            Send a message to see token budget
          </div>
        )}
      </section>

      {/* Knowledge Graph Stats */}
      <section className="border-t border-gray-800/60 pt-3">
        <h3 className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">
          Knowledge Graph
        </h3>
        {graphLoading ? (
          <div className="text-[11px] text-gray-600">Loading...</div>
        ) : graphNodes.length === 0 ? (
          <div className="text-[11px] text-gray-600 italic">
            No relationships yet
          </div>
        ) : (
          <div className="bg-gray-800/30 rounded-lg px-3 py-2.5 border border-gray-700/30 space-y-2">
            <div className="flex gap-4 text-xs">
              <div>
                <span className="text-gray-500">Nodes </span>
                <span className="text-white font-medium">{graphNodes.length}</span>
              </div>
              <div>
                <span className="text-gray-500">Edges </span>
                <span className="text-white font-medium">{graphEdges.length}</span>
              </div>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(typeBreakdown).map(([type, count]) => (
                <span
                  key={type}
                  className={`text-[10px] px-1.5 py-px rounded-full bg-gray-800/80 border border-gray-700/30 ${ENTITY_TYPE_COLORS[type] || "text-gray-400"}`}
                >
                  {type} ({count})
                </span>
              ))}
            </div>
            <button
              onClick={() => openModal("knowledge-graph")}
              className="w-full mt-1 py-1.5 text-xs bg-indigo-700/50 hover:bg-indigo-600/50 text-indigo-200 rounded-md border border-indigo-600/30 transition-colors"
            >
              View Knowledge Graph
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
