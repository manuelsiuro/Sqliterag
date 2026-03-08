import type { ToolRendererProps } from "./toolRendererRegistry";

interface ShellData {
  command: string;
  output: string;
  exit_code?: number;
  error?: string;
}

export function ShellResultRenderer({ data }: ToolRendererProps) {
  const d = data as unknown as ShellData;

  if (d.error) {
    return (
      <div className="mt-2 bg-gray-900/80 rounded-lg border border-red-700/40 px-3 py-2.5 font-mono text-sm">
        <div className="text-gray-400 mb-1">
          <span className="text-red-400">$</span> {d.command}
        </div>
        <div className="text-red-400 text-xs">{d.error}</div>
      </div>
    );
  }

  return (
    <div className="mt-2 bg-gray-900/80 rounded-lg border border-gray-700/40 px-3 py-2.5 font-mono text-sm">
      {/* Command header */}
      <div className="flex items-center gap-2 mb-1">
        <span className="text-emerald-400">$</span>
        <span className="text-gray-200">{d.command}</span>
        {d.exit_code !== undefined && d.exit_code !== 0 && (
          <span className="ml-auto text-xs px-1.5 py-0.5 rounded bg-red-900/40 text-red-300 border border-red-700/30">
            exit {d.exit_code}
          </span>
        )}
      </div>

      {/* Output */}
      {d.output && (
        <pre className="text-gray-300 text-xs whitespace-pre-wrap max-h-64 overflow-y-auto scrollbar-thin scrollbar-thumb-gray-700">
          {d.output}
        </pre>
      )}
    </div>
  );
}
