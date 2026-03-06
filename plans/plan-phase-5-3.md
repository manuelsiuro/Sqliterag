# Phase 5.3: NPC Personality via Memory

> **Status**: Ready for implementation
> **Priority**: P2 | **Complexity**: Medium | **Dependency**: Phase 3 (complete), Phase 5.1 (complete)
> **Goal**: NPCs use their memory + relationship graph + persistent personality traits to generate contextual, evolving dialogue

---

## Context

Currently `talk_to_npc` returns a minimal roleplay hint: `"Respond as {name}. Disposition: {disp}. Familiarity: {fam}."` (~20 tokens). The LLM must infer personality entirely from the NPC's `description` field and any memories in the flat JSON array. There's no structured personality, no relationship context, and no cross-referencing with the GameMemory/knowledge graph systems built in Phases 2-3.

**Phase 5.3 enriches `talk_to_npc`** to build a rich personality profile (~150-200 tokens) from three sources:
1. **Structured personality traits** — new `personality` (JSON) and `backstory` fields on the NPC model
2. **NPC memories** — both the local `NPC.memory` JSON array AND relevant `GameMemory` entries (via Stanford scoring)
3. **Relationship graph** — direct edges from `rpg_relationships` showing who the NPC knows/trusts/fears

The prompt builder Layer 3 also gets enhanced to surface personality cues for NPCs at the current location, so the LLM has context even before `talk_to_npc` is called.

---

## Files to Modify

| # | File | Lines | Change |
|---|------|-------|--------|
| 1 | `backend/app/models/rpg.py` | 161-174 | Add `personality` (Text, JSON) and `backstory` (Text) columns to NPC |
| 2 | `backend/app/database.py` | 196, 636-654 | Add `_migrate_npcs_personality()` migration; update `create_npc`/`talk_to_npc` tool schemas |
| 3 | `backend/app/services/builtin_tools/npcs.py` | 14-109 | Enhance `create_npc` with personality/backstory params; rewrite `talk_to_npc` with enriched context |
| 4 | `backend/app/config.py` | 121 | Add `npc_personality_enabled` + tuning knobs |
| 5 | `backend/app/services/tool_service.py` | 20 | Add `"traits": "personality"` alias for `create_npc` |
| 6 | `backend/app/services/prompt_builder.py` | 381-397, 211-216 | Enhance Layer 3 NPC display + social phase rules |
| 7 | `backend/app/services/archivist_agent.py` | ~88 | Enhance prompt to encourage richer NPC memory recording |
| 8 | `backend/app/services/narrator_agent.py` | ~104 | Enhance prompt to instruct following NPC voice/personality |
| 9 | `frontend/src/components/tools/renderers/NPCRenderer.tsx` | 3-17, 93-138 | Add personality/backstory/relationships to interface + render them |

No new files needed.

---

## Implementation

### Step 1: Schema + Migration

**`backend/app/models/rpg.py`** — Add after line 171 (`memory` field):

```python
personality: Mapped[str] = mapped_column(Text, default="{}")  # JSON: {"traits":[], "voice":"", "motivation":"", "secrets":[]}
backstory: Mapped[str] = mapped_column(Text, default="")
```

**`backend/app/database.py`** — New migration function (after `_migrate_campaigns_table` at line 237):

```python
async def _migrate_npcs_personality(conn) -> None:
    """Add personality and backstory columns (Phase 5.3, idempotent)."""
    for col_name, col_type in [
        ("personality", "TEXT DEFAULT '{}'"),
        ("backstory", "TEXT DEFAULT ''"),
    ]:
        try:
            await conn.execute(text(f"ALTER TABLE rpg_npcs ADD COLUMN {col_name} {col_type}"))
            logger.info("Added column rpg_npcs.%s", col_name)
        except Exception:
            pass
```

Call at line 196 (after `_migrate_campaigns_table`):
```python
await _migrate_npcs_personality(conn)
```

**`backend/app/database.py`** — Update tool schema for `create_npc` (line 636-645):

```python
"create_npc": {
    "description": "Create a new NPC with name, description, personality traits, backstory, location, and disposition.",
    "parameters_schema": _schema(["name"], {
        "name": {"type": "string", "description": "NPC name."},
        "description": {"type": "string", "description": "Physical appearance and notable features."},
        "personality": {"type": "string", "description": "Personality as JSON '{\"traits\":[\"gruff\",\"loyal\"],\"voice\":\"gravelly\",\"motivation\":\"protect village\"}' or comma-separated 'gruff, loyal, suspicious'."},
        "backstory": {"type": "string", "description": "NPC's history and background."},
        "location": {"type": "string", "description": "Location name where the NPC is."},
        "disposition": {"type": "string", "description": "Attitude: hostile, unfriendly, neutral, friendly, helpful. Default: neutral."},
    }),
    "execution_type": "builtin",
    "execution_config": _config("create_npc"),
},
```

Update `talk_to_npc` description (line 647-654):

```python
"talk_to_npc": {
    "description": "Initiate conversation with an NPC. Returns personality profile, memories, relationships, and detailed roleplay guidance.",
    ...
},
```

### Step 2: Backend Logic

**`backend/app/services/builtin_tools/npcs.py`** — Enhance `create_npc` (lines 14-58):

Add `personality: str = ""` and `backstory: str = ""` parameters. Parse personality flexibly:

```python
async def create_npc(
    name: str = "", npc_name: str = "", description: str = "",
    location: str = "", disposition: str = "neutral",
    personality: str = "",   # NEW
    backstory: str = "",     # NEW
    *, session: AsyncSession, conversation_id: str,
) -> str:
    # ... existing name/session/location logic ...

    # Parse personality: JSON or comma-separated fallback
    personality_obj = {}
    if personality:
        try:
            personality_obj = json.loads(personality)
        except (json.JSONDecodeError, TypeError):
            personality_obj = {"traits": [t.strip() for t in personality.split(",") if t.strip()]}

    npc = NPC(
        session_id=gs.id, name=name, description=description,
        location_id=location_id, disposition=disposition,
        personality=json.dumps(personality_obj),  # NEW
        backstory=backstory,                       # NEW
    )
    # ... existing flush ...

    return json.dumps({
        # ... existing fields ...
        "personality": personality_obj,  # NEW
        "backstory": backstory,          # NEW
    })
```

**`backend/app/services/builtin_tools/npcs.py`** — Rewrite `talk_to_npc` (lines 61-109):

Add `embedding_service=None` to signature (injected via `inspect.signature` pattern in `tool_service.py`). Build enriched roleplay_hint from 5 sections:

```python
async def talk_to_npc(
    npc_name: str, topic: str = "",
    *, session: AsyncSession, conversation_id: str,
    embedding_service=None,  # NEW — for GameMemory search
) -> str:
    # ... existing NPC lookup + party member fallback (unchanged) ...

    memory = json.loads(npc.memory)
    personality = {}
    try:
        personality = json.loads(npc.personality) if npc.personality else {}
    except (json.JSONDecodeError, TypeError):
        pass

    from app.config import settings
    if not settings.npc_personality_enabled:
        # Fallback to original thin hint
        return json.dumps({
            "type": "npc_info", "name": npc.name, "description": npc.description,
            "disposition": npc.disposition, "familiarity": npc.familiarity,
            "topic": topic, "memory": memory,
            "roleplay_hint": f"Respond as {npc.name}. Disposition: {npc.disposition}. Familiarity: {npc.familiarity}.",
        })

    # === Build enriched roleplay_hint ===
    hint_parts = [f"You are {npc.name}."]

    # Section 1: Identity
    if npc.description:
        hint_parts.append(f"Appearance: {npc.description}")
    if npc.backstory:
        hint_parts.append(f"Background: {npc.backstory[:150]}")

    # Section 2: Personality
    traits = personality.get("traits", [])
    if traits:
        hint_parts.append(f"Personality: {', '.join(traits[:5])}")
    if personality.get("voice"):
        hint_parts.append(f"Voice/Speech: {personality['voice']}")
    if personality.get("motivation"):
        hint_parts.append(f"Motivation: {personality['motivation']}")
    secrets = personality.get("secrets", [])
    if secrets:
        hint_parts.append(f"Secrets (reveal only if trust is high): {'; '.join(secrets[:2])}")

    # Section 3: Disposition behavior
    _DISP_BEHAVIOR = {
        "hostile": "Hostile — refuse cooperation, threaten.",
        "unfriendly": "Unfriendly — terse, reluctant, demand favors.",
        "neutral": "Neutral — businesslike, direct, no warmth.",
        "friendly": "Friendly — warm, offer help, share gossip.",
        "helpful": "Helpful — eager to assist, share secrets.",
    }
    _FAM_BEHAVIOR = {
        "stranger": "First meeting — cautious, ask who they are.",
        "acquaintance": "Met before — recall previous encounters.",
        "friend": "Trusted — share freely, offer guidance.",
        "close_friend": "Deep bond — speak openly, offer personal favors.",
    }
    hint_parts.append(_DISP_BEHAVIOR.get(npc.disposition, ""))
    hint_parts.append(_FAM_BEHAVIOR.get(npc.familiarity, ""))

    # Section 4: Memories (NPC.memory + GameMemory search)
    max_local = settings.npc_max_local_memories
    relevant_memories = list(memory[-max_local:])

    if embedding_service and topic:
        try:
            from app.services.memory_service import search_with_stanford_scoring, get_memories_by_ids
            gs = await get_or_create_session(session, conversation_id)
            results = await search_with_stanford_scoring(
                session, f"{npc.name} {topic}",
                embedding_service=embedding_service,
                session_id=gs.id,
                top_k=settings.npc_memory_search_top_k,
            )
            if results:
                mems = await get_memories_by_ids(session, [mid for mid, _ in results])
                for m in mems:
                    relevant_memories.append(m.content[:100])
        except Exception:
            pass  # Memory search is supplementary

    if relevant_memories:
        hint_parts.append(f"You remember: {'; '.join(relevant_memories[:max_local + settings.npc_memory_search_top_k])}")

    # Section 5: Relationships from graph
    relationship_hints = []
    try:
        from app.models.rpg import Relationship
        from sqlalchemy import or_
        gs_obj = await get_or_create_session(session, conversation_id)
        rel_result = await session.execute(
            select(Relationship).where(
                Relationship.session_id == gs_obj.id,
                or_(
                    (Relationship.source_type == "npc") & (Relationship.source_id == npc.id),
                    (Relationship.target_type == "npc") & (Relationship.target_id == npc.id),
                ),
            ).order_by(Relationship.strength.desc()).limit(settings.npc_max_relationship_hints)
        )
        rels = rel_result.scalars().all()
        for r in rels:
            if r.source_id == npc.id:
                other = await resolve_entity_name(session, r.target_type, r.target_id)
                relationship_hints.append(f"{r.relationship.replace('_', ' ')} {other}")
            else:
                other = await resolve_entity_name(session, r.source_type, r.source_id)
                relationship_hints.append(f"{other} {r.relationship.replace('_', ' ')} you")
    except Exception:
        pass  # Relationship context is supplementary

    if relationship_hints:
        hint_parts.append(f"Relationships: {', '.join(relationship_hints)}")

    if topic:
        hint_parts.append(f"The adventurer asks about: {topic}")

    roleplay_hint = "\n".join(p for p in hint_parts if p)

    return json.dumps({
        "type": "npc_info",
        "name": npc.name, "description": npc.description,
        "disposition": npc.disposition, "familiarity": npc.familiarity,
        "topic": topic, "memory": memory,
        "personality": personality,           # NEW
        "backstory": npc.backstory or None,   # NEW
        "relationships": relationship_hints,   # NEW
        "roleplay_hint": roleplay_hint,        # ENRICHED
    })
```

**Import additions** for `npcs.py` — add `resolve_entity_name` to the `_common.py` imports (it's already exported from `rpg_service.py` and listed in `_common.py` line 31).

**`backend/app/config.py`** — Add after line 120 (campaign settings), before `# Server`:

```python
# NPC personality via memory (Phase 5.3)
npc_personality_enabled: bool = True
npc_memory_search_top_k: int = 3
npc_max_local_memories: int = 5
npc_max_relationship_hints: int = 4
```

**`backend/app/services/tool_service.py`** — Add alias at line 20:

```python
"create_npc": {"class": "char_class", "traits": "personality"},
```

### Step 3: Prompt Enhancements

**`backend/app/services/prompt_builder.py`** — Enhance Layer 3 NPC display (lines 381-397):

When listing NPCs at current location, append up to 2 personality traits:

```python
# Replace the NPC formatting loop with:
for n in npcs:
    entity_names[("npc", n.id)] = n.name
    traits_str = ""
    try:
        p = json.loads(n.personality) if n.personality else {}
        traits = p.get("traits", [])[:2]
        if traits:
            traits_str = f", {'/'.join(traits)}"
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass
    npc_parts.append(f"{n.name} ({n.disposition}{traits_str})")
```

This changes e.g. `"Grim (friendly)"` → `"Grim (friendly, gruff/loyal)"` at ~5 extra tokens per NPC.

**Social phase rules** (lines 211-216) — update to reference enriched roleplay_hint:

```python
_SOCIAL_RULES = (
    "SOCIAL PHASE:\n"
    "- Use talk_to_npc for dialogue — it returns a detailed roleplay_hint with personality, memories, and relationships.\n"
    "- Follow the roleplay_hint closely: match the NPC's voice, traits, and disposition in dialogue.\n"
    "- Reference NPC memories when relevant to the conversation topic.\n"
    "- Use update_npc_relationship when disposition changes.\n"
)
```

**`backend/app/services/archivist_agent.py`** — Add to Layer 1 prompt (~line 88):

```
"- Use npc_remember to record events NPCs witnessed AND their emotional reactions.\n"
```

**`backend/app/services/narrator_agent.py`** — Add to Layer 1 prompt (~line 104):

```
"- Voice NPCs with distinct personalities: follow the roleplay_hint from talk_to_npc for voice, traits, and manner.\n"
```

### Step 4: Frontend

**`frontend/src/components/tools/renderers/NPCRenderer.tsx`** — Update `NPCData` interface (lines 3-17):

```typescript
interface NPCData {
  name: string;
  description: string;
  disposition: string;
  familiarity: string;
  location?: string;
  topic?: string;
  memory: string[];
  memory_added?: string;
  total_memories?: number;
  roleplay_hint?: string;
  changes?: string[];
  is_party_member?: boolean;
  error?: string;
  // Phase 5.3
  personality?: {
    traits?: string[];
    voice?: string;
    motivation?: string;
    secrets?: string[];
  };
  backstory?: string;
  relationships?: string[];
}
```

Add **personality trait pills** after description block (after line 93):

```tsx
{/* Personality Traits */}
{d.personality?.traits && d.personality.traits.length > 0 && (
  <div className="flex flex-wrap gap-1">
    {d.personality.traits.slice(0, 5).map((trait, i) => (
      <span key={i} className="text-[10px] px-1.5 py-0.5 rounded-full bg-purple-900/25 text-purple-300 border border-purple-700/25">
        {trait}
      </span>
    ))}
    {d.personality.voice && (
      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-indigo-900/25 text-indigo-300 border border-indigo-700/25">
        🗣 {d.personality.voice}
      </span>
    )}
  </div>
)}
```

Add **backstory** below traits (truncated):

```tsx
{d.backstory && (
  <div className="text-[10px] text-gray-500 bg-gray-800/30 rounded px-2 py-1 border border-gray-700/20">
    {d.backstory.length > 120 ? d.backstory.slice(0, 117) + "..." : d.backstory}
  </div>
)}
```

Add **relationships section** before memory block (before line 124):

```tsx
{/* Relationships */}
{d.relationships && d.relationships.length > 0 && (
  <div className="space-y-0.5">
    <div className="text-[10px] text-gray-500 font-medium">Relationships</div>
    {d.relationships.slice(0, 4).map((r, i) => (
      <div key={i} className="text-[11px] text-cyan-300/70 pl-2 border-l-2 border-cyan-700/30">
        {r}
      </div>
    ))}
  </div>
)}
```

All new fields are optional — existing NPCs without personality render exactly as before.

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Old NPC (no personality/backstory columns) | Migration adds defaults `'{}'` and `''`; renderer skips empty sections |
| LLM sends `personality` as plain string | Parsed as comma-separated trait list: `"gruff, loyal"` → `{"traits":["gruff","loyal"]}` |
| LLM sends `traits` instead of `personality` | Alias in `tool_service.py` remaps it |
| `embedding_service` unavailable | Skips GameMemory search; uses only NPC.memory array |
| `npc_personality_enabled = False` | Falls back to original thin roleplay_hint (full backward compat) |
| NPC has no memories or relationships | Those sections simply omitted from roleplay_hint |
| Very long backstory | Truncated to 150 chars in roleplay_hint; 120 chars in frontend |
| `talk_to_npc` with no topic | Skips GameMemory search (needs topic for relevance); includes local memories only |
| Party member fallback path | Unchanged — returns thin hint with `is_party_member: true` |

---

## Verification

1. **Backend startup**: `cd backend && uvicorn app.main:app --reload` — check logs for `Added column rpg_npcs.personality` migration
2. **Create NPC with personality**: In chat, ask DM to create an NPC — verify `create_npc` call includes personality traits in the tool result JSON
3. **Talk to NPC**: Call `talk_to_npc` — verify enriched `roleplay_hint` in tool result with personality, memories, relationships sections
4. **LLM dialogue quality**: Verify the LLM generates dialogue matching the NPC's personality traits and voice
5. **Frontend rendering**: Chrome MCP screenshot — verify personality trait pills (purple), backstory text, and relationships section (cyan) appear in NPC card
6. **Backward compatibility**: Talk to an existing NPC (no personality) — verify it renders without errors
7. **Config toggle**: Set `NPC_PERSONALITY_ENABLED=false` — verify fallback to thin roleplay_hint
8. **Type check**: `cd frontend && npx tsc --noEmit` — no TypeScript errors
