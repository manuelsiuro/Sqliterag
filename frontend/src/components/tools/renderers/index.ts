export {
  tryParseToolResult,
  getToolRenderer,
  registerToolRenderer,
} from "./toolRendererRegistry";
export type {
  StructuredToolResult,
  ToolRendererProps,
} from "./toolRendererRegistry";

import { registerToolRenderer } from "./toolRendererRegistry";
import { DiceResultRenderer } from "./DiceResultRenderer";

registerToolRenderer("roll_d20", DiceResultRenderer);
