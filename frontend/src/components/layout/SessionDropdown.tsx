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
  const containerRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const editRef = useRef<HTMLInputElement>(null);

  // Auto-focus search on mount
  useEffect(() => {
    searchRef.current?.focus();
  }, []);

  // Focus rename input
  useEffect(() => {
    if (editingId) editRef.current?.focus();
  }, [editingId]);

  // Close on outside click
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
      <ul className="max-h-72 overflow-y-auto">
        {conversations.length === 0 ? (
          <li className="px-4 py-6 text-sm text-gray-500 text-center">No sessions yet</li>
        ) : filtered.length === 0 ? (
          <li className="px-4 py-6 text-sm text-gray-500 text-center">No matches</li>
        ) : (
          filtered.map((conv) => (
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
                  <span className="flex-1 truncate">{conv.title}</span>
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
          ))
        )}
      </ul>
    </div>
  );
}
