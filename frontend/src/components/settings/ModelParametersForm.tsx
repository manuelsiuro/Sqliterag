import { useSettingsStore, QWEN3_DEFAULTS } from "@/store/settingsStore";
import type { ModelParameters } from "@/types";

interface ParamConfig {
  key: keyof ModelParameters;
  label: string;
  description: string;
  min: number;
  max: number;
  step: number;
  placeholder: string;
  isInt?: boolean;
}

interface ParamGroup {
  title: string;
  params: ParamConfig[];
}

const GROUPS: ParamGroup[] = [
  {
    title: "Sampling",
    params: [
      { key: "temperature", label: "Temperature", description: "Lower = more focused, higher = more creative", min: 0, max: 2, step: 0.1, placeholder: "0.7" },
      { key: "top_p", label: "Top P", description: "Nucleus sampling probability mass threshold", min: 0, max: 1, step: 0.05, placeholder: "0.9" },
      { key: "top_k", label: "Top K", description: "Limits choices to the top K most likely tokens", min: 1, max: 100, step: 1, placeholder: "40", isInt: true },
      { key: "presence_penalty", label: "Presence Penalty", description: "Penalizes repeated tokens to reduce repetition", min: 0, max: 2, step: 0.1, placeholder: "0.0" },
    ],
  },
  {
    title: "Output",
    params: [
      { key: "num_ctx", label: "Context Window", description: "Max tokens the model processes as input", min: 512, max: 131072, step: 512, placeholder: "8192", isInt: true },
      { key: "num_predict", label: "Max Output Tokens", description: "Max tokens generated in the response", min: 64, max: 8192, step: 64, placeholder: "1024", isInt: true },
    ],
  },
  {
    title: "Advanced",
    params: [
      { key: "repeat_penalty", label: "Repeat Penalty", description: "Penalizes recently used tokens to avoid loops", min: 0, max: 2, step: 0.1, placeholder: "1.1" },
      { key: "seed", label: "Seed", description: "Fixed seed for reproducible outputs", min: 0, max: 999999, step: 1, placeholder: "random", isInt: true },
    ],
  },
];

function getEffectivePlaceholder(p: ParamConfig, detail: { family: string | null } | null): string {
  const qwenVal = QWEN3_DEFAULTS[p.key];
  if (detail?.family?.toLowerCase().startsWith("qwen3") && qwenVal != null) {
    return String(qwenVal);
  }
  return p.placeholder;
}

export function ModelParametersForm() {
  const { modelParameters, updateModelParameters, resetModelParameters, selectedModelDetail } = useSettingsStore();

  const hasAnyOverride = Object.values(modelParameters).some((v) => v !== null);

  const handleChange = (key: keyof ModelParameters, raw: string) => {
    if (raw === "") {
      updateModelParameters({ [key]: null });
      return;
    }
    const allParams = GROUPS.flatMap((g) => g.params);
    const config = allParams.find((p) => p.key === key)!;
    const val = config.isInt ? parseInt(raw, 10) : parseFloat(raw);
    if (!isNaN(val)) {
      updateModelParameters({ [key]: val });
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
          Generation Parameters
        </h3>
        {hasAnyOverride && (
          <button
            onClick={resetModelParameters}
            className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
          >
            Reset All
          </button>
        )}
      </div>

      {GROUPS.map((group) => (
        <div key={group.title} className="bg-gray-800/30 rounded-lg border border-gray-700/30 p-3 space-y-3">
          <h4 className="text-xs font-medium text-gray-500 uppercase tracking-wider">{group.title}</h4>
          {group.params.map((p) => {
            const value = modelParameters[p.key];
            const placeholder = getEffectivePlaceholder(p, selectedModelDetail);
            return (
              <div key={p.key} className="space-y-1">
                <div className="flex items-center justify-between">
                  <label className="text-sm text-gray-300">{p.label}</label>
                  <div className="flex items-center gap-1.5">
                    <span className={`text-xs tabular-nums w-14 text-right ${value !== null ? "text-gray-400" : "text-gray-600 italic"}`}>
                      {value !== null ? value : placeholder}
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
                <p className="text-xs text-gray-600">{p.description}</p>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
