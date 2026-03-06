import { useState, useRef, useEffect } from "react";
import { useChatStore } from "@/store/chatStore";
import { useUIStore } from "@/store/uiStore";
import type { Conversation } from "@/types";

export function SessionDropdown() {
  const {
    conversations,
    activeConversationId,
    selectConversation,
    deleteConversation,
    updateConversationTitle,
  } = useChatStore();
  const { setSessionDropdownOpen } = useUIStore();

  const [search, setSearch] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [collapsedCampaigns, setCollapsedCampaigns] = useState<Set<string>>(new Set());
  const containerRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const editRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    searchRef.current?.focus();
  }, []);

  useEffect(() => {
    if (editingId) editRef.current?.focus();
  }, [editingId]);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setSessionDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [setSessionDropdownOpen]);

  const filtered = conversations.filter((c) =>
    c.title.toLowerCase().includes(search.trim().toLowerCase()),
  );

  // Group by campaign
  const campaignGroups = new Map<string, { name: string; convs: Conversation[] }>();
  const standalone: Conversation[] = [];

  for (const conv of filtered) {
    if (conv.campaign_id && conv.campaign_name) {
      const group = campaignGroups.get(conv.campaign_id);
      if (group) {
        group.convs.push(conv);
      } else {
        campaignGroups.set(conv.campaign_id, { name: conv.campaign_name, convs: [conv] });
      }
    } else {
      standalone.push(conv);
    }
  }

  // Sort campaign sessions by session number
  for (const group of campaignGroups.values()) {
    group.convs.sort((a, b) => (a.session_number ?? 0) - (b.session_number ?? 0));
  }

  const handleSelect = (id: string) => {
    selectConversation(id);
    setSessionDropdownOpen(false);
  };

  const startEditing = (conv: Conversation) => {
    setEditingId(conv.id);
    setEditValue(conv.title);
  };

  const commitEdit = () => {
    if (!editingId) return;
    const trimmed = editValue.trim();
    if (trimmed) updateConversationTitle(editingId, trimmed.slice(0, 100));
    setEditingId(null);
  };

  const toggleCampaign = (campaignId: string) => {
    setCollapsedCampaigns((prev) => {
      const next = new Set(prev);
      if (next.has(campaignId)) next.delete(campaignId);
      else next.add(campaignId);
      return next;
    });
  };

  const renderConvItem = (conv: Conversation, showSessionBadge = false) => (
    <li
      key={conv.id}
      className={`group flex items-center gap-2 px-3 py-2 cursor-pointer text-sm transition-colors ${
        activeConversationId === conv.id
          ? "bg-gray-700 text-white"
          : "text-gray-300 hover:bg-gray-800"
      }`}
      onClick={() => {
        if (editingId === conv.id) return;
        handleSelect(conv.id);
      }}
    >
      {editingId === conv.id ? (
        <input
          ref={editRef}
          className="flex-1 bg-gray-800 text-white text-sm px-1 py-0 rounded border border-gray-600 outline-none focus:border-blue-500"
          value={editValue}
          maxLength={100}
          onChange={(e) => setEditValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") { e.preventDefault(); commitEdit(); }
            else if (e.key === "Escape") { e.preventDefault(); setEditingId(null); }
          }}
          onBlur={commitEdit}
          onClick={(e) => e.stopPropagation()}
        />
      ) : (
        <>
          {showSessionBadge && conv.session_number != null && (
            <span className="text-[9px] px-1.5 py-px rounded-full bg-amber-900/40 text-amber-300 border border-amber-700/30 font-medium shrink-0">
              #{conv.session_number}
            </span>
          )}
          <span className="flex-1 truncate">{conv.title}</span>
          {conv.session_status === "ended" && (
            <span className="text-[9px] px-1.5 py-px rounded-full bg-gray-800 text-gray-500 border border-gray-700/30 shrink-0">
              ended
            </span>
          )}
          <button
            className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-blue-400 transition-opacity"
            onClick={(e) => { e.stopPropagation(); startEditing(conv); }}
            title="Rename"
          >
            &#x270E;
          </button>
          <button
            className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 transition-opacity"
            onClick={(e) => { e.stopPropagation(); deleteConversation(conv.id); }}
            title="Delete"
          >
            &times;
          </button>
        </>
      )}
    </li>
  );

  return (
    <div
      ref={containerRef}
      className="absolute top-full left-0 mt-1 w-80 bg-gray-900 border border-gray-700 rounded-lg shadow-2xl z-50 overflow-hidden"
    >
      {/* Search */}
      <div className="p-2 border-b border-gray-800">
        <input
          ref={searchRef}
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search sessions..."
          className="w-full px-3 py-1.5 bg-gray-800 border border-gray-700 rounded text-sm text-white placeholder-gray-500 focus:outline-none focus:border-gray-600"
        />
      </div>

      {/* List */}
      <ul className="max-h-80 overflow-y-auto">
        {conversations.length === 0 ? (
          <li className="px-4 py-6 text-sm text-gray-500 text-center">No sessions yet</li>
        ) : filtered.length === 0 ? (
          <li className="px-4 py-6 text-sm text-gray-500 text-center">No matches</li>
        ) : (
          <>
            {/* Campaign groups */}
            {Array.from(campaignGroups.entries()).map(([campId, { name, convs }]) => {
              const isCollapsed = collapsedCampaigns.has(campId);
              return (
                <li key={campId}>
                  <button
                    className="flex items-center gap-2 w-full px-3 py-1.5 text-left bg-amber-950/30 border-b border-amber-900/20 hover:bg-amber-950/50 transition-colors"
                    onClick={() => toggleCampaign(campId)}
                  >
                    <span
                      className="text-[10px] text-amber-500 transition-transform duration-150"
                      style={{ transform: isCollapsed ? "rotate(0deg)" : "rotate(90deg)" }}
                    >
                      {"\u25B6"}
                    </span>
                    <span className="text-xs font-medium text-amber-300 flex-1 truncate">
                      {name}
                    </span>
                    <span className="text-[10px] text-amber-500/60">
                      {convs.length} session{convs.length !== 1 ? "s" : ""}
                    </span>
                  </button>
                  {!isCollapsed && (
                    <ul className="bg-gray-900/50">
                      {convs.map((c) => renderConvItem(c, true))}
                    </ul>
                  )}
                </li>
              );
            })}

            {/* Standalone conversations */}
            {standalone.length > 0 && campaignGroups.size > 0 && (
              <li className="px-3 py-1 text-[10px] text-gray-600 uppercase tracking-wider border-t border-gray-800">
                Standalone
              </li>
            )}
            {standalone.map((c) => renderConvItem(c))}
          </>
        )}
      </ul>
    </div>
  );
}
