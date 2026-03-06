import type { ToolRendererProps } from "./toolRendererRegistry";
import { TYPE_ICONS } from "@/constants/rpg";

interface ItemDetailData {
  name: string;
  item_type: string;
  description: string;
  weight: number;
  value_gp: number;
  properties: Record<string, unknown>;
  rarity: string;
  error?: string;
}

const RARITY_LABEL: Record<string, string> = {
  common: "Common",
  uncommon: "Uncommon",
  rare: "Rare",
  very_rare: "Very Rare",
  legendary: "Legendary",
};

/* ── Rarity-driven style tokens ───────────────────────────────── */

const RARITY_NAME: Record<string, string> = {
  common: "text-gray-200",
  uncommon: "text-green-300",
  rare: "text-blue-300",
  very_rare: "text-purple-300",
  legendary: "text-yellow-200",
};

const RARITY_BADGE_BG: Record<string, string> = {
  common: "bg-gray-700/50 text-gray-300 border-gray-600/50",
  uncommon: "bg-green-900/50 text-green-300 border-green-600/40",
  rare: "bg-blue-900/50 text-blue-300 border-blue-600/40",
  very_rare: "bg-purple-900/50 text-purple-300 border-purple-600/40",
  legendary: "bg-yellow-900/50 text-yellow-300 border-yellow-500/40",
};

const RARITY_CARD_BORDER: Record<string, string> = {
  common: "border-gray-700/50",
  uncommon: "border-green-700/40",
  rare: "border-blue-700/40",
  very_rare: "border-purple-700/40",
  legendary: "border-yellow-600/40",
};

const RARITY_GLOW: Record<string, string> = {
  common: "",
  uncommon: "shadow-[0_0_12px_rgba(34,197,94,0.08)]",
  rare: "shadow-[0_0_12px_rgba(59,130,246,0.12)]",
  very_rare: "shadow-[0_0_16px_rgba(168,85,247,0.15)]",
  legendary: "shadow-[0_0_20px_rgba(250,204,21,0.18)]",
};

const PROP_ICONS: Record<string, string> = {
  damage: "\u2694\uFE0F",
  healing: "\uD83D\uDC9A",
  defense: "\uD83D\uDEE1\uFE0F",
  range: "\uD83C\uDFF9",
  duration: "\u23F3",
  charges: "\u26A1",
};

function formatPropertyValue(value: unknown): string {
  if (typeof value === "object" && value !== null) {
    const obj = value as Record<string, unknown>;
    if ("type" in obj && "value" in obj) {
      return `${obj.value} ${obj.type}`;
    }
    return JSON.stringify(value);
  }
  return String(value);
}

export function ItemDetailRenderer({ data }: ToolRendererProps) {
  const d = data as unknown as ItemDetailData;

  if (d.error) {
    return <div className="mt-2 text-red-400 text-sm">{d.error}</div>;
  }

  const icon = TYPE_ICONS[d.item_type] || "\uD83D\uDCE6";
  const nameColor = RARITY_NAME[d.rarity] || "text-gray-200";
  const badgeCls = RARITY_BADGE_BG[d.rarity] || RARITY_BADGE_BG.common;
  const borderCls = RARITY_CARD_BORDER[d.rarity] || RARITY_CARD_BORDER.common;
  const glowCls = RARITY_GLOW[d.rarity] || "";

  const props = d.properties && typeof d.properties === "object"
    ? Object.entries(d.properties).filter(([key]) => key !== "rarity" && key !== "type")
    : [];

  return (
    <div className={`mt-2 rounded-xl border ${borderCls} bg-gray-900/60 backdrop-blur ${glowCls} overflow-hidden`}>
      {/* ── Top accent line ── */}
      <div className={`h-0.5 ${
        d.rarity === "legendary" ? "bg-gradient-to-r from-yellow-600 via-amber-400 to-yellow-600" :
        d.rarity === "very_rare" ? "bg-gradient-to-r from-purple-700 via-purple-400 to-purple-700" :
        d.rarity === "rare" ? "bg-gradient-to-r from-blue-700 via-blue-400 to-blue-700" :
        d.rarity === "uncommon" ? "bg-gradient-to-r from-green-700 via-green-400 to-green-700" :
        "bg-gray-700/60"
      }`} />

      <div className="p-3 space-y-2.5">
        {/* ── Header row ── */}
        <div className="flex items-start gap-2.5">
          {/* Icon container */}
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 border ${borderCls} bg-gray-800/60`}>
            <span className="text-lg leading-none">{icon}</span>
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className={`text-sm font-bold ${nameColor} truncate`}>{d.name}</span>
              <span className={`shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded-md border ${badgeCls}`}>
                {RARITY_LABEL[d.rarity] || d.rarity}
              </span>
            </div>
            <div className="text-[11px] text-gray-500 capitalize mt-0.5">{d.item_type}</div>
          </div>
        </div>

        {/* ── Description ── */}
        {d.description && (
          <p className="text-xs text-gray-400/90 leading-relaxed italic pl-0.5">{d.description}</p>
        )}

        {/* ── Properties (damage, etc.) ── */}
        {props.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {props.map(([key, value]) => (
              <div
                key={key}
                className="flex items-center gap-1.5 text-xs bg-gray-800/70 rounded-lg px-2 py-1 border border-gray-700/40"
              >
                <span className="text-sm leading-none">{PROP_ICONS[key] || "\u25C6"}</span>
                <div>
                  <span className="text-gray-500 capitalize">{key}</span>
                  <span className="text-gray-300 font-medium ml-1">{formatPropertyValue(value)}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ── Stats footer ── */}
        <div className="flex items-center gap-4 pt-2 border-t border-gray-700/30">
          <div className="flex items-center gap-1.5 text-xs">
            <span className="text-gray-500 text-[11px]">{"\u2696\uFE0F"}</span>
            <span className="text-gray-300 font-medium">{d.weight}</span>
            <span className="text-gray-600">lb</span>
          </div>
          <div className="flex items-center gap-1.5 text-xs">
            <span className="text-yellow-500 text-[11px]">{"\uD83E\uDE99"}</span>
            <span className="text-yellow-300 font-medium">{d.value_gp}</span>
            <span className="text-gray-600">gp</span>
          </div>
        </div>
      </div>
    </div>
  );
}
