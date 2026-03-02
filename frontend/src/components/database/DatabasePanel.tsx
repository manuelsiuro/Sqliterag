import { DatabaseOverview } from "./DatabaseOverview";
import { DatabaseActions } from "./DatabaseActions";

interface DatabasePanelProps {
  onClose: () => void;
}

export function DatabasePanel({ onClose }: DatabasePanelProps) {
  return (
    <div className="w-80 bg-gray-900 border-l border-gray-800 flex flex-col h-full">
      <div className="flex items-center justify-between p-4 border-b border-gray-800">
        <h2 className="text-lg font-semibold text-white">Database</h2>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-white text-xl"
        >
          &times;
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        <DatabaseOverview />
        <hr className="border-gray-800" />
        <DatabaseActions />
      </div>
    </div>
  );
}
