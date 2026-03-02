import { useSettingsStore } from "@/store/settingsStore";
import { LoadingSpinner } from "@/components/common";

export function ModelDetailCard() {
  const { selectedModelDetail, isLoadingModelDetail } = useSettingsStore();

  if (isLoadingModelDetail) {
    return (
      <div className="flex justify-center py-3">
        <LoadingSpinner size="sm" />
      </div>
    );
  }

  if (!selectedModelDetail) return null;

  const details = [
    { label: "Family", value: selectedModelDetail.family },
    { label: "Parameters", value: selectedModelDetail.parameter_size },
    { label: "Quantization", value: selectedModelDetail.quantization_level },
    {
      label: "Context Length",
      value: selectedModelDetail.context_length?.toLocaleString(),
    },
    { label: "Format", value: selectedModelDetail.format },
    { label: "Parent Model", value: selectedModelDetail.parent_model || undefined },
  ].filter((d) => d.value);

  if (details.length === 0) return null;

  return (
    <div className="bg-gray-800 rounded-lg p-3 space-y-1.5">
      <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">
        Model Info
      </h3>
      {details.map((d) => (
        <div key={d.label} className="flex justify-between text-sm">
          <span className="text-gray-400">{d.label}</span>
          <span className="text-white font-medium">{d.value}</span>
        </div>
      ))}
    </div>
  );
}
