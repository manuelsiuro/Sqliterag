import type { ToolRendererProps } from "./toolRendererRegistry";

interface InventoryItem {
  name: string;
  item_type: string;
  quantity: number;
  weight_each: number;
  weight_total: number;
  value_gp: number;
  is_equipped: boolean;
  rarity: string;
}

interface InventoryData {
  character: string;
  items: InventoryItem[];
  total_weight: number;
  capacity: number;
  encumbered: boolean;
  total_value_gp: number;
  error?: string;
}

const TYPE_ICONS: Record<string, string> = {
  weapon: "\u2694\uFE0F",
  armor: "\uD83D\uDEE1\uFE0F",
  consumable: "\uD83E\uDDEA",
  quest: "\u2B50",
  scroll: "\uD83D\uDCDC",
  misc: "\uD83D\uDCE6",
};

const RARITY_COLORS: Record<string, string> = {
  common: "text-gray-400",
  uncommon: "text-green-400",
  rare: "text-blue-400",
  very_rare: "text-purple-400",
  legendary: "text-yellow-400",
};

export function InventoryRenderer({ data }: ToolRendererProps) {
  const d = data as unknown as InventoryData;

  if (d.error) {
    return <div className="mt-2 text-red-400 text-sm">{d.error}</div>;
  }

  const weightPct = Math.min(100, (d.total_weight / Math.max(d.capacity, 1)) * 100);

  return (
    <div className="mt-2 bg-gray-800/30 rounded-lg px-3 py-2.5 border border-gray-700/30 space-y-2">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-amber-300">{d.character}'s Inventory</span>
        <span className="text-xs text-yellow-400">{d.total_value_gp} gp</span>
      </div>

      {/* Weight bar */}
      <div>
        <div className="flex justify-between text-[10px] text-gray-500 mb-0.5">
          <span>Weight</span>
          <span className={d.encumbered ? "text-red-400" : ""}>
            {d.total_weight}/{d.capacity} lbs
          </span>
        </div>
        <div className="w-full h-2 bg-gray-800 rounded-full overflow-hidden border border-gray-700">
          <div
            className={`h-full rounded-full transition-all ${
              d.encumbered ? "bg-red-500" : weightPct > 70 ? "bg-yellow-500" : "bg-blue-500"
            }`}
            style={{ width: `${weightPct}%` }}
          />
        </div>
      </div>

      {/* Item list */}
      {d.items.length === 0 ? (
        <div className="text-xs text-gray-500 italic">Empty inventory.</div>
      ) : (
        <div className="space-y-1">
          {d.items.map((item, i) => (
            <div
              key={item.name}
              className="flex items-center gap-2 bg-gray-800/40 rounded px-2 py-1.5 border border-gray-700/30 animate-item-appear"
              style={{ animationDelay: `${i * 40}ms` }}
            >
              <span className="text-sm">{TYPE_ICONS[item.item_type] || "\uD83D\uDCE6"}</span>
              <span className={`text-sm flex-1 truncate ${RARITY_COLORS[item.rarity] || "text-gray-300"}`}>
                {item.name}
                {item.quantity > 1 && <span className="text-gray-500 ml-1">x{item.quantity}</span>}
              </span>
              {item.is_equipped && (
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-green-900/40 text-green-400 border border-green-700/40">
                  E
                </span>
              )}
              <span className="text-[10px] text-gray-600">{item.weight_total}lb</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
