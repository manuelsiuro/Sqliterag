const ICON_RULES: [RegExp, string][] = [
  [/equip|armor|weapon|shield|gear/i, "\u{1F6E1}\u{FE0F}"],   // 🛡️
  [/explore|travel|journey|wander/i, "\u{1F9ED}"],             // 🧭
  [/npc|meet|talk|speak|greet|convers/i, "\u{1F4AC}"],         // 💬
  [/quest|adventure|mission|objective/i, "\u{1F4DC}"],         // 📜
  [/combat|fight|attack|battle|slay/i, "\u{2694}\u{FE0F}"],   // ⚔️
  [/spell|magic|cast|enchant|arcane/i, "\u{2728}"],            // ✨
  [/heal|rest|recover|sleep|camp/i, "\u{1F49A}"],              // 💚
  [/inventory|item|loot|pick\s?up|bag/i, "\u{1F392}"],        // 🎒
  [/character|customiz|create|build|class/i, "\u{1F9D9}"],     // 🧙
  [/shop|buy|trade|sell|merchant/i, "\u{1F6D2}"],              // 🛒
  [/look|examine|inspect|search|investi/i, "\u{1F441}"],       // 👁
  [/move|go|enter|leave|walk|run/i, "\u{1F6B6}"],              // 🚶
  [/start|begin|play|new game/i, "\u{1F3AE}"],                 // 🎮
  [/stealth|sneak|hide|shadow/i, "\u{1F977}"],                 // 🥷
  [/craft|forge|smith|brew/i, "\u{1F528}"],                    // 🔨
  [/map|location|region|area/i, "\u{1F5FA}\u{FE0F}"],         // 🗺️
];

const FALLBACK_ICON = "\u{25B6}\u{FE0F}"; // ▶️

export function getActionIcon(label: string): string {
  for (const [pattern, icon] of ICON_RULES) {
    if (pattern.test(label)) return icon;
  }
  return FALLBACK_ICON;
}
