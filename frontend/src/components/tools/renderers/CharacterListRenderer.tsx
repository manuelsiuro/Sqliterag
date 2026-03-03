import type { ToolRendererProps } from "./toolRendererRegistry";

interface CharSummary {
  name: string;
  race: string;
  class: string;
  level: number;
  current_hp: number;
  max_hp: number;
  armor_class: number;
  is_alive: boolean;
  conditions: string[];
}

interface CharListData {
  characters: CharSummary[];
  count: number;
}

export function CharacterListRenderer({ data }: ToolRendererProps) {
  const { characters, count } = data as unknown as CharListData;

  if (count === 0) {
    return (
      <div className="mt-2 text-gray-400 text-sm italic">
        No characters yet. Create one with create_character.
      </div>
    );
  }

  return (
    <div className="mt-2 space-y-2">
      <div className="text-xs text-gray-500">{count} character{count !== 1 ? "s" : ""}</div>
      {characters.map((c) => {
        const hpPct = Math.max(0, (c.current_hp / Math.max(c.max_hp, 1)) * 100);
        return (
          <div
            key={c.name}
            className={`flex items-center gap-3 bg-gray-800/50 rounded-lg px-3 py-2 border ${
              !c.is_alive ? "border-red-800/40 opacity-60" : "border-gray-700/40"
            }`}
          >
            {/* Name and class */}
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-white truncate">
                {c.name}
                {!c.is_alive && <span className="text-red-400 text-xs ml-1">(Dead)</span>}
              </div>
              <div className="text-xs text-gray-500">
                L{c.level} {c.race} {c.class}
              </div>
            </div>

            {/* Mini HP bar */}
            <div className="w-20">
              <div className="text-[10px] text-gray-500 text-right">{c.current_hp}/{c.max_hp}</div>
              <div className="w-full h-1.5 bg-gray-700 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${
                    hpPct > 50 ? "bg-emerald-500" : hpPct > 25 ? "bg-yellow-500" : "bg-red-500"
                  }`}
                  style={{ width: `${hpPct}%` }}
                />
              </div>
            </div>

            {/* AC */}
            <div className="text-center min-w-[2rem]">
              <div className="text-[10px] text-gray-500">AC</div>
              <div className="text-sm font-bold text-blue-300">{c.armor_class}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
