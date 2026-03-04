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

const STATUS_STYLES: Record<string, { border: string; icon: string; label: string }> = {
  active: { border: "border-amber-700/40 bg-amber-900/10", icon: "\u2694\uFE0F", label: "text-amber-400" },
  completed: { border: "border-emerald-700/40 bg-emerald-900/10", icon: "\u2705", label: "text-emerald-400" },
  failed: { border: "border-red-700/40 bg-red-900/10", icon: "\u274C", label: "text-red-400" },
};

function QuestCard({ quest, status }: { quest: QuestEntry; status: string }) {
  const style = STATUS_STYLES[status] || STATUS_STYLES.active;

  return (
    <div className={`rounded-lg px-3 py-2.5 border space-y-2 ${style.border}`}>
      {/* Title */}
      <div className="flex items-center gap-2">
        <span className="text-base">{style.icon}</span>
        <span className="text-sm font-bold text-amber-200">{quest.title}</span>
      </div>

      {/* Description */}
      {quest.description && (
        <div className="text-xs text-gray-400 bg-gray-800/40 rounded px-2 py-1.5 border border-gray-700/30 italic">
          {quest.description}
        </div>
      )}

      {/* Objectives */}
      {quest.objectives.length > 0 && (
        <div className="space-y-1">
          <div className="text-[10px] text-gray-500 font-medium">Objectives</div>
          {quest.objectives.map((obj, i) => {
            const text = typeof obj === "string" ? obj : obj.text;
            const done = typeof obj === "object" ? obj.completed : false;
            return (
              <div
                key={i}
                className={`flex items-start gap-2 text-xs animate-item-appear ${done ? "text-emerald-400/60" : "text-gray-300"}`}
                style={{ animationDelay: `${i * 40}ms` }}
              >
                <span className={`mt-0.5 flex-shrink-0 w-4 h-4 rounded border flex items-center justify-center text-[10px] ${
                  done
                    ? "bg-emerald-900/40 border-emerald-600/50 text-emerald-400"
                    : "bg-gray-800/60 border-gray-600/50 text-gray-500"
                }`}>
                  {done ? "\u2713" : ""}
                </span>
                <span className={done ? "line-through" : ""}>{text}</span>
              </div>
            );
          })}
        </div>
      )}

      {/* Rewards */}
      {quest.rewards && Object.keys(quest.rewards).length > 0 && (
        <div className="space-y-1">
          <div className="text-[10px] text-gray-500 font-medium">Rewards</div>
          <div className="flex flex-wrap gap-1.5">
            {quest.rewards.gold != null && (
              <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-yellow-900/30 text-yellow-300 border border-yellow-700/30 font-medium">
                {"\uD83E\uDE99"} {String(quest.rewards.gold)} gold
              </span>
            )}
            {quest.rewards.xp != null && (
              <span className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-purple-900/30 text-purple-300 border border-purple-700/30 font-medium">
                {"\u2728"} {String(quest.rewards.xp)} XP
              </span>
            )}
            {Object.entries(quest.rewards)
              .filter(([k]) => k !== "gold" && k !== "xp")
              .map(([k, v]) => (
                <span key={k} className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-gray-800/60 text-gray-300 border border-gray-700/40">
                  {k}: {String(v)}
                </span>
              ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function QuestJournalRenderer({ data }: ToolRendererProps) {
  const d = data as unknown as Record<string, unknown>;

  if (d.error) {
    return <div className="mt-2 text-red-400 text-sm">{d.error as string}</div>;
  }

  // Quest completion result
  if (d.message && d.distributed_to) {
    const cd = d as unknown as QuestCompleteData;
    return (
      <div className="mt-2 bg-gray-800/30 rounded-lg px-3 py-2.5 border border-gray-700/30 space-y-2">
        <div className="flex items-center gap-2">
          <span className="text-xl">{"\uD83C\uDF89"}</span>
          <div>
            <div className="text-sm font-bold text-yellow-300">{cd.message}</div>
            {cd.title && <div className="text-[10px] text-gray-500">{cd.title}</div>}
          </div>
        </div>
        <div className="space-y-1">
          {cd.distributed_to.map((p) => (
            <div key={p.name} className="flex items-center justify-between text-xs bg-gray-800/40 rounded px-2 py-1 border border-gray-700/30">
              <span className="text-gray-200 font-medium">{p.name}</span>
              <div className="flex items-center gap-2">
                <span className="text-purple-300">+{p.xp_gained} XP</span>
                <span className="text-[11px] px-1.5 py-0.5 rounded bg-blue-900/30 text-blue-300 border border-blue-700/30">
                  Lv {p.new_level}
                </span>
              </div>
            </div>
          ))}
        </div>
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
    <div className="mt-2 bg-gray-800/30 rounded-lg px-3 py-2.5 border border-gray-700/30 space-y-3">
      <div className="flex items-center gap-2">
        <span className="text-xl">{"\uD83D\uDCD6"}</span>
        <span className="text-sm font-bold text-amber-200">Quest Journal</span>
      </div>
      {jd.active?.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-[10px] text-amber-400 font-medium uppercase tracking-wider">Active ({jd.active.length})</div>
          {jd.active.map((q) => <QuestCard key={q.title} quest={q} status="active" />)}
        </div>
      )}
      {jd.completed?.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-[10px] text-emerald-400 font-medium uppercase tracking-wider">Completed ({jd.completed.length})</div>
          {jd.completed.map((q) => <QuestCard key={q.title} quest={q} status="completed" />)}
        </div>
      )}
      {jd.failed?.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-[10px] text-red-400 font-medium uppercase tracking-wider">Failed ({jd.failed.length})</div>
          {jd.failed.map((q) => <QuestCard key={q.title} quest={q} status="failed" />)}
        </div>
      )}
    </div>
  );
}
