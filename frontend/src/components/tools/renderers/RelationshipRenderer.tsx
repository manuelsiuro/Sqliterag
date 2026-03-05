import type { ToolRendererProps } from "./toolRendererRegistry";

// -- Data shapes --

interface EntityRef {
  name: string;
  type: string;
}

interface RelationshipAdded {
  type: "relationship_added";
  source: EntityRef;
  target: EntityRef;
  relationship: string;
  strength: number;
  is_update: boolean;
  error?: string;
}

interface RelationshipEdge {
  source_name: string;
  source_type: string;
  target_name: string;
  target_type: string;
  relationship: string;
  strength: number;
  direction: "outgoing" | "incoming";
}

interface RelationshipGraph {
  type: "relationship_graph";
  entity: EntityRef;
  relationships: RelationshipEdge[];
  depth: number;
  count: number;
  error?: string;
}

// -- Constants --

const ENTITY_ICONS: Record<string, string> = {
  character: "\u2694\uFE0F",
  npc: "\uD83D\uDDE3\uFE0F",
  location: "\uD83D\uDCCD",
  quest: "\uD83D\uDCDC",
  item: "\uD83D\uDC8E",
};

const REL_CATEGORY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  social: { bg: "bg-purple-900/30", text: "text-purple-300", border: "border-purple-700/30" },
  spatial: { bg: "bg-amber-900/30", text: "text-amber-300", border: "border-amber-700/30" },
  quest: { bg: "bg-blue-900/30", text: "text-blue-300", border: "border-blue-700/30" },
  ownership: { bg: "bg-green-900/30", text: "text-green-300", border: "border-green-700/30" },
  knowledge: { bg: "bg-cyan-900/30", text: "text-cyan-300", border: "border-cyan-700/30" },
  default: { bg: "bg-gray-700/30", text: "text-gray-300", border: "border-gray-600/30" },
};

const REL_TO_CATEGORY: Record<string, string> = {
  knows_about: "knowledge", witnessed: "knowledge", suspects: "knowledge",
  allied_with: "social", enemy_of: "social", fears: "social", trusts: "social",
  friend_of: "social", rival_of: "social", respects: "social",
  located_at: "spatial", connected_to: "spatial", guards: "spatial", resides_in: "spatial",
  quest_giver: "quest", seeks: "quest", requires: "quest", assigned_to: "quest",
  owns: "ownership", carries: "ownership", crafted_by: "ownership",
};

function getRelColor(rel: string) {
  const cat = REL_TO_CATEGORY[rel] || "default";
  return REL_CATEGORY_COLORS[cat] || REL_CATEGORY_COLORS.default;
}

function entityIcon(type: string) {
  return ENTITY_ICONS[type] || "\u2B50";
}

function displayRel(rel: string) {
  return rel.replace(/_/g, " ");
}

// -- Strength bar --

function StrengthBar({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(100, value));
  const color =
    pct >= 75 ? "bg-green-500" : pct >= 40 ? "bg-yellow-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-1.5 min-w-[60px]">
      <div className="flex-1 h-1 bg-gray-700 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[10px] text-gray-500 w-6 text-right">{pct}</span>
    </div>
  );
}

// -- Sub-renderers --

function RelationshipAddedCard({ d }: { d: RelationshipAdded }) {
  if (d.error) {
    return <div className="mt-2 text-red-400 text-sm">{d.error}</div>;
  }

  const color = getRelColor(d.relationship);

  return (
    <div className="bg-gray-800/30 rounded-lg px-3 py-2.5 border border-gray-700/30 space-y-2">
      <div className="flex items-center gap-2 text-sm">
        <span className="text-gray-400 font-medium">
          {d.is_update ? "Updated" : "New"} Relationship
        </span>
        {d.is_update && (
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-900/30 text-amber-300 border border-amber-700/30">
            updated
          </span>
        )}
      </div>

      <div className="flex items-center gap-2 text-sm flex-wrap">
        <span className="font-medium text-gray-200">
          {entityIcon(d.source.type)} {d.source.name}
        </span>
        <span className={`px-2 py-0.5 rounded-full text-xs ${color.bg} ${color.text} border ${color.border}`}>
          {displayRel(d.relationship)}
        </span>
        <span className="text-gray-500">&rarr;</span>
        <span className="font-medium text-gray-200">
          {entityIcon(d.target.type)} {d.target.name}
        </span>
      </div>

      <StrengthBar value={d.strength} />
    </div>
  );
}

function RelationshipGraphCard({ d }: { d: RelationshipGraph }) {
  if (d.error) {
    return <div className="mt-2 text-red-400 text-sm">{d.error}</div>;
  }

  return (
    <div className="bg-gray-800/30 rounded-lg px-3 py-2.5 border border-gray-700/30 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm text-gray-400 font-medium">
          {entityIcon(d.entity.type)} {d.entity.name}
          <span className="text-gray-500 ml-1 text-xs">({d.entity.type})</span>
        </span>
        <span className="text-[10px] text-gray-500">
          {d.count} connection{d.count !== 1 ? "s" : ""}
          {d.depth > 1 ? ` (depth ${d.depth})` : ""}
        </span>
      </div>

      {d.relationships.length === 0 ? (
        <div className="text-xs text-gray-500 italic">No relationships found.</div>
      ) : (
        <div className="space-y-1">
          {d.relationships.map((edge, i) => {
            const color = getRelColor(edge.relationship);
            const isOutgoing = edge.direction === "outgoing";

            return (
              <div key={i} className="flex items-center gap-1.5 text-xs flex-wrap">
                {isOutgoing ? (
                  <>
                    <span className="text-gray-500">&rarr;</span>
                    <span className={`px-1.5 py-0.5 rounded-full ${color.bg} ${color.text} border ${color.border}`}>
                      {displayRel(edge.relationship)}
                    </span>
                    <span className="text-gray-300">
                      {entityIcon(edge.target_type)} {edge.target_name}
                    </span>
                  </>
                ) : (
                  <>
                    <span className="text-gray-500">&larr;</span>
                    <span className="text-gray-300">
                      {entityIcon(edge.source_type)} {edge.source_name}
                    </span>
                    <span className={`px-1.5 py-0.5 rounded-full ${color.bg} ${color.text} border ${color.border}`}>
                      {displayRel(edge.relationship)}
                    </span>
                  </>
                )}
                <StrengthBar value={edge.strength} />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// -- Main renderer --

export function RelationshipRenderer({ data }: ToolRendererProps) {
  const raw = data as RelationshipAdded | RelationshipGraph;

  if (raw.type === "relationship_added") {
    return <RelationshipAddedCard d={raw as RelationshipAdded} />;
  }

  return <RelationshipGraphCard d={raw as RelationshipGraph} />;
}
