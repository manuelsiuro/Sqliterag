import { useEffect } from "react";
import { useSettingsStore } from "@/store/settingsStore";

interface ModelSelectorProps {
  selectedModel: string;
  onSelect: (model: string) => void;
}

export function ModelSelector({ selectedModel, onSelect }: ModelSelectorProps) {
  const { localModels, loadLocalModels } = useSettingsStore();

  useEffect(() => {
    loadLocalModels();
  }, [loadLocalModels]);

  return (
    <div>
      <label className="block text-sm font-medium text-gray-300 mb-1">Model</label>
      <select
        value={selectedModel}
        onChange={(e) => onSelect(e.target.value)}
        className="w-full bg-gray-800 text-white border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500"
      >
        {localModels.length === 0 && <option value="">No models available</option>}
        {localModels.map((m) => (
          <option key={m.name} value={m.name}>
            {m.name} {m.parameter_size ? `(${m.parameter_size})` : ""}
          </option>
        ))}
      </select>
    </div>
  );
}
