import { useEffect, useMemo, useState } from "react";
import { useToolStore } from "@/store/toolStore";
import { useChatStore } from "@/store/chatStore";
import { useSettingsStore } from "@/store/settingsStore";
import { ToolList } from "./ToolList";
import { ToolForm } from "./ToolForm";
import {
  TOOL_CATEGORIES,
  getCategoryKey,
  getCategory,
  getToolIdsByCategory,
  estimateTotalToolTokens,
  type ToolGroup,
} from "./toolCategories";
import type { ToolCreate, ToolDefinition } from "@/types";

type FilterMode = "all" | "active" | "inactive";

export function ToolsPanel() {
  const {
    tools, loadTools, createTool, updateTool,
    loadConversationTools, conversationToolIds,
    setConversationToolsBatch, toggleConversationToolGroup,
  } = useToolStore();
  const { activeConversationId, conversations } = useChatStore();
  const { selectedModelDetail, loadModelDetail, modelParameters, isLoadingModelDetail } =
    useSettingsStore();
  const [showForm, setShowForm] = useState(false);
  const [editingTool, setEditingTool] = useState<ToolDefinition | undefined>();
  const [searchQuery, setSearchQuery] = useState("");
  const [filterMode, setFilterMode] = useState<FilterMode>("all");
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});

  useEffect(() => {
    loadTools();
  }, [loadTools]);

  useEffect(() => {
    if (activeConversationId) {
      loadConversationTools(activeConversationId);
    }
  }, [activeConversationId, loadConversationTools]);

  // Load model detail for context indicator
  const modelName = conversations.find((c) => c.id === activeConversationId)?.model;
  useEffect(() => {
    if (modelName) loadModelDetail(modelName);
  }, [modelName, loadModelDetail]);

  const isSearchActive = searchQuery.trim().length > 0;
  const hasConversation = !!activeConversationId;

  const groups = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();

    // Filter tools
    const filtered = tools.filter((tool) => {
      // Search filter
      if (query) {
        const matchesName = tool.name.toLowerCase().includes(query);
        const matchesDesc = tool.description.toLowerCase().includes(query);
        if (!matchesName && !matchesDesc) return false;
      }

      // Status filter
      if (filterMode === "active" && hasConversation) {
        if (!conversationToolIds.includes(tool.id)) return false;
      } else if (filterMode === "inactive" && hasConversation) {
        if (conversationToolIds.includes(tool.id)) return false;
      }

      return true;
    });

    // Bucket into categories
    const buckets = new Map<string, ToolDefinition[]>();
    for (const tool of filtered) {
      const key = getCategoryKey(tool);
      if (!buckets.has(key)) buckets.set(key, []);
      buckets.get(key)!.push(tool);
    }

    // Build ordered groups (skip empty)
    const result: ToolGroup[] = [];
    for (const cat of TOOL_CATEGORIES) {
      const catTools = buckets.get(cat.key);
      if (catTools && catTools.length > 0) {
        result.push({ category: getCategory(cat.key), tools: catTools });
      }
    }

    return result;
  }, [tools, searchQuery, filterMode, conversationToolIds, hasConversation]);

  const totalFiltered = groups.reduce((sum, g) => sum + g.tools.length, 0);

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

  const handleToggleGroup = (key: string) => {
    setCollapsedGroups((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleToggleGroupEnabled = (categoryKey: string, enable: boolean) => {
    if (!activeConversationId) return;
    const groupIds = getToolIdsByCategory(tools, categoryKey);
    toggleConversationToolGroup(activeConversationId, groupIds, enable);
  };

  const handleEnableAll = () => {
    if (!activeConversationId) return;
    setConversationToolsBatch(activeConversationId, tools.map((t) => t.id));
  };

  const handleDisableAll = () => {
    if (!activeConversationId) return;
    setConversationToolsBatch(activeConversationId, []);
  };

  // Context indicator computations
  const enabledTools = tools.filter((t) => conversationToolIds.includes(t.id));
  const estimatedTokens = estimateTotalToolTokens(enabledTools);
  const contextLength = modelParameters.num_ctx ?? selectedModelDetail?.context_length ?? null;
  const pct = contextLength ? Math.round((estimatedTokens / contextLength) * 100) : null;

  const filterTabs: { mode: FilterMode; label: string }[] = [
    { mode: "all", label: "All" },
    { mode: "active", label: "Active" },
    { mode: "inactive", label: "Inactive" },
  ];

  if (showForm) {
    return (
      <div className="space-y-4">
        <ToolForm
          tool={editingTool}
          onSave={handleSave}
          onCancel={handleCancel}
        />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="space-y-3">
        <button
          onClick={() => {
            setEditingTool(undefined);
            setShowForm(true);
          }}
          className="w-full px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition-colors"
        >
          + New Tool
        </button>

        {/* Search */}
        <div className="relative">
          <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500 text-sm">
            {"\u{1F50D}"}
          </span>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search tools..."
            className="w-full pl-8 pr-3 py-1.5 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-gray-600"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery("")}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 text-xs"
            >
              &times;
            </button>
          )}
        </div>

        {/* Filter tabs */}
        <div className="flex gap-1">
          {filterTabs.map(({ mode, label }) => {
            const disabled = mode !== "all" && !hasConversation;
            return (
              <button
                key={mode}
                onClick={() => !disabled && setFilterMode(mode)}
                disabled={disabled}
                className={`flex-1 px-2 py-1 text-xs rounded-md transition-colors ${
                  filterMode === mode
                    ? "bg-blue-600/30 text-blue-300 border border-blue-500/50"
                    : disabled
                      ? "bg-gray-800/30 text-gray-600 border border-gray-700/30 cursor-not-allowed"
                      : "bg-gray-800 text-gray-400 border border-gray-700 hover:text-gray-300"
                }`}
              >
                {label}
              </button>
            );
          })}
        </div>

        {/* Enable All / Disable All */}
        {hasConversation && (
          <div className="flex gap-2">
            <button
              onClick={handleEnableAll}
              className="flex-1 px-2 py-1 text-xs rounded-md bg-green-900/30 text-green-400 border border-green-700/40 hover:bg-green-900/50 transition-colors"
            >
              Enable All
            </button>
            <button
              onClick={handleDisableAll}
              className="flex-1 px-2 py-1 text-xs rounded-md bg-red-900/30 text-red-400 border border-red-700/40 hover:bg-red-900/50 transition-colors"
            >
              Disable All
            </button>
          </div>
        )}
      </div>

      {/* Tool list */}
      {totalFiltered === 0 ? (
        <p className="text-sm text-gray-500 text-center py-4">
          {tools.length === 0
            ? "No tools defined yet."
            : "No tools match your filters."}
        </p>
      ) : (
        <ToolList
          groups={groups}
          collapsedGroups={collapsedGroups}
          onToggleGroup={handleToggleGroup}
          onEdit={handleEdit}
          isSearchActive={isSearchActive}
          hasConversation={hasConversation}
          conversationToolIds={conversationToolIds}
          onToggleGroupEnabled={handleToggleGroupEnabled}
        />
      )}

      {/* Context indicator footer */}
      <div className="border-t border-gray-800 pt-3 space-y-1.5">
        {!hasConversation ? (
          <p className="text-[11px] text-gray-500 text-center">
            Select a conversation to manage tools
          </p>
        ) : isLoadingModelDetail ? (
          <p className="text-[11px] text-gray-500 text-center animate-pulse">
            Loading model info...
          </p>
        ) : contextLength == null ? (
          <p className="text-[11px] text-gray-500 text-center">
            Context info unavailable{modelName ? ` for ${modelName}` : ""}
          </p>
        ) : (
          <>
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-gray-400">Tool context usage</span>
              <span className="text-gray-500">
                ~{estimatedTokens >= 1000 ? `${(estimatedTokens / 1000).toFixed(1)}k` : estimatedTokens}
                {" / "}
                {contextLength >= 1000 ? `${(contextLength / 1000).toFixed(0)}k` : contextLength}
                {" tokens"}
              </span>
            </div>
            <div className="w-full h-1.5 bg-gray-800 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${
                  pct! > 50
                    ? "bg-red-500"
                    : pct! > 30
                      ? "bg-yellow-500"
                      : "bg-green-500"
                }`}
                style={{ width: `${Math.min(pct!, 100)}%` }}
              />
            </div>
            {pct! >= 50 && (
              <p className="text-[10px] text-yellow-400">
                Tools consume {pct}% of context. Consider disabling some.
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}
