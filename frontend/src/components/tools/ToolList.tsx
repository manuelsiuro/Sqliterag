import type { ToolDefinition } from "@/types";
import { useToolStore } from "@/store/toolStore";
import { useChatStore } from "@/store/chatStore";
import type { ToolGroup } from "./toolCategories";

interface ToolListProps {
  groups: ToolGroup[];
  collapsedGroups: Record<string, boolean>;
  onToggleGroup: (key: string) => void;
  onEdit: (tool: ToolDefinition) => void;
  isSearchActive: boolean;
  hasConversation: boolean;
  conversationToolIds: string[];
  onToggleGroupEnabled: (categoryKey: string, enable: boolean) => void;
}

function ToolCard({
  tool,
  onEdit,
}: {
  tool: ToolDefinition;
  onEdit: (tool: ToolDefinition) => void;
}) {
  const { deleteTool, updateTool, conversationToolIds, toggleConversationTool } =
    useToolStore();
  const { activeConversationId } = useChatStore();
  const isConvEnabled = conversationToolIds.includes(tool.id);

  return (
    <div className="p-3 bg-gray-800/60 rounded-lg border border-gray-700">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-white truncate">
              {tool.name}
            </span>
            <span
              className={`px-1.5 py-0.5 text-[10px] rounded font-medium ${
                tool.execution_type === "http"
                  ? "bg-blue-900/50 text-blue-300"
                  : tool.execution_type === "builtin"
                    ? "bg-purple-900/50 text-purple-300"
                    : "bg-gray-700 text-gray-400"
              }`}
            >
              {tool.execution_type}
            </span>
          </div>
          <p className="text-xs text-gray-400 mt-0.5 line-clamp-2">
            {tool.description}
          </p>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <button
            onClick={() => updateTool(tool.id, { is_enabled: !tool.is_enabled })}
            title={tool.is_enabled ? "Disable globally" : "Enable globally"}
            className={`w-8 h-5 rounded-full relative transition-colors ${
              tool.is_enabled ? "bg-green-600" : "bg-gray-600"
            }`}
          >
            <span
              className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                tool.is_enabled ? "left-3.5" : "left-0.5"
              }`}
            />
          </button>
        </div>
      </div>

      <div className="flex items-center gap-2 mt-2">
        {activeConversationId && (
          <button
            onClick={() => toggleConversationTool(activeConversationId, tool.id)}
            className={`text-xs px-2 py-1 rounded transition-colors ${
              isConvEnabled
                ? "bg-blue-600/30 text-blue-300 border border-blue-500/50"
                : "bg-gray-700/50 text-gray-400 border border-gray-600/50 hover:text-gray-300"
            }`}
          >
            {isConvEnabled ? "Enabled for chat" : "Enable for chat"}
          </button>
        )}
        <div className="flex-1" />
        <button
          onClick={() => onEdit(tool)}
          className="text-xs text-gray-400 hover:text-white transition-colors"
        >
          Edit
        </button>
        <button
          onClick={() => deleteTool(tool.id)}
          className="text-xs text-red-400 hover:text-red-300 transition-colors"
        >
          Delete
        </button>
      </div>
    </div>
  );
}

export function ToolList({
  groups,
  collapsedGroups,
  onToggleGroup,
  onEdit,
  isSearchActive,
  hasConversation,
  conversationToolIds,
  onToggleGroupEnabled,
}: ToolListProps) {
  return (
    <div className="space-y-2">
      {groups.map(({ category, tools }) => {
        const isCollapsed = isSearchActive ? false : !!collapsedGroups[category.key];
        const enabledCount = hasConversation
          ? tools.filter((t) => conversationToolIds.includes(t.id)).length
          : 0;
        const allEnabled = enabledCount === tools.length;
        const someEnabled = enabledCount > 0 && !allEnabled;

        return (
          <div key={category.key}>
            {/* Group header */}
            <button
              onClick={() => onToggleGroup(category.key)}
              className="w-full flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-gray-800/60 transition-colors group"
            >
              <span className="text-[10px] text-gray-500 group-hover:text-gray-400 transition-colors w-3">
                {isCollapsed ? "\u25B6" : "\u25BC"}
              </span>
              <span className="text-sm">{category.emoji}</span>
              <span className="text-sm font-medium text-gray-300 group-hover:text-white transition-colors">
                {category.label}
              </span>
              <span className="text-[10px] text-gray-600 bg-gray-800 px-1.5 py-0.5 rounded-full">
                {tools.length}
              </span>
              {hasConversation && (
                <span
                  role="checkbox"
                  aria-checked={allEnabled ? "true" : someEnabled ? "mixed" : "false"}
                  title={allEnabled ? "Disable all in group" : "Enable all in group"}
                  onClick={(e) => {
                    e.stopPropagation();
                    onToggleGroupEnabled(category.key, !allEnabled);
                  }}
                  className={`ml-auto w-4 h-4 rounded border flex items-center justify-center text-[10px] cursor-pointer transition-colors shrink-0 ${
                    allEnabled
                      ? "bg-blue-600 border-blue-500 text-white"
                      : someEnabled
                        ? "bg-blue-600/40 border-blue-500/60 text-white/80"
                        : "bg-gray-700 border-gray-600 text-transparent hover:border-gray-500"
                  }`}
                >
                  {allEnabled ? "\u2713" : someEnabled ? "\u2012" : ""}
                </span>
              )}
            </button>

            {/* Tools in group */}
            {!isCollapsed && (
              <div className="pl-5 mt-1 space-y-2">
                {tools.map((tool) => (
                  <ToolCard key={tool.id} tool={tool} onEdit={onEdit} />
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
