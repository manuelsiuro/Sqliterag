import { useEffect } from "react";
import { useDatabaseStore } from "@/store/databaseStore";

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function DatabaseOverview() {
  const { info, isLoading, loadInfo } = useDatabaseStore();

  useEffect(() => {
    loadInfo();
  }, [loadInfo]);

  if (isLoading && !info) {
    return <p className="text-sm text-gray-500">Loading...</p>;
  }

  if (!info) {
    return <p className="text-sm text-gray-500">No database info available</p>;
  }

  return (
    <div className="space-y-4">
      <div className="bg-gray-800 rounded-lg p-3 space-y-2">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
          Database
        </h3>
        <div className="space-y-1 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-400">File</span>
            <span className="text-gray-200 truncate ml-2 max-w-[160px]" title={info.file_path}>
              {info.file_path.split("/").pop()}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Size</span>
            <span className="text-gray-200">{formatBytes(info.file_size_bytes)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">SQLite</span>
            <span className="text-gray-200">{info.sqlite_version}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-400">Tables</span>
            <span className="text-gray-200">{info.table_count}</span>
          </div>
        </div>
      </div>

      <div className="bg-gray-800 rounded-lg p-3 space-y-2">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
          Tables
        </h3>
        <div className="space-y-1 text-sm">
          {info.tables.map((t) => (
            <div key={t.name} className="flex justify-between">
              <span className="text-gray-300">{t.name}</span>
              <span className="text-gray-500">{t.row_count.toLocaleString()} rows</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
