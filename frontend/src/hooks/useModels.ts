import { useEffect } from "react";
import { useSettingsStore } from "@/store/settingsStore";

export function useModels() {
  const { localModels, loadLocalModels, searchResults, searchModels, pullModel, isPulling } =
    useSettingsStore();

  useEffect(() => {
    loadLocalModels();
  }, [loadLocalModels]);

  return { localModels, searchResults, searchModels, pullModel, isPulling, refresh: loadLocalModels };
}
