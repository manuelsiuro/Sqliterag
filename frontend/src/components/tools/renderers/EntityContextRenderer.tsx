import type { ToolRendererProps } from "./toolRendererRegistry";

// -- Data shapes --

interface EntityRef {
  name: string;
  type: string;
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

interface MemoryEntry {
  content: string;
  memory_type: string;
  importance: number;
  entities: string[];
  created_at: string | null;
}

interface EntityContextData {
  type: "entity_context";
  entity: EntityRef;
  details: Record<string, unknown>;
  relationships: RelationshipEdge[];
  relationship_count: number;
  memories: MemoryEntry[];
  memory_count: number;
  summary: string;
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

const ENTITY_TYPE_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  character: { bg: "bg-blue-900/30", text: "text-blue-300", border: "border-blue-700/30" },
  npc: { bg: "bg-purple-900/30", text: "text-purple-300", border: "border-purple-700/30" },
  location: { bg: "bg-amber-900/30", text: "text-amber-300", border: "border-amber-700/30" },
  quest: { bg: "bg-emerald-900/30", text: "text-emerald-300", border: "border-emerald-700/30" },
  item: { bg: "bg-gray-700/30", text: "text-gray-300", border: "border-gray-600/30" },
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

const MEMORY_TYPE_COLORS: Record<string, string> = {
  episodic: "bg-blue-900/40 text-blue-300 border-blue-700/40",
  semantic: "bg-purple-900/40 text-purple-300 border-purple-700/40",
  procedural: "bg-amber-900/40 text-amber-300 border-amber-700/40",
};

// -- Helpers --

function entityIcon(type: string) {
  return ENTITY_ICONS[type] || "\u2B50";
}

function getRelColor(rel: string) {
  const cat = REL_TO_CATEGORY[rel] || "default";
  return REL_CATEGORY_COLORS[cat] || REL_CATEGORY_COLORS.default;
}

function displayRel(rel: string) {
  return rel.replace(/_/g, " ");
}

function getTypeColor(type: string) {
  return ENTITY_TYPE_COLORS[type] || ENTITY_TYPE_COLORS.item;
}

function getMemTypeStyle(memoryType: string): string {
  return MEMORY_TYPE_COLORS[memoryType] || "bg-gray-700/40 text-gray-300 border-gray-600/40";
}

// -- Sub-components --

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

function CharacterDetails({ details }: { details: Record<string, unknown> }) {
  const abilities = details.abilities as Record<string, number> | undefined;
  const conditions = details.conditions as string[] | undefined;
  return (
    <div className="space-y-1">
      <div className="flex flex-wrap gap-2 text-xs">
        {details.race && <span className="text-gray-400">{String(details.race)}</span>}
        {details.class && <span className="text-blue-300 font-medium">{String(details.class)}</span>}
        {details.level && <span className="text-gray-400">Lv.{String(details.level)}</span>}
      </div>
      <div className="flex flex-wrap gap-3 text-xs">
        {details.hp && (
          <span className="text-red-300">HP {String(details.hp)}</span>
        )}
        {details.ac && (
          <span className="text-blue-300">AC {String(details.ac)}</span>
        )}
      </div>
      {abilities && (
        <div className="flex flex-wrap gap-2 text-[10px] text-gray-400">
          {Object.entries(abilities).map(([k, v]) => (
            <span key={k}>{k.slice(0, 3).toUpperCase()} {v}</span>
          ))}
        </div>
      )}
      {conditions && conditions.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {conditions.map((c, i) => (
            <span key={i} className="text-[10px] px-1.5 py-0.5 rounded bg-red-900/30 text-red-300 border border-red-700/30">
              {c}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function NPCDetails({ details }: { details: Record<string, unknown> }) {
  return (
    <div className="space-y-1">
      {details.description && (
        <p className="text-xs text-gray-300">{String(details.description)}</p>
      )}
      <div className="flex flex-wrap gap-2 text-xs">
        {details.disposition && (
          <span className="px-1.5 py-0.5 rounded bg-purple-900/30 text-purple-300 border border-purple-700/30">
            {String(details.disposition)}
          </span>
        )}
        {details.familiarity && (
          <span className="px-1.5 py-0.5 rounded bg-gray-700/40 text-gray-300 border border-gray-600/30">
            {String(details.familiarity)}
          </span>
        )}
        {details.location && (
          <span className="text-gray-400">at {String(details.location)}</span>
        )}
      </div>
      {Array.isArray(details.memory) && details.memory.length > 0 && (
        <div className="text-[10px] text-gray-500">
          NPC memories: {(details.memory as string[]).slice(0, 3).join("; ")}
        </div>
      )}
    </div>
  );
}

function LocationDetails({ details }: { details: Record<string, unknown> }) {
  const exits = details.exits as Record<string, string> | undefined;
  const env = details.environment as Record<string, string> | undefined;
  return (
    <div className="space-y-1">
      {details.description && (
        <p className="text-xs text-gray-300">{String(details.description)}</p>
      )}
      <div className="flex flex-wrap gap-2 text-xs">
        {details.biome && (
          <span className="px-1.5 py-0.5 rounded bg-amber-900/30 text-amber-300 border border-amber-700/30">
            {String(details.biome)}
          </span>
        )}
        {env && Object.values(env).some(Boolean) && (
          <span className="text-gray-400">
            {Object.values(env).filter(Boolean).join(", ")}
          </span>
        )}
      </div>
      {exits && Object.keys(exits).length > 0 && (
        <div className="flex flex-wrap gap-1">
          {Object.entries(exits).map(([dir, dest]) => (
            <span key={dir} className="rounded-full overflow-hidden text-[10px] inline-flex">
              <span className="bg-amber-900/30 text-amber-300 border-r border-amber-700/30 px-1.5 py-0.5">
                {dir}
              </span>
              <span className="bg-gray-700/30 text-gray-300 px-1.5 py-0.5">{dest}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function QuestDetails({ details }: { details: Record<string, unknown> }) {
  const objectives = details.objectives as Array<{ text: string; completed: boolean }> | undefined;
  const rewards = details.rewards as Record<string, number> | undefined;
  const statusColors: Record<string, string> = {
    active: "bg-emerald-900/30 text-emerald-300 border-emerald-700/30",
    completed: "bg-blue-900/30 text-blue-300 border-blue-700/30",
    failed: "bg-red-900/30 text-red-300 border-red-700/30",
  };
  return (
    <div className="space-y-1">
      {details.description && (
        <p className="text-xs text-gray-300">{String(details.description)}</p>
      )}
      {details.status && (
        <span className={`text-xs px-1.5 py-0.5 rounded border ${statusColors[String(details.status)] || statusColors.active}`}>
          {String(details.status)}
        </span>
      )}
      {objectives && objectives.length > 0 && (
        <div className="space-y-0.5">
          {objectives.map((obj, i) => (
            <div key={i} className="text-xs text-gray-400 flex items-center gap-1">
              <span>{obj.completed ? "\u2705" : "\u25CB"}</span>
              <span className={obj.completed ? "line-through text-gray-500" : ""}>{obj.text}</span>
            </div>
          ))}
        </div>
      )}
      {rewards && Object.keys(rewards).length > 0 && (
        <div className="text-[10px] text-gray-500">
          Rewards: {Object.entries(rewards).map(([k, v]) => `${v} ${k}`).join(", ")}
        </div>
      )}
    </div>
  );
}

function ItemDetails({ details }: { details: Record<string, unknown> }) {
  const RARITY_COLORS: Record<string, string> = {
    common: "text-gray-400",
    uncommon: "text-green-400",
    rare: "text-blue-400",
    very_rare: "text-purple-400",
    legendary: "text-amber-400",
  };
  return (
    <div className="space-y-1">
      {details.description && (
        <p className="text-xs text-gray-300">{String(details.description)}</p>
      )}
      <div className="flex flex-wrap gap-2 text-xs">
        {details.item_type && (
          <span className="text-gray-400">{String(details.item_type)}</span>
        )}
        {details.rarity && (
          <span className={`font-medium ${RARITY_COLORS[String(details.rarity)] || "text-gray-400"}`}>
            {String(details.rarity).replace(/_/g, " ")}
          </span>
        )}
        {(details.weight as number) > 0 && (
          <span className="text-gray-500">{String(details.weight)} lb</span>
        )}
        {(details.value_gp as number) > 0 && (
          <span className="text-yellow-400">{String(details.value_gp)} gp</span>
        )}
      </div>
    </div>
  );
}

function DetailsSection({ entityType, details }: { entityType: string; details: Record<string, unknown> }) {
  if (!details || Object.keys(details).length === 0) return null;

  switch (entityType) {
    case "character": return <CharacterDetails details={details} />;
    case "npc": return <NPCDetails details={details} />;
    case "location": return <LocationDetails details={details} />;
    case "quest": return <QuestDetails details={details} />;
    case "item": return <ItemDetails details={details} />;
    default: return null;
  }
}

// -- Main renderer --

export function EntityContextRenderer({ data }: ToolRendererProps) {
  const d = data as EntityContextData;

  if (d.error) {
    return <div className="mt-2 text-red-400 text-sm">{d.error}</div>;
  }

  const typeColor = getTypeColor(d.entity.type);

  return (
    <div className="bg-gray-800/30 rounded-lg px-3 py-2.5 border border-gray-700/30 space-y-2">
      {/* Header */}
      <div className="flex items-center gap-2">
        <span className="text-base">{entityIcon(d.entity.type)}</span>
        <span className="text-sm font-medium text-gray-200">{d.entity.name}</span>
        <span className={`text-[10px] px-1.5 py-0.5 rounded border ${typeColor.bg} ${typeColor.text} ${typeColor.border}`}>
          {d.entity.type}
        </span>
      </div>

      {/* Details */}
      <DetailsSection entityType={d.entity.type} details={d.details} />

      {/* Relationships */}
      {d.relationships.length > 0 && (
        <div className="space-y-1">
          <div className="text-xs text-gray-500 font-medium">
            Connections ({d.relationship_count})
          </div>
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

      {/* Memories */}
      {d.memories.length > 0 && (
        <div className="space-y-1">
          <div className="text-xs text-gray-500 font-medium">
            Memories ({d.memory_count})
          </div>
          {d.memories.map((mem, i) => (
            <div key={i} className="bg-gray-800/20 rounded px-2 py-1.5 border border-gray-700/20 space-y-0.5">
              <div className="flex items-center gap-1.5">
                <span className={`text-[10px] px-1 py-0.5 rounded border ${getMemTypeStyle(mem.memory_type)}`}>
                  {mem.memory_type}
                </span>
                <ImportanceDot importance={mem.importance} />
                {mem.created_at && (
                  <span className="text-[10px] text-gray-500">
                    {new Date(mem.created_at).toLocaleDateString()}
                  </span>
                )}
              </div>
              <p className="text-xs text-gray-300">{mem.content}</p>
            </div>
          ))}
        </div>
      )}

      {/* Summary */}
      {d.summary && (
        <p className="text-[10px] text-gray-500 italic">{d.summary}</p>
      )}
    </div>
  );
}
