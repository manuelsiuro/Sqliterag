import type { ToolRendererProps } from "./toolRendererRegistry";

interface SpellData {
  caster: string;
  spell_name: string;
  spell_level: number;
  target: string;
  effect: string;
  damage: number;
  damage_rolls: number[];
  healing: number;
  slots_remaining: Record<string, number>;
  target_hp: string;
  error?: string;
}

export function SpellCastRenderer({ data }: ToolRendererProps) {
  const d = data as unknown as SpellData;

  if (d.error) {
    return <div className="mt-2 text-red-400 text-sm">{d.error}</div>;
  }

  const levelLabel = d.spell_level === 0 ? "Cantrip" : `Level ${d.spell_level}`;

  return (
    <div className="mt-2 space-y-2">
      {/* Spell header */}
      <div className="flex items-center gap-2">
        <span className="text-lg">&#10024;</span>
        <div>
          <div className="text-sm font-bold text-purple-200">{d.spell_name}</div>
          <div className="text-xs text-gray-500">
            {d.caster} &middot; {levelLabel}
            {d.target && <> &rarr; {d.target}</>}
          </div>
        </div>
      </div>

      {/* Effect description */}
      <div className="text-xs text-gray-400 italic bg-gray-800/40 rounded px-2 py-1.5 border border-gray-700/30">
        {d.effect}
      </div>

      {/* Damage */}
      {d.damage > 0 && (
        <div className="flex items-center gap-2">
          <span className="text-red-400 text-sm">&#128165;</span>
          <div className="flex gap-1">
            {d.damage_rolls.map((r, i) => (
              <span
                key={i}
                className="w-6 h-6 rounded flex items-center justify-center text-xs font-bold bg-red-800/50 text-red-200 border border-red-700/40 animate-item-appear"
                style={{ animationDelay: `${i * 40}ms` }}
              >
                {r}
              </span>
            ))}
          </div>
          <span className="text-sm font-bold text-red-300">{d.damage} damage</span>
          {d.target_hp && <span className="text-xs text-gray-500 ml-auto">{d.target}: {d.target_hp}</span>}
        </div>
      )}

      {/* Healing */}
      {d.healing > 0 && (
        <div className="flex items-center gap-2">
          <span className="text-emerald-400 text-sm">&#128154;</span>
          <span className="text-sm font-bold text-emerald-300">{d.healing} healing</span>
          {d.target_hp && <span className="text-xs text-gray-500 ml-auto">{d.target}: {d.target_hp}</span>}
        </div>
      )}

      {/* Spell slots */}
      {d.spell_level > 0 && (
        <div className="text-xs text-gray-500">
          Slots remaining: {Object.entries(d.slots_remaining).map(([lvl, cnt]) => (
            <span key={lvl} className="ml-1 text-purple-400">L{lvl}: {cnt}</span>
          ))}
        </div>
      )}
    </div>
  );
}
