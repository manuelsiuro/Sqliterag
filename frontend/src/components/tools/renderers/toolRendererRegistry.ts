import type { ComponentType } from "react";

export interface StructuredToolResult {
  type: string;
  [key: string]: unknown;
}

export interface ToolRendererProps {
  data: StructuredToolResult;
  rawContent: string;
}

const registry: Record<string, ComponentType<ToolRendererProps>> = {};

export function registerToolRenderer(
  type: string,
  component: ComponentType<ToolRendererProps>,
) {
  registry[type] = component;
}

export function getToolRenderer(
  type: string,
): ComponentType<ToolRendererProps> | null {
  return registry[type] ?? null;
}

export function tryParseToolResult(
  content: string,
): StructuredToolResult | null {
  try {
    const parsed = JSON.parse(content);
    if (
      parsed &&
      typeof parsed === "object" &&
      typeof parsed.type === "string"
    ) {
      return parsed as StructuredToolResult;
    }
    return null;
  } catch {
    return null;
  }
}
