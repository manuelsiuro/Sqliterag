import type { ToolRendererProps } from "./toolRendererRegistry";

interface CampaignStartedData {
  type: "campaign_started";
  campaign_id?: string;
  campaign_name?: string;
  world_name?: string;
  session_number?: number;
  message?: string;
  error?: string;
}

interface CampaignListData {
  type: "campaign_list";
  campaigns?: Array<{
    id: string;
    name: string;
    world_name: string;
    status: string;
    session_count: number;
  }>;
  count?: number;
  error?: string;
}

type CampaignData = CampaignStartedData | CampaignListData;

export function CampaignRenderer({ data }: ToolRendererProps) {
  const d = data as CampaignData;

  if ("error" in d && d.error) {
    return <div className="mt-2 text-red-400 text-sm">{d.error}</div>;
  }

  if (d.type === "campaign_started") {
    const cs = d as CampaignStartedData;
    return (
      <div className="bg-gray-800/30 rounded-lg px-3 py-2.5 border border-amber-700/30 space-y-1.5">
        <div className="flex items-center gap-2">
          <span className="text-amber-400 text-sm font-bold">{cs.campaign_name}</span>
          {cs.session_number != null && (
            <span className="text-[10px] px-1.5 py-px rounded-full bg-amber-900/40 text-amber-300 border border-amber-700/30">
              Session #{cs.session_number}
            </span>
          )}
        </div>
        {cs.world_name && (
          <div className="text-xs text-gray-400">World: {cs.world_name}</div>
        )}
        {cs.message && (
          <div className="text-xs text-gray-300">{cs.message}</div>
        )}
      </div>
    );
  }

  if (d.type === "campaign_list") {
    const cl = d as CampaignListData;
    if (!cl.campaigns || cl.campaigns.length === 0) {
      return (
        <div className="bg-gray-800/30 rounded-lg px-3 py-2.5 border border-gray-700/30">
          <div className="text-sm text-gray-400">No campaigns found.</div>
        </div>
      );
    }
    return (
      <div className="bg-gray-800/30 rounded-lg px-3 py-2.5 border border-gray-700/30 space-y-1.5">
        <div className="text-xs text-gray-500 uppercase tracking-wider">
          Campaigns ({cl.count ?? cl.campaigns.length})
        </div>
        {cl.campaigns.map((c) => (
          <div
            key={c.id}
            className="flex items-center gap-2 bg-gray-800/40 rounded px-2 py-1.5 border border-gray-700/20"
          >
            <span className={`text-sm font-medium ${c.status === "active" ? "text-amber-300" : "text-gray-400"}`}>
              {c.name}
            </span>
            <span className="text-[10px] text-gray-500 ml-auto">
              {c.session_count} session{c.session_count !== 1 ? "s" : ""}
            </span>
            <span className={`text-[9px] px-1.5 py-px rounded-full border ${
              c.status === "active"
                ? "bg-emerald-900/30 text-emerald-400 border-emerald-700/30"
                : "bg-gray-800 text-gray-500 border-gray-700/30"
            }`}>
              {c.status}
            </span>
          </div>
        ))}
      </div>
    );
  }

  return null;
}
