import { useState } from "react";
import { useSettingsStore } from "@/store/settingsStore";
import { LoadingSpinner } from "@/components/common";

export function HuggingFaceSearch() {
  const [query, setQuery] = useState("");
  const { searchResults, isSearching, isPulling, pullStatus, searchModels, pullModel } =
    useSettingsStore();

  const handleSearch = () => {
    if (query.trim()) searchModels(query.trim());
  };

  return (
    <div className="space-y-3">
      <label className="block text-sm font-medium text-gray-300">Search HuggingFace (GGUF)</label>
      <div className="flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSearch()}
          placeholder="Search models..."
          className="flex-1 bg-gray-800 text-white border border-gray-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500 placeholder:text-gray-500"
        />
        <button
          onClick={handleSearch}
          disabled={isSearching}
          className="px-3 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg text-sm disabled:opacity-50"
        >
          Search
        </button>
      </div>

      {isSearching && <LoadingSpinner size="sm" />}

      {isPulling && <p className="text-xs text-blue-400">{pullStatus}</p>}

      {searchResults.length > 0 && (
        <ul className="space-y-2 max-h-60 overflow-y-auto">
          {searchResults.map((r) => (
            <li key={r.id} className="flex items-center justify-between bg-gray-800 rounded-lg p-2">
              <div className="min-w-0 flex-1">
                <p className="text-sm text-white truncate">{r.id}</p>
                <p className="text-xs text-gray-400">
                  Downloads: {r.downloads.toLocaleString()} | Likes: {r.likes}
                </p>
              </div>
              <button
                onClick={() => pullModel(r.id)}
                disabled={isPulling}
                className="ml-2 px-2 py-1 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded disabled:opacity-50"
              >
                Pull
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
