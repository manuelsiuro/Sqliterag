import { useEffect, useState } from "react";
import { useToolStore } from "@/store/toolStore";
import { useChatStore } from "@/store/chatStore";
import { ToolList } from "./ToolList";
import { ToolForm } from "./ToolForm";
import type { ToolCreate, ToolDefinition } from "@/types";

interface ToolsPanelProps {
  onClose: () => void;
}

export function ToolsPanel({ onClose }: ToolsPanelProps) {
  const { tools, loadTools, createTool, updateTool, loadConversationTools } = useToolStore();
  const { activeConversationId } = useChatStore();
  const [showForm, setShowForm] = useState(false);
  const [editingTool, setEditingTool] = useState<ToolDefinition | undefined>();

  useEffect(() => {
    loadTools();
  }, [loadTools]);

  useEffect(() => {
    if (activeConversationId) {
      loadConversationTools(activeConversationId);
    }
  }, [activeConversationId, loadConversationTools]);

  const handleSave = async (data: ToolCreate) => {
    if (editingTool) {
      await updateTool(editingTool.id, data);
    } else {
      await createTool(data);
    }
    setShowForm(false);
    setEditingTool(undefined);
  };

  const handleEdit = (tool: ToolDefinition) => {
    setEditingTool(tool);
    setShowForm(true);
  };

  const handleCancel = () => {
    setShowForm(false);
    setEditingTool(undefined);
  };

  return (
    <div className="w-80 bg-gray-900 border-l border-gray-800 flex flex-col h-full">
      <div className="flex items-center justify-between p-4 border-b border-gray-800">
        <h2 className="text-lg font-semibold text-white">Tools</h2>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-white text-xl"
        >
          &times;
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {showForm ? (
          <ToolForm
            tool={editingTool}
            onSave={handleSave}
            onCancel={handleCancel}
          />
        ) : (
          <>
            <button
              onClick={() => {
                setEditingTool(undefined);
                setShowForm(true);
              }}
              className="w-full px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition-colors"
            >
              + New Tool
            </button>
            <ToolList tools={tools} onEdit={handleEdit} />
          </>
        )}
      </div>
    </div>
  );
}
