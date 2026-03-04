export interface ActionSuggestion {
  label: string;
  description: string;
}

export interface ParsedMessage {
  narrative: string;
  actions: ActionSuggestion[];
}

const ACTION_LINE_RE = /^\*\*(.+?)\*\*\s*[–—\-:]\s*(.+)$/;

const PROMPT_LINE_RE =
  /^\*{0,2}(what would you like to do|type what you'?d like to do|choose an action|pick an action|select an option|what do you do)/i;

const TRAILING_EMOJI_LINE_RE = /^[\s🎮🎲⚔️🗡️🛡️✨💀🐉🧙📜]*$/;

/** Numbered or bulleted line: "1. Do something" or "- Do something" */
const NUMBERED_LINE_RE = /^(?:\d+[.)]\s*|[-•]\s+)(.+)$/;

/**
 * Scans the tail of an assistant message for a block of 2+ consecutive
 * "**Label** – Description" lines. Falls back to detecting plain-text
 * lines after a "What would you like to do?" prompt.
 * Returns the narrative portion and extracted actions, or null if no
 * action block is found.
 */
export function parseActionSuggestions(content: string): ParsedMessage | null {
  const lines = content.split("\n");

  // Walk backward to find where the action block starts
  let actionEnd = lines.length - 1;

  // Skip trailing blank / emoji-only lines
  while (actionEnd >= 0 && TRAILING_EMOJI_LINE_RE.test(lines[actionEnd].trim())) {
    actionEnd--;
  }

  if (actionEnd < 0) return null;

  // Now collect consecutive action lines going upward
  let actionStart = actionEnd;
  while (actionStart >= 0 && ACTION_LINE_RE.test(lines[actionStart].trim())) {
    actionStart--;
  }
  actionStart++; // first action line

  const actionLineCount = actionEnd - actionStart + 1;

  if (actionLineCount >= 2) {
    // Extract bold-format actions
    const actions: ActionSuggestion[] = [];
    for (let i = actionStart; i <= actionEnd; i++) {
      const match = lines[i].trim().match(ACTION_LINE_RE);
      if (match) {
        actions.push({ label: match[1].trim(), description: match[2].trim() });
      }
    }

    // Trim narrative: remove prompt lines just above the action block
    let narrativeEnd = actionStart - 1;
    while (
      narrativeEnd >= 0 &&
      (lines[narrativeEnd].trim() === "" || PROMPT_LINE_RE.test(lines[narrativeEnd].trim()))
    ) {
      narrativeEnd--;
    }

    const narrative = lines
      .slice(0, narrativeEnd + 1)
      .join("\n")
      .trimEnd();

    return { narrative, actions };
  }

  // Fallback: look for a prompt line followed by plain-text action lines
  // (numbered, bulleted, or plain non-empty lines)
  let promptIdx = -1;
  for (let i = lines.length - 1; i >= 0; i--) {
    if (PROMPT_LINE_RE.test(lines[i].trim())) {
      promptIdx = i;
      break;
    }
  }

  if (promptIdx < 0) return null;

  // Collect non-empty lines after the prompt, stopping at first blank line
  // once we've started collecting actions
  const actions: ActionSuggestion[] = [];
  let started = false;
  for (let i = promptIdx + 1; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (!trimmed || TRAILING_EMOJI_LINE_RE.test(trimmed)) {
      if (started) break; // stop at first gap after actions begin
      continue;
    }
    started = true;
    const numMatch = trimmed.match(NUMBERED_LINE_RE);
    const label = numMatch ? numMatch[1].trim() : trimmed;
    actions.push({ label, description: "" });
  }

  if (actions.length < 2) return null;

  // Narrative is everything before the prompt line
  let narrativeEnd = promptIdx - 1;
  while (narrativeEnd >= 0 && lines[narrativeEnd].trim() === "") {
    narrativeEnd--;
  }

  const narrative = lines
    .slice(0, narrativeEnd + 1)
    .join("\n")
    .trimEnd();

  return { narrative, actions };
}
