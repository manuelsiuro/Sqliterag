# Custom Tool Renderers

Extend tool results with rich, data-driven UI components instead of raw text.

## Overview

By default, tool results render as plain text inside a green `<pre>` block. The **tool renderer system** lets you replace that with custom React components for any tool — styled dice, charts, formatted tables, or anything else.

How it works:

1. Your backend tool returns a **JSON string** with a `"type"` discriminator field
2. The frontend attempts to parse the result as JSON
3. If parsing succeeds and a renderer is registered for that `type`, the custom component renders
4. Otherwise, the existing `<pre>` fallback kicks in — fully backward-compatible

## Architecture

```
Backend tool function
  │
  ▼
returns JSON string: {"type": "roll_d20", "rolls": [15, 8], ...}
  │
  ▼
SSE tool_result event (carries result string as-is)
  │
  ▼
ToolResultBubble.tsx
  │
  ├── tryParseToolResult(content) → StructuredToolResult | null
  │
  ├── getToolRenderer(parsed.type) → React component | null
  │
  ├── [match found] → <CustomRenderer data={parsed} rawContent={content} />
  │
  └── [no match]   → <pre>{content}</pre>  (existing fallback)
```

No changes are needed to `ToolService`, `ChatService`, SSE events, DB models, or TypeScript API types. The DB `content` column stays `Text` — JSON is just a string.

## Step-by-Step: Adding a Custom Renderer

### Step 1 — Backend: Return JSON from your tool

Make your tool function return a JSON string with a `"type"` field as the discriminator:

```python
# backend/app/services/builtin_tools.py
import json

def weather_lookup(city: str) -> str:
    """Look up current weather for a city."""
    # ... fetch weather data ...
    return json.dumps({
        "type": "weather",
        "city": city,
        "temp": 72,
        "condition": "sunny",
        "humidity": 45,
    })
```

The `"type"` field is the key the frontend uses to find the right renderer. Pick a unique, descriptive string.

### Step 2 — Create a Renderer Component

Create a new file in `frontend/src/components/tools/renderers/`:

```tsx
// frontend/src/components/tools/renderers/WeatherRenderer.tsx
import type { ToolRendererProps } from "./toolRendererRegistry";

interface WeatherData {
  city: string;
  temp: number;
  condition: string;
  humidity: number;
}

export function WeatherRenderer({ data }: ToolRendererProps) {
  const { city, temp, condition, humidity } = data as unknown as WeatherData;

  return (
    <div className="mt-2 p-3 bg-gray-900/60 rounded-lg">
      <div className="text-white text-lg font-bold">{city}</div>
      <div className="text-green-300 text-2xl font-bold mt-1">{temp}°F</div>
      <div className="text-gray-400 text-sm mt-1">
        {condition} · {humidity}% humidity
      </div>
    </div>
  );
}
```

Your component receives:
- `data` — the parsed JSON object (cast it to your specific shape)
- `rawContent` — the original JSON string, useful for debugging or copy-to-clipboard features

### Step 3 — Register the Renderer

Add one import and one registration call in `frontend/src/components/tools/renderers/index.ts`:

```ts
import { registerToolRenderer } from "./toolRendererRegistry";
import { WeatherRenderer } from "./WeatherRenderer";

registerToolRenderer("weather", WeatherRenderer);
```

That's it. The next time a tool returns `{"type": "weather", ...}`, your component renders automatically.

## API Reference

### `StructuredToolResult`

```ts
interface StructuredToolResult {
  type: string;
  [key: string]: unknown;
}
```

The base shape for all structured tool results. The `type` field is the discriminator used to look up the renderer.

### `ToolRendererProps`

```ts
interface ToolRendererProps {
  data: StructuredToolResult;
  rawContent: string;
}
```

Props passed to every renderer component:
- `data` — Parsed JSON result. Cast to your specific interface to access typed fields.
- `rawContent` — The original string content from the message, before parsing.

### `registerToolRenderer(type, component)`

Registers a React component as the renderer for a given `type` string.

```ts
registerToolRenderer("roll_d20", DiceResultRenderer);
```

### `getToolRenderer(type)`

Returns the registered component for a type, or `null` if none is registered.

### `tryParseToolResult(content)`

Attempts to `JSON.parse` the content string. Returns a `StructuredToolResult` if the result is a valid object with a `type` field, otherwise returns `null`. Safe to call on any string — never throws.

## Design Guidelines

### Theme

Renderers live inside the green tool-result bubble. Stick to the existing dark theme:

| Purpose | Classes |
|---------|---------|
| Background | `bg-gray-900/60`, `bg-green-900/30` |
| Primary text | `text-white` |
| Secondary text | `text-gray-300`, `text-gray-400` |
| Accent text | `text-green-300`, `text-green-400` |
| Borders | `border-green-500/50`, `border-green-700/40` |
| Cards | `rounded-lg` or `rounded-xl` with `p-3` |

### Animations

Define keyframes in `frontend/src/index.css` and reference them via a utility class. For lists, use staggered `animationDelay` on each item:

```tsx
style={{ animationDelay: `${index * 80}ms` }}
```

### Edge Cases

Always handle gracefully:
- Empty arrays (e.g. zero dice rolled)
- Missing optional fields (use defaults)
- Unexpected values (don't crash — render what you can)

## The Dice Renderer as Reference

See `DiceResultRenderer.tsx` for the canonical example. Highlights:

- **Data-driven conditional styling**: nat-20 gets a golden glow (`ring-yellow-400/60`, yellow shadow), nat-1 gets dimmed red (`text-red-300 opacity-70`)
- **Staggered animation**: Each die pops in with an 80ms delay using `animate-dice-pop`
- **Modifier display**: Only shown when `modifier !== 0`
- **Gradient backgrounds**: `bg-gradient-to-br from-green-700 to-green-900` for the dice squares
