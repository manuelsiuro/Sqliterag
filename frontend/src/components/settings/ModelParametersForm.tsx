import { useSettingsStore } from "@/store/settingsStore";
import type { ModelParameters } from "@/types";

interface ParamConfig {
  key: keyof ModelParameters;
  label: string;
  min: number;
  max: number;
  step: number;
  placeholder: string;
  isInt?: boolean;
}

const PARAMS: ParamConfig[] = [
  { key: "temperature", label: "Temperature", min: 0, max: 2, step: 0.1, placeholder: "0.8" },
  { key: "top_p", label: "Top P", min: 0, max: 1, step: 0.05, placeholder: "0.9" },
  { key: "top_k", label: "Top K", min: 1, max: 100, step: 1, placeholder: "40", isInt: true },
  { key: "num_ctx", label: "Context Window", min: 512, max: 131072, step: 512, placeholder: "4096", isInt: true },
  { key: "repeat_penalty", label: "Repeat Penalty", min: 0, max: 2, step: 0.1, placeholder: "1.1" },
  { key: "seed", label: "Seed", min: 0, max: 999999, step: 1, placeholder: "random", isInt: true },
];

export function ModelParametersForm() {
  const { modelParameters, updateModelParameters } = useSettingsStore();

  const handleChange = (key: keyof ModelParameters, raw: string) => {
    if (raw === "") {
      updateModelParameters({ [key]: null });
      return;
    }
    const config = PARAMS.find((p) => p.key === key)!;
    const val = config.isInt ? parseInt(raw, 10) : parseFloat(raw);
    if (!isNaN(val)) {
      updateModelParameters({ [key]: val });
    }
  };

  return (
    <div className="space-y-3">
      <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
        Generation Parameters
      </h3>
      {PARAMS.map((p) => {
        const value = modelParameters[p.key];
        return (
          <div key={p.key} className="space-y-1">
            <div className="flex items-center justify-between">
              <label className="text-sm text-gray-300">{p.label}</label>
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-gray-500 tabular-nums w-14 text-right">
                  {value !== null ? value : "default"}
                </span>
                {value !== null && (
                  <button
                    onClick={() => updateModelParameters({ [p.key]: null })}
                    className="text-gray-500 hover:text-gray-300 text-xs"
                    title="Reset to default"
                  >
                    &times;
                  </button>
                )}
              </div>
            </div>
            <input
              type="range"
              min={p.min}
              max={p.max}
              step={p.step}
              value={value ?? ""}
              onChange={(e) => handleChange(p.key, e.target.value)}
              className="w-full h-1.5 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
            />
          </div>
        );
      })}
    </div>
  );
}
