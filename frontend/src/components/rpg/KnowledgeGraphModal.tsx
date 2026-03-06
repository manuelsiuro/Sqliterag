import { useEffect, useState, useRef } from "react";
import { useChatStore } from "@/store/chatStore";
import { useVisualizationStore } from "@/store/visualizationStore";
import { ForceGraph } from "./ForceGraph";

const ENTITY_TYPES = ["character", "npc", "location", "quest", "item"] as const;

const TYPE_COLORS: Record<string, string> = {
  character: "bg-blue-400",
  npc: "bg-purple-400",
  location: "bg-amber-400",
  quest: "bg-green-400",
  item: "bg-gray-400",
};

const TYPE_TEXT: Record<string, string> = {
  character: "text-blue-300",
  npc: "text-purple-300",
  location: "text-amber-300",
  quest: "text-green-300",
  item: "text-gray-300",
};

export function KnowledgeGraphModal() {
  const { activeConversationId } = useChatStore();
  const { graphNodes, graphEdges, graphLoading, loadGraph } = useVisualizationStore();
  const [typeFilter, setTypeFilter] = useState<Set<string>>(new Set());
  const [strengthThreshold, setStrengthThreshold] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 500 });

  useEffect(() => {
    if (activeConversationId) {
      loadGraph(activeConversationId);
    }
  }, [activeConversationId, loadGraph]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setDimensions({ width: Math.max(width, 200), height: Math.max(height, 200) });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const toggleType = (type: string) => {
    setTypeFilter((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  if (graphLoading) {
    return <div className="text-gray-500 text-center py-12">Loading graph...</div>;
  }

  if (graphNodes.length === 0) {
    return (
      <div className="text-center py-12 space-y-3">
        <div className="text-4xl opacity-30">{"\uD83D\uDD78\uFE0F"}</div>
        <div className="text-sm text-gray-400">No relationships yet</div>
        <div className="text-xs text-gray-600">
          Play the game to build the world graph — create NPCs, locations, and relationships
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Controls */}
      <div className="flex items-center gap-4 flex-wrap">
        {/* Entity type filter */}
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-gray-500 uppercase tracking-wider mr-1">Filter:</span>
          {ENTITY_TYPES.map((type) => {
            const active = typeFilter.size === 0 || typeFilter.has(type);
            return (
              <button
                key={type}
                onClick={() => toggleType(type)}
                className={`flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full border transition-colors ${
                  active
                    ? `bg-gray-800/80 ${TYPE_TEXT[type]} border-gray-600/40`
                    : "bg-gray-900/50 text-gray-600 border-gray-800/30"
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${TYPE_COLORS[type]} ${active ? "" : "opacity-30"}`} />
                {type}
              </button>
            );
          })}
        </div>

        {/* Strength threshold */}
        <div className="flex items-center gap-2 ml-auto">
          <span className="text-[10px] text-gray-500">Min Strength:</span>
          <input
            type="range"
            min={0}
            max={100}
            value={strengthThreshold}
            onChange={(e) => setStrengthThreshold(Number(e.target.value))}
            className="w-20 h-1 accent-amber-500"
          />
          <span className="text-[10px] text-gray-400 w-6 tabular-nums">{strengthThreshold}</span>
        </div>
      </div>

      {/* Graph */}
      <div
        ref={containerRef}
        className="bg-gray-950 rounded-lg border border-gray-800 overflow-hidden"
        style={{ height: "55vh", minHeight: 300 }}
      >
        <ForceGraph
          nodes={graphNodes}
          edges={graphEdges}
          width={dimensions.width}
          height={dimensions.height}
          typeFilter={typeFilter.size > 0 ? typeFilter : undefined}
          minStrength={strengthThreshold}
        />
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 justify-center">
        {ENTITY_TYPES.map((type) => (
          <div key={type} className="flex items-center gap-1.5">
            <span className={`w-2.5 h-2.5 rounded-full ${TYPE_COLORS[type]}`} />
            <span className="text-[10px] text-gray-400 capitalize">{type}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
