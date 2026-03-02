import { useState } from "react";
import { useSettingsStore } from "@/store/settingsStore";
import { LoadingSpinner } from "@/components/common";

function formatRelativeDate(isoDate: string | null): string {
  if (!isoDate) return "";
  const diff = Date.now() - new Date(isoDate).getTime();
  const days = Math.floor(diff / 86400000);
  if (days < 1) return "today";
  if (days === 1) return "1 day ago";
  if (days < 30) return `${days} days ago`;
  const months = Math.floor(days / 30);
  if (months === 1) return "1 month ago";
  if (months < 12) return `${months} months ago`;
  const years = Math.floor(months / 12);
  return years === 1 ? "1 year ago" : `${years} years ago`;
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return n.toString();
}

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
        <ul className="space-y-2 max-h-96 overflow-y-auto">
          {searchResults.map((r) => {
            const author = r.author || r.id.split("/")[0];
            const modelName = r.id.split("/").pop() || r.id;
            const visibleTags = r.tags.slice(0, 5);
            const extraTagCount = Math.max(0, r.tags.length - 5);

            return (
              <li key={r.id} className="bg-gray-800 rounded-lg p-3 space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-white font-medium truncate" title={r.id}>
                      {modelName}
                    </p>
                    <p className="text-xs text-gray-500">{author}</p>
                  </div>
                  <div className="flex gap-1.5 shrink-0">
                    {r.url && (
                      <a
                        href={r.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="px-2 py-1 bg-gray-700 hover:bg-gray-600 text-gray-300 hover:text-white text-xs rounded"
                        title="Open on HuggingFace"
                      >
                        HF
                      </a>
                    )}
                    <button
                      onClick={() => pullModel(r.id)}
                      disabled={isPulling}
                      className="px-2 py-1 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded disabled:opacity-50"
                    >
                      Pull
                    </button>
                  </div>
                </div>

                <div className="flex items-center gap-3 text-xs text-gray-400">
                  <span title="Downloads">{formatNumber(r.downloads)} downloads</span>
                  <span title="Likes">{r.likes} likes</span>
                  {r.pipeline_tag && (
                    <span className="bg-gray-700 text-gray-300 px-1.5 py-0.5 rounded text-[10px]">
                      {r.pipeline_tag}
                    </span>
                  )}
                  {r.last_modified && (
                    <span className="ml-auto text-gray-500">
                      {formatRelativeDate(r.last_modified)}
                    </span>
                  )}
                </div>

                {visibleTags.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {visibleTags.map((tag) => (
                      <span
                        key={tag}
                        className="bg-gray-700/60 text-gray-400 px-1.5 py-0.5 rounded text-[10px]"
                      >
                        {tag}
                      </span>
                    ))}
                    {extraTagCount > 0 && (
                      <span className="text-gray-500 text-[10px] py-0.5">
                        +{extraTagCount} more
                      </span>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
