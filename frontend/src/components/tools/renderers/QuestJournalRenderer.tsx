import type { ToolRendererProps } from "./toolRendererRegistry";

interface Objective {
  text: string;
  completed: boolean;
}

interface QuestEntry {
  title: string;
  description: string;
  objectives: Array<Objective | string>;
  rewards: Record<string, unknown>;
}

interface QuestJournalData {
  active: QuestEntry[];
  completed: QuestEntry[];
  failed: QuestEntry[];
}

interface QuestInfoData {
  title: string;
  description: string;
  status: string;
  objectives: Array<Objective | string>;
  rewards: Record<string, unknown>;
  error?: string;
}

interface QuestCompleteData {
  title: string;
  rewards: Record<string, unknown>;
  distributed_to: { name: string; xp_gained: number; new_level: number }[];
  message: string;
}

function QuestCard({ quest, status }: { quest: QuestEntry; status: string }) {
  const statusColors: Record<string, string> = {
    active: "border-amber-700/40 bg-amber-900/20",
    completed: "border-emerald-700/40 bg-emerald-900/20",
    failed: "border-red-700/40 bg-red-900/20",
  };

  return (
    <div className={`rounded-lg px-3 py-2 border ${statusColors[status] || statusColors.active}`}>
      <div className="text-sm font-medium text-amber-200">{quest.title}</div>
      {quest.description && (
        <div className="text-xs text-gray-400 mt-0.5">{quest.description}</div>
      )}
      {quest.objectives.length > 0 && (
        <div className="mt-1.5 space-y-0.5">
          {quest.objectives.map((obj, i) => {
            const text = typeof obj === "string" ? obj : obj.text;
            const done = typeof obj === "object" ? obj.completed : false;
            return (
              <div key={i} className={`flex items-center gap-1.5 text-xs ${done ? "text-emerald-400 line-through opacity-60" : "text-gray-300"}`}>
                <span>{done ? "\u2611" : "\u2610"}</span>
                <span>{text}</span>
              </div>
            );
          })}
        </div>
      )}
      {quest.rewards && Object.keys(quest.rewards).length > 0 && (
        <div className="mt-1.5 flex gap-2 text-[11px]">
          {quest.rewards.gold != null && (
            <span className="inline-flex items-center gap-1 bg-yellow-900/30 text-yellow-300 border border-yellow-700/40 px-2 py-0.5 rounded-full font-medium">
              <span className="text-xs">{"🪙"}</span>
              {String(quest.rewards.gold)} gold
            </span>
          )}
          {quest.rewards.xp != null && (
            <span className="inline-flex items-center gap-1 bg-purple-900/30 text-purple-300 border border-purple-700/40 px-2 py-0.5 rounded-full font-medium">
              <span className="text-xs">{"✨"}</span>
              {String(quest.rewards.xp)} XP
            </span>
          )}
          {Object.entries(quest.rewards)
            .filter(([k]) => k !== "gold" && k !== "xp")
            .map(([k, v]) => (
              <span key={k} className="inline-flex items-center gap-1 bg-gray-800/60 text-gray-300 border border-gray-700/40 px-2 py-0.5 rounded-full">
                {k}: {String(v)}
              </span>
            ))}
        </div>
      )}
    </div>
  );
}

export function QuestJournalRenderer({ data }: ToolRendererProps) {
  // Handle both journal view and single quest view
  const d = data as unknown as Record<string, unknown>;

  if (d.error) {
    return <div className="mt-2 text-red-400 text-sm">{d.error as string}</div>;
  }

  // Quest completion result
  if (d.message && d.distributed_to) {
    const cd = d as unknown as QuestCompleteData;
    return (
      <div className="mt-2 space-y-2">
        <div className="flex items-center gap-2">
          <span className="text-lg">{"🎉"}</span>
          <span className="text-sm font-bold text-yellow-300">{cd.message}</span>
        </div>
        {cd.distributed_to.map((p) => (
          <div key={p.name} className="text-xs text-gray-300">
            {p.name}: +{p.xp_gained} XP (Level {p.new_level})
          </div>
        ))}
      </div>
    );
  }

  // Single quest info
  if (d.title && d.status) {
    const qi = d as unknown as QuestInfoData;
    return (
      <div className="mt-2">
        <QuestCard
          quest={{ title: qi.title, description: qi.description, objectives: qi.objectives, rewards: qi.rewards }}
          status={qi.status}
        />
      </div>
    );
  }

  // Full journal
  const jd = d as unknown as QuestJournalData;
  const hasAny = (jd.active?.length || 0) + (jd.completed?.length || 0) + (jd.failed?.length || 0) > 0;

  if (!hasAny) {
    return <div className="mt-2 text-gray-500 text-sm italic">No quests yet.</div>;
  }

  return (
    <div className="mt-2 space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-lg">{"📖"}</span>
        <span className="text-sm font-bold text-amber-300">Quest Journal</span>
      </div>
      {jd.active?.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-xs text-amber-400 font-medium">Active ({jd.active.length})</div>
          {jd.active.map((q) => <QuestCard key={q.title} quest={q} status="active" />)}
        </div>
      )}
      {jd.completed?.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-xs text-emerald-400 font-medium">Completed ({jd.completed.length})</div>
          {jd.completed.map((q) => <QuestCard key={q.title} quest={q} status="completed" />)}
        </div>
      )}
      {jd.failed?.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-xs text-red-400 font-medium">Failed ({jd.failed.length})</div>
          {jd.failed.map((q) => <QuestCard key={q.title} quest={q} status="failed" />)}
        </div>
      )}
    </div>
  );
}
