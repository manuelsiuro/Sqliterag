# Phase 5.5: Session Recap Generation

> **Goal**: Auto-generate a dramatic "Previously on [Campaign]..." narrative recap when resuming a campaign session, displayed as a visible card in chat before user interaction.

## Context

Players who continue a campaign across multiple sessions currently get no visual recap. The system prompt (Layer 3) injects truncated summaries for LLM context, but the player never sees a narrative catch-up. Phase 5.5 adds a theatrical "Previously on..." narration — LLM-generated, cached, and displayed as the first message when a campaign session resumes.

**Dependencies**: Phase 2.6 (session summarization) and Phase 5.1 (campaign persistence) — both complete.

---

## Architecture: REST Endpoint + Builtin Tool + Frontend Renderer

**Why REST endpoint (not SSE injection)**: The `stream_chat` endpoint requires a user message. When `continueCampaign()` returns, the conversation has zero messages — there's no natural SSE trigger. A dedicated `GET /conversations/{id}/recap` endpoint can be called immediately after continuation, returns cached or freshly generated recap JSON, and the frontend injects it as a display-only first message.

**Why also a tool**: A `session_recap` builtin tool lets the LLM respond to "what happened last session?" on demand, using the same cached recap.

---

## Data Flow

```
User clicks "Continue Campaign" (GamePanel/TopBar)
  |
  v
campaignStore.continueCampaign(id)
  -> POST /api/campaigns/{id}/continue  (existing, unchanged)
  <- { conversation_id, session_number, campaign_name }
  |
  v
chatStore.selectConversation(newConvId)
  -> GET /api/conversations/{id}  (existing, loads empty messages)
  |
  v
chatStore: detect campaign session_number > 1, no messages yet
  -> GET /api/conversations/{id}/recap  (NEW)
  |
  v
Backend: recap_service.generate_session_recap()
  -> Check cached: GameSession.session_recap column
  -> If cached: return immediately
  -> If not: get_previous_summaries() + gather party/location/quests
  -> LLM call with think=False -> dramatic 2nd-person recap
  -> Cache in GameSession.session_recap
  <- { type: "session_recap", campaign_name, session_number, recap, previous_sessions }
  |
  v
Frontend: inject as display-only first message (not persisted to DB)
  -> RecapRenderer shows amber/gold "Previously on..." card
```

---

## Implementation Steps

### Step 1: Schema — Add `session_recap` column to GameSession

**File**: `backend/app/models/rpg.py`
- Add `session_recap: Mapped[str | None] = mapped_column(Text, nullable=True)` to `GameSession`

**File**: `backend/app/database.py`
- Add `("session_recap", "TEXT")` to the `columns_to_add` list in `_migrate_game_sessions_table()` (line ~209)

### Step 2: Config

**File**: `backend/app/config.py`
- Add after the Phase 5.4 block (line ~131):
```python
# Session recap generation (Phase 5.5)
session_recap_enabled: bool = True
session_recap_max_tokens: int = 400
```

### Step 3: Recap Service (NEW)

**File**: `backend/app/services/recap_service.py` (new file)

**Reuses**:
- `campaign_service.get_previous_summaries(db, campaign_id, limit=3)` from `backend/app/services/campaign_service.py`
- Same LLM call pattern as `summarization_service.generate_session_summary()` from `backend/app/services/summarization_service.py`

**Core function**:
```python
async def generate_session_recap(
    db: AsyncSession,
    game_session: GameSession,
    llm_service,
    model: str,
) -> str:
```

**Logic**:
1. Call `get_previous_summaries(db, game_session.campaign_id, limit=settings.campaign_recap_max_sessions)`
2. Gather current Characters (limit 6), Location, active Quests from DB
3. Build LLM prompt:
   - System: `/nothink\nYou are narrating a "Previously on..." recap for a D&D campaign. Write dramatically in 2nd person, 150-200 words.`
   - User: Campaign name + previous session summaries + current party/location/quests
4. Call `llm_service.chat(model, messages, think=False, options={"num_predict": max_tokens})`
5. Return narrative text

**Programmatic fallback** (if LLM returns empty):
```python
def _programmatic_recap(campaign_name, summaries, characters) -> str:
    parts = [f"Previously on {campaign_name}..."]
    for s in summaries:
        parts.append(f"In Session {s['session_number']}: {s['summary']}")
    if characters:
        names = ", ".join(c.name for c in characters[:4])
        parts.append(f"Your party ({names}) continues the adventure.")
    return " ".join(parts)
```

### Step 4: REST Endpoint

**File**: `backend/app/routers/conversations.py`

Add after `get_rpg_state` endpoint (line ~115):
```python
@router.get("/{conversation_id}/recap")
async def get_session_recap(conversation_id: str, session: AsyncSession = Depends(get_session)):
```

**Logic**:
1. Look up GameSession for conversation_id
2. If no session, `session_number <= 1`, no `campaign_id`, or `session_recap_enabled=False` → return `None`
3. If `game_session.session_recap` cached → return parsed JSON
4. Otherwise → call `recap_service.generate_session_recap()`, cache in `game_session.session_recap`, commit
5. Return JSON: `{ type, campaign_name, session_number, recap, narrative, previous_sessions }`

**Dependency injection**: Need `llm_service` and `model` — get model from conversation's `model` field, get `llm_service` from `ChatService` dependency (same pattern as `chat.py` router).

### Step 5: Builtin Tool — `session_recap`

**File**: `backend/app/services/builtin_tools/session.py`

Add new function:
```python
async def session_recap(
    *,
    session: AsyncSession,
    conversation_id: str,
    llm_service=None,
) -> str:
    """Generate a dramatic 'Previously on...' recap of prior campaign sessions."""
```

**Logic**:
- Get game session, check `campaign_id` and `session_number > 1`
- If cached `session_recap` → return it
- Otherwise → call `recap_service.generate_session_recap()`, cache, return
- If no campaign or session 1 → return error: "No previous sessions to recap"
- Return type: `"session_recap"`

### Step 6: Register Tool

**File**: `backend/app/services/builtin_tools/__init__.py`
- Import `session_recap` from `session` module (line 68)
- Add `"session_recap": session_recap` to `BUILTIN_REGISTRY` under Phase 9 section (line ~130)

**File**: `backend/app/database.py` — `_builtin_tool_defs()`
- Add `"session_recap"` entry with description and empty parameters schema

**File**: `backend/app/services/prompt_builder.py`
- Add `"session_recap"` to `RPG_TOOL_NAMES` set (total → 57)
- Add `"session_recap"` to `_CORE_TOOLS` set (always available, since it's session-level)

### Step 7: Frontend — RecapRenderer (NEW)

**File**: `frontend/src/components/tools/renderers/RecapRenderer.tsx` (new file)

**Interface**:
```typescript
interface SessionRecapData {
  type: "session_recap";
  campaign_name?: string;
  session_number?: number;
  recap?: string;
  narrative?: boolean;
  previous_sessions?: Array<{ session_number: number; summary: string }>;
  error?: string;
}
```

**Design**:
- Card container: `bg-gray-800/30 rounded-lg px-3 py-2.5 border border-amber-700/30 space-y-2`
- Header: "Previously on {campaign_name}..." with session number pill (amber)
- Body: italic narrative text (the LLM-generated recap)
- Collapsible section: individual session summaries as sub-items
- Error handling: `if (d.error)` → red error text (standard pattern)
- Amber/gold accent colors consistent with CampaignRenderer

### Step 8: Register Renderer

**File**: `frontend/src/components/tools/renderers/index.ts`

Add as Phase 15:
```typescript
// Phase 15 -- Session Recap
import { RecapRenderer } from "./RecapRenderer";
registerToolRenderer("session_recap", RecapRenderer);
```

### Step 9: API Client

**File**: `frontend/src/services/api.ts`

Add method:
```typescript
getSessionRecap: (conversationId: string) =>
  request<SessionRecapData | null>(`/conversations/${conversationId}/recap`),
```

### Step 10: Auto-inject Recap in Chat Flow

**File**: `frontend/src/store/chatStore.ts`

Modify `selectConversation` (line ~57):
- After loading messages, if `messages.length === 0`:
  - Call `api.getSessionRecap(id)` (try/catch, silent on failure)
  - If recap returned with `.recap` content:
    - Create a display-only `Message` with `role: "tool"`, `tool_name: "session_recap"`, `content: JSON.stringify(recap)`
    - Prepend to messages array
- This makes recap appear automatically when opening a continued campaign session

Also add `injectRecapMessage` helper method to the store interface for use from `handleContinue`:
```typescript
injectRecapMessage: (recap: SessionRecapData) => void;
```

### Step 11: Campaign Continuation Integration

**File**: `frontend/src/components/rpg/GamePanel.tsx`

Update `handleContinue` (line ~448):
- After `continueCampaign()` + `selectConversation()`:
  - Fetch recap via `api.getSessionRecap(conversationId)`
  - If recap exists, call `useChatStore.getState().injectRecapMessage(recap)`
- Same update in `TopBar.tsx` if it has a Continue button

---

## Edge Cases

| Case | Handling |
|------|----------|
| No previous summaries (sessions ended without summary) | Programmatic fallback: "You continue your adventure in {world_name}..." |
| LLM returns empty (qwen3.5 thinking mode issue) | `think=False` prevents this. If still empty, use programmatic fallback |
| Session 1 (first in campaign) | Endpoint returns `null`, frontend skips injection |
| Non-campaign session | Endpoint returns `null`, frontend skips injection |
| Page reload on continued session | `selectConversation` detects `messages.length === 0` + calls recap endpoint (cached, instant) |
| Config disabled (`session_recap_enabled=False`) | Endpoint returns `null` |
| Recap already cached | DB column `session_recap` returned instantly, no LLM call |

---

## Files Modified (Summary)

| File | Change |
|------|--------|
| `backend/app/models/rpg.py` | Add `session_recap` column to GameSession |
| `backend/app/database.py` | Migration + tool def seeding |
| `backend/app/config.py` | Add `session_recap_enabled`, `session_recap_max_tokens` |
| `backend/app/services/recap_service.py` | **NEW** — Core recap generation |
| `backend/app/routers/conversations.py` | Add `GET /{id}/recap` endpoint |
| `backend/app/services/builtin_tools/session.py` | Add `session_recap` tool function |
| `backend/app/services/builtin_tools/__init__.py` | Import + register in BUILTIN_REGISTRY |
| `backend/app/services/prompt_builder.py` | Add to RPG_TOOL_NAMES + _CORE_TOOLS |
| `frontend/src/components/tools/renderers/RecapRenderer.tsx` | **NEW** — Recap card renderer |
| `frontend/src/components/tools/renderers/index.ts` | Register Phase 15 |
| `frontend/src/services/api.ts` | Add `getSessionRecap()` |
| `frontend/src/store/chatStore.ts` | Auto-inject recap on conversation load |
| `frontend/src/components/rpg/GamePanel.tsx` | Inject recap after Continue Campaign |

---

## Verification

1. **Backend**: `curl http://localhost:8000/api/conversations/{id}/recap` for a continued campaign session — should return recap JSON
2. **Tool test**: In chat, type "what happened last session?" — LLM should call `session_recap` tool, RecapRenderer displays result
3. **Chrome MCP end-to-end**:
   - Start a campaign session, create characters, do some exploration
   - End session (LLM calls `end_session`)
   - Click "Continue Campaign" in GamePanel
   - Verify recap card appears as first message in new conversation
   - Verify amber/gold styling, campaign name in header, italic narrative
   - Reload page, re-select the conversation — verify recap reappears (cached)
   - Screenshot the recap card for visual verification
4. **Edge case**: Start a non-campaign session — verify no recap injected
5. **Config test**: Set `SESSION_RECAP_ENABLED=false`, verify endpoint returns null
