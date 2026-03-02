import type { ToolDefinition } from "@/types";
import { useToolStore } from "@/store/toolStore";
import { useChatStore } from "@/store/chatStore";

interface ToolListProps {
  tools: ToolDefinition[];
  onEdit: (tool: ToolDefinition) => void;
}

export function ToolList({ tools, onEdit }: ToolListProps) {
  const { deleteTool, updateTool, conversationToolIds, toggleConversationTool } = useToolStore();
  const { activeConversationId } = useChatStore();

  if (tools.length === 0) {
    return (
      <p className="text-sm text-gray-500 text-center py-4">
        No tools defined yet. Create one to get started.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {tools.map((tool) => {
        const isConvEnabled = conversationToolIds.includes(tool.id);
        return (
          <div
            key={tool.id}
            className="p-3 bg-gray-800/60 rounded-lg border border-gray-700"
          >
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
                {/* Global enable/disable */}
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
      })}
    </div>
  );
}
