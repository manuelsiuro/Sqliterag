# Phase 5.1: Cross-Session Campaign Persistence

## Context

Currently, each conversation is an isolated game session. When a session ends (`end_session` tool), the game state (characters, locations, NPCs, quests, inventory, relationships) is trapped in that conversation forever. Players cannot continue their campaign in a new session — they must start from scratch.

Phase 5.1 introduces a **Campaign** entity that groups multiple game sessions, enabling players to end a session, start a new conversation, and resume with all characters, locations, NPCs, quests, inventory, and world state carried forward. Session summaries from prior sessions are injected into the system prompt as "Previously on..." context.

**Dependencies**: Phase 2 (memory), Phase 3 (knowledge graph), Phase 4 (multi-agent) — all complete.

---

## Design Decisions

### D1: Campaign as a new model (not extending Conversation)
A Campaign groups multiple Conversations (1:N). Conversation is a generic chat entity also used for non-RPG chats. Campaign is RPG-specific.

### D2: Entity migration (re-parent, not clone)
When continuing a campaign, active entities (Characters, Locations, NPCs, Quests, Relationships, InventoryItems) have their `session_id` updated to the new GameSession. No data duplication. The old ended session keeps its GameMemory records as historical data.

### D3: Backward compatible
All new FKs are nullable. Existing standalone sessions work exactly as before. Only sessions explicitly linked to a campaign get cross-session behavior.

### D4: One active session per campaign
A campaign can only have one `status="active"` session at a time. This prevents entity migration conflicts.

---

## Implementation Steps

### Step 1: Campaign ORM Model + GameSession FK

**File**: `backend/app/models/rpg.py`

Add `Campaign` class before `GameSession`:
```python
class Campaign(Base):
    __tablename__ = "rpg_campaigns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(200))
    world_name: Mapped[str] = mapped_column(String(200), default="Unnamed World")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | completed
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())

    sessions: Mapped[list[GameSession]] = relationship(back_populates="campaign")
```

Add to `GameSession`:
```python
campaign_id: Mapped[str | None] = mapped_column(
    String(36), ForeignKey("rpg_campaigns.id", ondelete="SET NULL"), nullable=True
)
campaign: Mapped[Campaign | None] = relationship(back_populates="sessions")
```

**File**: `backend/app/models/__init__.py` — Add `Campaign` to imports and `__all__`.

---

### Step 2: Database Migration

**File**: `backend/app/database.py`

Add `_migrate_campaigns_table(conn)` function (idempotent ALTER TABLE pattern matching existing `_migrate_game_sessions_table`):
1. `rpg_campaigns` table is auto-created by `Base.metadata.create_all`
2. Add `campaign_id` column to `rpg_game_sessions` (idempotent ALTER TABLE)
3. Create index `idx_gamesession_campaign` on `rpg_game_sessions(campaign_id, session_number)`

Call from `init_db()` alongside existing migrations.

---

### Step 3: Campaign Schemas

**New file**: `backend/app/schemas/campaign.py`

```python
class CampaignCreate(BaseModel):
    name: str
    description: str = ""

class CampaignRead(BaseModel):  # from_attributes=True
    id: str
    name: str
    world_name: str
    description: str
    status: str
    session_count: int  # computed
    created_at: datetime
    updated_at: datetime

class CampaignDetail(CampaignRead):
    sessions: list[CampaignSessionRead]

class CampaignSessionRead(BaseModel):  # from_attributes=True
    conversation_id: str
    session_number: int
    status: str
    world_name: str
    summary: str | None
    created_at: datetime
```

**File**: `backend/app/schemas/conversation.py`

Extend `ConversationRead` with optional campaign fields:
```python
campaign_id: str | None = None
campaign_name: str | None = None
session_number: int | None = None
```

---

### Step 4: Campaign Service

**New file**: `backend/app/services/campaign_service.py`

Core functions:

- `create_campaign(db, name, description) -> Campaign`
- `get_campaign(db, campaign_id) -> Campaign | None`
- `list_campaigns(db, status=None) -> list[Campaign]`
- `get_campaign_detail(db, campaign_id) -> dict` — campaign + sessions with summaries
- `continue_campaign(db, campaign_id, conversation_id) -> GameSession` — **core logic**:
  1. Verify campaign is active
  2. Find the last ended session in this campaign
  3. Verify no active session exists in this campaign
  4. Create new `Conversation` (title: "{campaign.name} - Session N")
  5. Create new `GameSession` linked to campaign and new conversation
  6. Copy `world_name`, `environment`, `current_location_id` from last session
  7. Set `session_number = last_session.session_number + 1`
  8. Re-parent active entities: `UPDATE rpg_characters SET session_id = :new WHERE session_id = :old`
  9. Same for: `rpg_locations`, `rpg_npcs`, `rpg_quests` (active/completed only), `rpg_relationships`
  10. InventoryItems follow characters automatically (FK to character_id, not session_id)
  11. Return new GameSession
- `get_previous_summaries(db, campaign_id, limit=3) -> list[str]` — for "Previously on..."

**Entity re-parenting detail** — SQL updates per table:
- `rpg_characters`: all characters (alive ones carry forward)
- `rpg_locations`: all locations (world map persists)
- `rpg_npcs`: all NPCs (they persist in the world)
- `rpg_quests`: active + completed quests (failed quests stay with old session)
- `rpg_relationships`: all relationships (knowledge graph carries forward)
- `rpg_inventory_items`: no direct update needed (FK to character_id, characters are re-parented)
- `game_memories`: NOT re-parented (historical, stay with original session for cross-session search)

---

### Step 5: Campaign Router

**New file**: `backend/app/routers/campaigns.py`

Endpoints:
- `GET /api/campaigns` — List campaigns (filter by `?status=active`)
- `POST /api/campaigns` — Create campaign
- `GET /api/campaigns/{id}` — Get campaign detail with session list
- `PATCH /api/campaigns/{id}` — Update name/description/status
- `DELETE /api/campaigns/{id}` — Delete campaign (cascades to sessions)
- `POST /api/campaigns/{id}/continue` — Continue campaign (creates new conversation + session, re-parents entities)

**File**: `backend/app/main.py` — Register `campaigns.router`.

---

### Step 6: Conversation Router Enhancement

**File**: `backend/app/routers/conversations.py`

Modify `list_conversations` to join GameSession and Campaign to populate `campaign_id`, `campaign_name`, `session_number` on each conversation response. This enables frontend grouping.

Modify `get_rpg_state` to include `campaign_id` and `campaign_name` in the response.

---

### Step 7: Builtin Tools — Campaign Lifecycle

**File**: `backend/app/services/builtin_tools/session.py`

Add two new tools:

**`start_campaign`**(campaign_name, world_name):
- Creates Campaign + sets `gs.campaign_id` on current session
- Returns type `"campaign_started"` with campaign_id, name, world_name

**`list_campaigns`**():
- Returns type `"campaign_list"` with available campaigns

**File**: `backend/app/services/builtin_tools/memory.py`

Modify `end_session`:
- After existing logic, if `gs.campaign_id` is set, include `campaign_id` and `campaign_name` in the response JSON so the user knows they can continue later

**File**: `backend/app/database.py` (`_builtin_tool_defs`):
- Add `start_campaign` and `list_campaigns` tool definitions

**File**: `backend/app/services/builtin_tools/__init__.py`:
- Register new tools in `BUILTIN_REGISTRY`

**File**: `backend/app/services/prompt_builder.py`:
- Add `start_campaign`, `list_campaigns` to `RPG_TOOL_NAMES` and `_CORE_TOOLS`

---

### Step 8: Prompt Builder — Campaign Context Injection

**File**: `backend/app/services/prompt_builder.py`

In `_build_layer3_state`, after existing world/location/party queries:

1. Check if `game_session.campaign_id` is set
2. If yes, query previous session summaries (limit 3, most recent first)
3. Prepend a compact "CAMPAIGN" section to the state block:
```
CAMPAIGN: Shadows of Eldenhollow | Session #3
PREVIOUSLY:
- Session 2: The party cleared the goblin caves and found a silver key.
- Session 1: Three adventurers met in Oakville and accepted a quest.
```
4. Budget: ~100-150 tokens max (truncate summaries if needed)

---

### Step 9: Cross-Session Memory Search

**File**: `backend/app/services/builtin_tools/memory.py`

Modify `search_memory`: When `session_range` is empty and the current session belongs to a campaign, auto-expand the search scope to all sessions in that campaign. Query campaign's session numbers and pass as `session_range`.

**File**: `backend/app/services/memory_service.py`

No changes needed — `search_with_stanford_scoring` already accepts `session_range` tuple. The campaign-aware `search_memory` tool passes the range.

---

### Step 10: Configuration

**File**: `backend/app/config.py`

```python
# Campaign persistence (Phase 5.1)
campaign_enabled: bool = True
campaign_recap_max_sessions: int = 3
```

---

### Step 11: Frontend — TypeScript Types

**File**: `frontend/src/types/index.ts`

Add:
```typescript
export interface Campaign {
  id: string;
  name: string;
  world_name: string;
  description: string;
  status: "active" | "completed";
  session_count: number;
  created_at: string;
  updated_at: string;
}

export interface CampaignSession {
  conversation_id: string;
  session_number: number;
  status: "active" | "ended";
  world_name: string;
  summary: string | null;
  created_at: string;
}

export interface CampaignDetail extends Campaign {
  sessions: CampaignSession[];
}
```

Extend existing `Conversation`:
```typescript
campaign_id?: string | null;
campaign_name?: string | null;
session_number?: number | null;
```

---

### Step 12: Frontend — API Client

**File**: `frontend/src/services/api.ts`

Add methods:
- `listCampaigns(): Promise<Campaign[]>`
- `getCampaign(id: string): Promise<CampaignDetail>`
- `createCampaign(data: { name: string; description?: string }): Promise<Campaign>`
- `updateCampaign(id: string, data): Promise<Campaign>`
- `deleteCampaign(id: string): Promise<void>`
- `continueCampaign(campaignId: string): Promise<{ conversation_id: string; session_number: number }>`

---

### Step 13: Frontend — Campaign Store

**New file**: `frontend/src/store/campaignStore.ts`

Zustand store following `chatStore.ts` pattern:
```typescript
interface CampaignState {
  campaigns: Campaign[];
  activeCampaignId: string | null;
  activeCampaignDetail: CampaignDetail | null;
  isLoading: boolean;

  loadCampaigns: () => Promise<void>;
  selectCampaign: (id: string) => Promise<void>;
  createCampaign: (name: string, description?: string) => Promise<Campaign>;
  continueCampaign: (campaignId: string) => Promise<string>; // returns new conversation_id
  clearSelection: () => void;
}
```

Auto-select campaign when `chatStore.activeConversationId` changes — subscribe to chatStore, look up `campaign_id` on active conversation.

---

### Step 14: Frontend — SessionDropdown Campaign Grouping

**File**: `frontend/src/components/layout/SessionDropdown.tsx`

Group conversations by campaign:
- Campaign-linked conversations grouped under collapsible amber campaign headers
- Each header shows: campaign name, session count
- Sessions within show: session number badge, title, status (active/ended)
- Standalone conversations appear under "Standalone" divider at bottom
- "New Campaign" button at bottom of dropdown

---

### Step 15: Frontend — TopBar Campaign Badge

**File**: `frontend/src/components/layout/TopBar.tsx`

- When active conversation has `campaign_name`: show amber badge `[Campaign Name > Session #N]`
- When session is ended and conversation has `campaign_id`: show "Continue Campaign" button (green accent)
- Add "New Campaign" option to the "+" button area

---

### Step 16: Frontend — GamePanel Campaign Section

**File**: `frontend/src/components/rpg/GamePanel.tsx`

Add campaign info section at top of panel (above World):
- Campaign name + "Session N of M"
- Collapsible session history with summaries
- "Continue Campaign" button when session is ended

---

### Step 17: Frontend — Tool Renderers

**New file**: `frontend/src/components/tools/renderers/CampaignRenderer.tsx`

Handle types: `campaign_started`, `campaign_list`, enhanced `session_ended` (with campaign info)

Register in `frontend/src/components/tools/renderers/index.ts`.

---

## Implementation Order

```
Backend (Steps 1-10):
  1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10

Frontend (Steps 11-17):
  11 → 12 → 13 → 14 → 15 → 16 → 17
```

Backend and frontend can be developed in sequence (backend first).

---

## Critical Files

| File | Action |
|------|--------|
| `backend/app/models/rpg.py` | Add Campaign model, campaign_id FK to GameSession |
| `backend/app/models/__init__.py` | Register Campaign |
| `backend/app/database.py` | Migration + tool seed defs |
| `backend/app/schemas/campaign.py` | **NEW** — Campaign Pydantic schemas |
| `backend/app/schemas/conversation.py` | Extend with campaign fields |
| `backend/app/services/campaign_service.py` | **NEW** — Campaign CRUD + continue logic |
| `backend/app/routers/campaigns.py` | **NEW** — Campaign API endpoints |
| `backend/app/routers/conversations.py` | Join campaign data in list/state endpoints |
| `backend/app/main.py` | Register campaigns router |
| `backend/app/services/builtin_tools/session.py` | Add start_campaign, list_campaigns tools |
| `backend/app/services/builtin_tools/memory.py` | Campaign-aware end_session + search_memory |
| `backend/app/services/builtin_tools/__init__.py` | Register new tools |
| `backend/app/services/prompt_builder.py` | Campaign context in Layer 3 + tool names |
| `backend/app/config.py` | Campaign config flags |
| `frontend/src/types/index.ts` | Campaign types + Conversation extension |
| `frontend/src/services/api.ts` | Campaign API methods |
| `frontend/src/store/campaignStore.ts` | **NEW** — Campaign Zustand store |
| `frontend/src/components/layout/SessionDropdown.tsx` | Campaign grouping |
| `frontend/src/components/layout/TopBar.tsx` | Campaign badge + continue button |
| `frontend/src/components/rpg/GamePanel.tsx` | Campaign info section |
| `frontend/src/components/tools/renderers/CampaignRenderer.tsx` | **NEW** — Campaign tool renderers |
| `frontend/src/components/tools/renderers/index.ts` | Register campaign renderers |

---

## Verification

### Backend Testing
1. Start backend: `cd backend && uvicorn app.main:app --reload`
2. Verify migration: Check `rpg_campaigns` table exists, `rpg_game_sessions` has `campaign_id` column
3. API test: `POST /api/campaigns` → `GET /api/campaigns` → verify campaign created
4. Tool test: In chat, say "start a campaign called Test" → verify `start_campaign` tool works
5. End + continue: End session → `POST /api/campaigns/{id}/continue` → verify new conversation created with entities carried over

### Frontend Testing (Chrome MCP)
1. Navigate to app, verify SessionDropdown shows campaign grouping
2. Create a campaign via chat ("start a campaign")
3. Play a session (create characters, explore locations)
4. End session → verify "Continue Campaign" button appears
5. Click continue → verify new conversation opens with same characters/locations/quests
6. Verify GamePanel shows campaign info and session history
7. Verify system prompt includes "Previously on..." context

### Cross-Session Memory Test
1. In session 1: archive an event, end session
2. Continue campaign to session 2
3. Use `search_memory` → verify it finds events from session 1
4. Verify prompt builder injects session 1 summary as campaign context
