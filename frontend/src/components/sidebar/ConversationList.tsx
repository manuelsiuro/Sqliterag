import type { Conversation } from "@/types";

interface ConversationListProps {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void;
}

export function ConversationList({ conversations, activeId, onSelect, onDelete }: ConversationListProps) {
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
          onClick={() => onSelect(conv.id)}
        >
          <span className="flex-1 truncate">{conv.title}</span>
          <button
            className="opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 transition-opacity"
            onClick={(e) => {
              e.stopPropagation();
              onDelete(conv.id);
            }}
          >
            &times;
          </button>
        </li>
      ))}
    </ul>
  );
}
