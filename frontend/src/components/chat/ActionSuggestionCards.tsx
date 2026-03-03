import type { ActionSuggestion } from "./parseActionSuggestions";
import { getActionIcon } from "./actionIcons";

interface ActionSuggestionCardsProps {
  actions: ActionSuggestion[];
  onAction: (label: string) => void;
  disabled: boolean;
  isLatest: boolean;
}

export function ActionSuggestionCards({
  actions,
  onAction,
  disabled,
  isLatest,
}: ActionSuggestionCardsProps) {
  const muted = !isLatest;

  return (
    <div
      className={`flex flex-wrap gap-2 mt-3 ${muted ? "opacity-40 pointer-events-none" : ""}`}
    >
      {actions.map((action, i) => (
        <button
          key={action.label}
          disabled={disabled || muted}
          onClick={() => onAction(action.label)}
          className={`
            card-appear group/card flex items-start gap-2.5 text-left
            px-3.5 py-2.5 rounded-xl border text-sm
            transition-all duration-150
            ${
              disabled
                ? "bg-gray-800/40 border-gray-700/20 text-gray-500 cursor-not-allowed"
                : "bg-gradient-to-br from-gray-800/80 to-gray-900/90 border-indigo-500/20 text-gray-200 cursor-pointer hover:border-indigo-400/50 hover:shadow-[0_0_12px_rgba(99,102,241,0.15)] active:scale-[0.97]"
            }
          `}
          style={{ animationDelay: `${i * 60}ms` }}
        >
          <span className="text-base leading-none mt-0.5 shrink-0">
            {getActionIcon(action.label)}
          </span>
          <span className="min-w-0">
            <span className="font-medium block leading-tight">{action.label}</span>
            <span className="text-xs text-gray-400 block leading-snug line-clamp-1 mt-0.5">
              {action.description}
            </span>
          </span>
        </button>
      ))}
    </div>
  );
}
