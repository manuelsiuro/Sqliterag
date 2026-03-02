import { useState } from "react";
import type { ToolCreate, ToolDefinition, ToolParameterProperty } from "@/types";

interface ToolFormProps {
  tool?: ToolDefinition;
  onSave: (data: ToolCreate) => void;
  onCancel: () => void;
}

interface ParamEntry {
  name: string;
  type: string;
  description: string;
  required: boolean;
}

export function ToolForm({ tool, onSave, onCancel }: ToolFormProps) {
  const [name, setName] = useState(tool?.name ?? "");
  const [description, setDescription] = useState(tool?.description ?? "");
  const [executionType, setExecutionType] = useState(tool?.execution_type ?? "mock");
  const [urlTemplate, setUrlTemplate] = useState(
    (tool?.execution_config as Record<string, string>)?.url ?? ""
  );
  const [httpMethod, setHttpMethod] = useState(
    (tool?.execution_config as Record<string, string>)?.method ?? "GET"
  );

  const initialParams: ParamEntry[] = tool
    ? Object.entries(tool.parameters_schema.properties ?? {}).map(([pName, prop]) => ({
        name: pName,
        type: (prop as ToolParameterProperty).type,
        description: (prop as ToolParameterProperty).description ?? "",
        required: (tool.parameters_schema.required ?? []).includes(pName),
      }))
    : [];

  const [params, setParams] = useState<ParamEntry[]>(initialParams);

  const addParam = () => {
    setParams([...params, { name: "", type: "string", description: "", required: false }]);
  };

  const removeParam = (index: number) => {
    setParams(params.filter((_, i) => i !== index));
  };

  const updateParam = (index: number, field: keyof ParamEntry, value: string | boolean) => {
    setParams(params.map((p, i) => (i === index ? { ...p, [field]: value } : p)));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    const properties: Record<string, ToolParameterProperty> = {};
    const required: string[] = [];

    for (const p of params) {
      if (!p.name.trim()) continue;
      properties[p.name.trim()] = { type: p.type, description: p.description };
      if (p.required) required.push(p.name.trim());
    }

    const data: ToolCreate = {
      name: name.trim(),
      description,
      parameters_schema: { type: "object", required, properties },
      execution_type: executionType,
      execution_config:
        executionType === "http"
          ? { url: urlTemplate, method: httpMethod }
          : {},
    };

    onSave(data);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-xs text-gray-400 mb-1">Function Name</label>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. get_weather"
          required
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-white focus:outline-none focus:border-blue-500"
        />
      </div>

      <div>
        <label className="block text-xs text-gray-400 mb-1">Description</label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="What does this tool do?"
          required
          rows={2}
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-white focus:outline-none focus:border-blue-500 resize-none"
        />
      </div>

      <div>
        <label className="block text-xs text-gray-400 mb-1">Execution Type</label>
        <select
          value={executionType}
          onChange={(e) => setExecutionType(e.target.value)}
          className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-white focus:outline-none focus:border-blue-500"
        >
          <option value="mock">Mock</option>
          <option value="http">HTTP</option>
        </select>
      </div>

      {executionType === "http" && (
        <div className="space-y-3 p-3 bg-gray-800/50 rounded border border-gray-700">
          <div>
            <label className="block text-xs text-gray-400 mb-1">URL Template</label>
            <input
              value={urlTemplate}
              onChange={(e) => setUrlTemplate(e.target.value)}
              placeholder="https://api.example.com/data?q={query}"
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-white focus:outline-none focus:border-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-400 mb-1">HTTP Method</label>
            <select
              value={httpMethod}
              onChange={(e) => setHttpMethod(e.target.value)}
              className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-sm text-white focus:outline-none focus:border-blue-500"
            >
              <option value="GET">GET</option>
              <option value="POST">POST</option>
              <option value="PUT">PUT</option>
              <option value="DELETE">DELETE</option>
            </select>
          </div>
        </div>
      )}

      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-xs text-gray-400">Parameters</label>
          <button
            type="button"
            onClick={addParam}
            className="text-xs text-blue-400 hover:text-blue-300"
          >
            + Add Parameter
          </button>
        </div>
        <div className="space-y-2">
          {params.map((p, i) => (
            <div key={i} className="flex items-start gap-2 p-2 bg-gray-800/50 rounded border border-gray-700">
              <div className="flex-1 space-y-1">
                <input
                  value={p.name}
                  onChange={(e) => updateParam(i, "name", e.target.value)}
                  placeholder="param name"
                  className="w-full px-2 py-1 bg-gray-800 border border-gray-700 rounded text-xs text-white focus:outline-none focus:border-blue-500"
                />
                <div className="flex gap-2">
                  <select
                    value={p.type}
                    onChange={(e) => updateParam(i, "type", e.target.value)}
                    className="px-2 py-1 bg-gray-800 border border-gray-700 rounded text-xs text-white focus:outline-none focus:border-blue-500"
                  >
                    <option value="string">string</option>
                    <option value="number">number</option>
                    <option value="integer">integer</option>
                    <option value="boolean">boolean</option>
                  </select>
                  <label className="flex items-center gap-1 text-xs text-gray-400">
                    <input
                      type="checkbox"
                      checked={p.required}
                      onChange={(e) => updateParam(i, "required", e.target.checked)}
                      className="rounded"
                    />
                    Required
                  </label>
                </div>
                <input
                  value={p.description}
                  onChange={(e) => updateParam(i, "description", e.target.value)}
                  placeholder="description"
                  className="w-full px-2 py-1 bg-gray-800 border border-gray-700 rounded text-xs text-white focus:outline-none focus:border-blue-500"
                />
              </div>
              <button
                type="button"
                onClick={() => removeParam(i)}
                className="text-red-400 hover:text-red-300 text-sm mt-1"
              >
                &times;
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="flex gap-2 pt-2">
        <button
          type="submit"
          className="flex-1 px-3 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded transition-colors"
        >
          {tool ? "Update" : "Create"} Tool
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-3 py-2 bg-gray-700 hover:bg-gray-600 text-white text-sm rounded transition-colors"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
