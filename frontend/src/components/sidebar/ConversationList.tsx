import { useState, useRef, useEffect } from "react";
import type { Conversation } from "@/types";

interface ConversationListProps {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
  onRename: (id: string, title: string) => void;
}

export function ConversationList({ conversations, activeId, onSelect, onDelete, onRename }: ConversationListProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingId && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [editingId]);

  const startEditing = (conv: Conversation) => {
    setEditingId(conv.id);
    setEditValue(conv.title);
  };

  const commitEdit = () => {
    if (!editingId) return;
    const trimmed = editValue.trim();
    if (trimmed) {
      onRename(editingId, trimmed.slice(0, 100));
    }
    setEditingId(null);
  };

  const cancelEdit = () => {
    setEditingId(null);
  };

  if (conversations.length === 0) {
    return <p className="px-3 py-2 text-sm text-gray-500">No conversations yet</p>;
  }

  return (
    <ul className="space-y-1">
      {conversations.map((conv) => (
        <li
          key={conv.id}
          className={`group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer text-sm transition-colors ${
            activeId === conv.id ? "bg-gray-700 text-white" : "text-gray-300 hover:bg-gray-800"
          }`}
          onClick={() => {
            if (editingId === conv.id) return;
            onSelect(conv.id);
          }}
          onDoubleClick={() => startEditing(conv)}
        >
          {editingId === conv.id ? (
            <input
              ref={inputRef}
              className="flex-1 bg-gray-800 text-white text-sm px-1 py-0 rounded border border-gray-600 outline-none focus:border-blue-500"
              value={editValue}
              maxLength={100}
              onChange={(e) => setEditValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  commitEdit();
                } else if (e.key === "Escape") {
                  e.preventDefault();
                  cancelEdit();
                }
              }}
              onBlur={commitEdit}
              onClick={(e) => e.stopPropagation()}
            />
          ) : (
            <>
              <span className="flex-1 truncate">{conv.title}</span>
              <button
                className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-blue-400 transition-opacity"
                onClick={(e) => {
                  e.stopPropagation();
                  startEditing(conv);
                }}
                title="Rename"
              >
                ✎
              </button>
              <button
                className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 transition-opacity"
                onClick={(e) => {
                  e.stopPropagation();
                  onDelete(conv.id);
                }}
              >
                &times;
              </button>
            </>
          )}
        </li>
      ))}
    </ul>
  );
}
