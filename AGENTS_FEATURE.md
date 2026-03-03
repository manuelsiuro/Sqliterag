# Agents Feature: Research & Architecture Document

> **Purpose**: Comprehensive research document synthesizing codebase analysis, academic papers, and industry best practices to define a roadmap for improving D&D gameplay in sqliteRAG. This document is the foundation for future development tasks.
>
> **Date**: March 2026 | **Model Target**: qwen3.5:9b | **Current Tools**: 41 RPG tools

---

## Table of Contents

1. [Current System Analysis](#1-current-system-analysis)
2. [Key Problems Identified](#2-key-problems-identified)
3. [Multi-Agent Architecture](#3-multi-agent-architecture)
4. [Enhanced RAG for Game Memory](#4-enhanced-rag-for-game-memory)
5. [Knowledge Graph for World State](#5-knowledge-graph-for-world-state)
6. [Context Engineering](#6-context-engineering)
7. [Ollama Optimizations](#7-ollama-optimizations)
8. [Enhanced System Prompt](#8-enhanced-system-prompt)
9. [Proposed Development Tasks](#9-proposed-development-tasks)
10. [Research Sources](#10-research-sources)

---

## 1. Current System Analysis

### Architecture Overview

sqliteRAG is a local-first D&D 5e game engine built on:

- **Backend**: Python/FastAPI with async SQLite (aiosqlite)
- **Frontend**: React 19 + TypeScript + Zustand + Tailwind CSS
- **LLM**: Ollama (local models, default `llama3.2`)
- **Embeddings**: `nomic-embed-text` via Ollama (768-dimensional vectors)
- **Vector Search**: sqlite-vec extension for cosine similarity
- **Streaming**: Server-Sent Events (SSE) via `@microsoft/fetch-event-source`

### The 41 RPG Tools (9 Phases)

| Phase | Category | Count | Tools |
|-------|----------|-------|-------|
| 0 | Original | 1 | `roll_d20` |
| 1 | Dice & Math | 3 | `roll_dice`, `roll_check`, `roll_save` |
| 2 | Characters | 4 | `create_character`, `get_character`, `update_character`, `list_characters` |
| 3 | Combat | 10 | `start_combat`, `get_combat_status`, `next_turn`, `end_combat`, `attack`, `cast_spell`, `heal`, `take_damage`, `death_save`, `combat_action` |
| 4 | Inventory | 6 | `create_item`, `give_item`, `equip_item`, `unequip_item`, `get_inventory`, `transfer_item` |
| 5 | World | 5 | `create_location`, `connect_locations`, `move_to`, `look_around`, `set_environment` |
| 6 | NPCs | 4 | `create_npc`, `talk_to_npc`, `update_npc_relationship`, `npc_remember` |
| 7 | Quests | 4 | `create_quest`, `update_quest_objective`, `complete_quest`, `get_quest_journal` |
| 8 | Rest | 2 | `short_rest`, `long_rest` |
| 9 | Session | 2 | `init_game_session`, `get_game_state` |

All tools are registered in `BUILTIN_REGISTRY` in `backend/app/services/builtin_tools.py` (lines 1806-1859). Each is an async Python function with parameters extracted from function signatures and converted to Ollama's tool calling format.

### Agent Loop (`chat_service.py`)

```
stream_chat(conversation_id, model, user_message, options)
  ├─ Load full conversation history from database (no truncation)
  ├─ Try RAG context injection (if documents available)
  ├─ Load conversation tools
  ├─ If RPG tools detected → inject RPG_SYSTEM_PROMPT
  └─ Agent Loop (MAX_TOOL_ROUNDS = 10, non-streaming)
       ├─ Call LLM with messages + tools
       ├─ If tool_calls → execute each tool → save result → append to messages → loop
       └─ If no tool_calls → stream final response to client via SSE
```

### RAG System (`rag_service.py`)

- **Chunking**: `RecursiveCharacterTextSplitter` — 500 chars, 50 char overlap
- **Storage**: `document_chunks` table + `vec_chunks` virtual table (sqlite-vec, float[768])
- **Retrieval**: Vector similarity search, top_k=5, chunks joined with `"\n---\n"`
- **Injection**: RAG context prepended as system message before each chat request
- **File Types**: PDF (pypdf) and plain text

### Database Schema (17 tables)

**Core**: `conversations`, `messages`, `tools`, `conversation_tools`, `documents`, `document_chunks`, `vec_chunks`

**RPG**: `rpg_game_sessions`, `rpg_characters`, `rpg_items`, `rpg_inventory_items`, `rpg_locations`, `rpg_npcs`, `rpg_quests`

Key relationships:
- `rpg_game_sessions` has 1:1 with `conversations`
- Characters, NPCs, Locations, Quests all scoped to a game session
- NPC memory stored as JSON array of events
- Combat state stored as JSON on the session
- Character conditions, spell slots, death saves stored as JSON

### Current System Prompt

```
You are a Dungeon Master running a D&D 5e game. You have access to RPG tools
that enforce game rules. IMPORTANT RULES:
- Always use the tools to modify game state. Never just narrate mechanical changes.
- Use create_character before referencing a character in other tools.
- Use roll_check / roll_save for ability checks and saves — don't invent results.
- Use the attack tool for combat attacks — don't narrate hit/miss without rolling.
- Track HP, conditions, and spell slots through the tools.
- Narrate results dramatically after receiving tool output.
- When starting a new game, use init_game_session first.
```

---

## 2. Key Problems Identified

### P1: No Long-Term Memory

The system sends the **entire conversation history** to the LLM each turn (`chat_service.py` lines 76-81). There is no summarization, truncation, or memory tier. After 20-30 exchanges with tool calls, the context window overflows silently — the model loses coherence, forgets character names, and contradicts earlier narrative.

**Impact**: Sessions longer than ~15 minutes become incoherent. The model cannot recall events from earlier in the same session, let alone across sessions.

### P2: No Context Window Management

There is zero token counting or budget enforcement. The system blindly appends:
- System prompt (~130 tokens)
- RAG context (variable, unbounded)
- 41 tool definitions (~2,000-3,000 tokens)
- Full conversation history (grows linearly)
- Expects response space

With a `num_ctx` of 8192, the model gets squeezed out of its own response space after just a few exchanges with tool calls.

### P3: Basic System Prompt

The current prompt is a flat 130-token string. It lacks:
- Dynamic state injection (current location, party status, active quests)
- Conditional rules (combat-specific rules only during combat)
- Response format enforcement (the model sometimes responds without using tools)
- Game phase awareness (exploration vs. combat vs. social)

### P4: All 41 Tools Always Active

Every RPG tool is sent to the model every turn, consuming ~2,000-3,000 tokens of context window. During exploration, the model sees combat tools it doesn't need. During social encounters, it sees inventory management tools. This wastes tokens and confuses smaller models — research shows tool selection accuracy degrades with tool count.

### P5: No Cross-Session Continuity

Each conversation is isolated. There is no mechanism to:
- Resume a campaign across sessions
- Carry over world state, character progress, or NPC relationships
- Build on accumulated lore or player decisions

### P6: Flat RAG With No Game Awareness

The RAG system treats all documents equally. There is no distinction between:
- D&D rules (procedural knowledge)
- Session events (episodic memory)
- World lore (semantic knowledge)

Retrieval is pure vector similarity with no metadata filtering, no recency weighting, and no importance scoring.

### P7: No Structured World Model

While the database has tables for locations, NPCs, and quests, there is no explicit **relationship graph** connecting them. The model cannot efficiently answer questions like "Who knows about the missing amulet?" or "What locations are connected to the thieves' guild?"

---

## 3. Multi-Agent Architecture

### Research Foundation

The **ChatRPG study** — "Static Vs. Agentic Game Master AI for Facilitating Solo Role-Playing Experiences" (Jorgensen et al., Aalborg University, 2025, accepted ACM CUI 2025) — provides the strongest empirical evidence for multi-agent RPG systems.

**Key result**: The agentic multi-agent system (v2) achieved a **+243% improvement in mastery** over the static prompt-engineered system (v1), with statistical significance (t = -3.683, p = 0.004, n=12 within-subjects).

Full quantitative results (paired t-tests):

| Metric | Static (v1) | Agentic (v2) | Improvement | p-value |
|--------|-------------|--------------|-------------|---------|
| **Mastery** | **0.68** | **2.33** | **+243%** | **0.004** |
| Goals and rules | 1.35 | 2.39 | +77% | 0.018 |
| Ease of control | 2.08 | 2.81 | +35% | 0.012 |
| Curiosity | 1.83 | 2.57 | +40% | 0.047 |
| Immersion | 1.64 | 2.42 | +48% | 0.034 |
| Story quality | 1.17 | 2.33 | +99% | 0.019 |
| Coherent story | 1.00 | 2.25 | +125% | 0.040 |
| Replay likelihood | 1.58 | 2.50 | +58% | 0.050 |
| Satisfaction | 1.08 | 2.17 | +101% | 0.047 |

**Paper**: [arXiv:2502.19519](https://arxiv.org/abs/2502.19519)
**Code**: [github.com/KarmaKamikaze/ChatRPG](https://github.com/KarmaKamikaze/ChatRPG)

### Recommended Architecture: Narrator + Archivist + Rules Engine

Based on the ChatRPG study, the "Labyrinth" function-calling paper (Song et al., 2024), and the AIDM project, we recommend a **three-agent pipeline**:

```
Player Input
    │
    ▼
┌─────────────┐
│   NARRATOR   │  Primary agent — storytelling, dialogue, scene description
│  (qwen3.5:9b)│  Tools: look_around, talk_to_npc, set_environment, move_to
│              │  Receives: game state summary, relevant memories, active quest context
└──────┬───────┘
       │
       ▼
┌─────────────┐
│  RULES       │  Mechanical agent — dice, combat, character management
│  ENGINE      │  Tools: roll_dice, attack, cast_spell, heal, take_damage,
│  (qwen3.5:9b)│  create_character, update_character, start_combat, etc.
│              │  Receives: narrator's action requests, current character/combat state
└──────┬───────┘
       │
       ▼
┌─────────────┐
│  ARCHIVIST   │  Memory agent — state persistence, summarization, retrieval
│  (qwen3.5:9b)│  Tools: npc_remember, update_npc_relationship, update_quest_objective,
│              │  + new memory tools (archive_event, summarize_session, search_memory)
│              │  Receives: all tool results, generates state updates and memory entries
└──────┬───────┘
       │
       ▼
  Final Response → Player
```

### Why Three Agents (Not Two or Five)

- **Two agents** (ChatRPG v2): Proven effective but the Narrator handles both storytelling and rules, leading to rule-bending for narrative convenience.
- **Three agents** (our proposal): Separates rules enforcement from narrative, preventing the DM from fudging dice. The Archivist maintains memory independently.
- **Five+ agents** (AIDM, SENNA): More granular but significantly more complex to orchestrate and slower with local models. Better suited for cloud APIs.

### Supporting Research

| Project | Architecture | Validated? | Key Finding |
|---------|-------------|-----------|-------------|
| ChatRPG v2 | 2-agent (Narrator + Archivist) | Yes (n=12, p<0.05) | +243% mastery, +125% coherence |
| Song et al. 2024 | Function-calling LLM | Yes (n=144 transcripts) | Both dice + state functions score 4.39/5.0 consistency |
| AIDM | 24+ agents with orchestrator | No (open-source) | ChromaDB memory, per-agent model selection |
| CALYPSO | Multi-module DM assistant | Yes (AIIDE 2023) | High/low fidelity output distinction |
| D&D Agents (NeurIPS 2025) | Multi-agent combat sim | Yes | Claude 3.5 Haiku most reliable for tool use |
| FIREBALL | Dataset + state tracking | Yes (25K sessions) | LLMs with state info > dialog history alone |
| Generative Agents | 25 agents in RPG town | Yes (Stanford/Google) | Memory stream + reflection + retrieval |

### Communication Pattern: Sequential Pipeline with Shared State

Based on the research, the most reliable pattern for local models is a **sequential pipeline** where:
1. Each agent processes in turn (not concurrent)
2. All agents read/write to a **shared SQLite state** (existing RPG tables)
3. The orchestrator in `chat_service.py` manages the pipeline
4. Tool results from one agent flow as context to the next

This avoids the complexity of message-passing between concurrent agents while maintaining clear separation of concerns.

### Incremental Migration Path

Phase 1 can be implemented without multi-agent by simply improving the single agent (better prompt, context management, dynamic tools). Multi-agent can be Phase 3+ once the foundation is solid.

---

## 4. Enhanced RAG for Game Memory

### Three-Tier Memory Architecture

Drawing from cognitive psychology and the Stanford Generative Agents paper (Park et al., 2023), game memory should be partitioned into three tiers:

#### Procedural Memory (Rules & Mechanics)

**What**: D&D 5e rules, spell descriptions, class features, monster stat blocks, house rules.
**Storage**: RAG document chunks with `memory_type = 'procedural'`.
**Retrieval**: JIT (just-in-time) — only inject relevant rules when the game phase demands them.
**Persistence**: Immutable. Loaded from uploaded PDFs/documents. Never evicted.
**Token budget**: ~500 tokens per turn.

#### Episodic Memory (Session Events)

**What**: What happened, when, to whom. Combat outcomes, player decisions, NPC encounters, quest progress.
**Storage**: New `game_memories` table with timestamps, importance scores, and entity tags.
**Retrieval**: Recency-weighted + importance-scored + relevance-matched (Stanford formula).
**Persistence**: Full detail for current session, progressively summarized for older sessions.
**Token budget**: ~800 tokens per turn.

#### Semantic Memory (World Knowledge)

**What**: NPC backstories, location lore, faction relationships, world history, accumulated player knowledge.
**Storage**: RAG chunks with `memory_type = 'semantic'` + knowledge graph edges.
**Retrieval**: Entity-triggered — when an NPC is mentioned, retrieve their backstory and relationships.
**Persistence**: Grows over time. Summarized but never deleted.
**Token budget**: ~400 tokens per turn.

### Stanford Retrieval Scoring Formula

From the Generative Agents paper (arXiv:2304.03442):

```
retrieval_score = α_recency × recency + α_importance × importance + α_relevance × relevance
```

- **Recency**: Exponential decay with factor 0.995 per game-hour since last access
- **Importance**: Integer 1-10 assigned by the LLM (e.g., "a merchant greets you" = 2, "the dragon attacks" = 9)
- **Relevance**: Cosine similarity between memory embedding and current query
- **Normalization**: All scores min-max scaled to [0, 1]
- **Alpha weights**: Start at 1.0 each, tune based on gameplay quality

### Hybrid Search: sqlite-vec + FTS5

The current system uses vector-only search. Research shows **Reciprocal Rank Fusion (RRF)** combining FTS5 full-text search with sqlite-vec vector search significantly improves retrieval quality (Alex Garcia, 2024).

**Why both?** Vector search captures semantic meaning ("the party fought monsters" matches "combat encounter") but misses exact terms. FTS5 captures exact names ("Thordak", "Silverdale") that vector search might confuse with similar-sounding entities.

#### RRF Implementation (from Alex Garcia)

```sql
WITH vec_matches AS (
  SELECT chunk_id, row_number() OVER (ORDER BY distance) AS rank_number
  FROM vec_chunks
  WHERE embedding MATCH :query_embedding AND k = :k
),
fts_matches AS (
  SELECT rowid, row_number() OVER (ORDER BY rank) AS rank_number
  FROM fts_chunks
  WHERE content MATCH :query_text LIMIT :k
),
final AS (
  SELECT
    chunks.id, chunks.content,
    (COALESCE(1.0 / (60 + fts_matches.rank_number), 0.0) * :weight_fts +
     COALESCE(1.0 / (60 + vec_matches.rank_number), 0.0) * :weight_vec
    ) AS combined_rank
  FROM fts_matches
  FULL OUTER JOIN vec_matches ON vec_matches.chunk_id = fts_matches.rowid
  JOIN game_memories chunks ON chunks.id = COALESCE(fts_matches.rowid, vec_matches.chunk_id)
  ORDER BY combined_rank DESC
)
SELECT * FROM final LIMIT :top_k;
```

Parameters: `rrf_k = 60`, `weight_fts = 0.4`, `weight_vec = 0.6` (tune based on results).

**Reference**: [alexgarcia.xyz/blog/2024/sqlite-vec-hybrid-search](https://alexgarcia.xyz/blog/2024/sqlite-vec-hybrid-search/index.html)

### Session Summarization

Drawing from "Recursively Summarizing Enables Long-Term Dialogue Memory" (arXiv:2308.15022) and the H-MEM hierarchical memory system (arXiv:2507.22925):

**Four-level hierarchy**:
1. **Turn-level**: Raw messages (full detail, current session only)
2. **Encounter-level**: "The party defeated 3 goblins in the cave. Arin took 12 damage. Found a silver key."
3. **Session-level**: "Session 3: Cleared goblin caves, found the missing merchant's silver key, learned the thieves' guild operates from the sewers."
4. **Campaign-level**: "The heroes are investigating kidnappings in Silverdale. They've traced the plot to a thieves' guild with connections to a mysterious patron."

**Trigger**: Summarize at end of each session, or when context reaches 70% capacity (MemGPT pattern).

### MemGPT-Style Context Management

From MemGPT (Packer et al., UC Berkeley, arXiv:2310.08560), now the Letta framework:

1. **Warning at 70%**: When prompt tokens exceed 70% of context window, insert a system warning
2. **Flush at 100%**: Queue manager flushes ~50% of oldest messages
3. **Recursive summary**: Evicted messages replaced with summary combining evicted content + previous summary
4. **Recall storage**: All evicted messages stored searchable in database
5. **Self-directed memory**: LLM uses tool calls to search/retrieve old context on demand

New tools to add:
- `archive_event(description, importance)` — store important events in long-term memory
- `search_memory(query, memory_type)` — retrieve relevant memories
- `get_session_summary(session_id)` — retrieve past session summaries

### Metadata Schema for Game Memories

```sql
CREATE TABLE game_memories (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES rpg_game_sessions(id),
    memory_type TEXT NOT NULL,  -- 'procedural' | 'episodic' | 'semantic'
    entity_type TEXT,           -- 'character' | 'location' | 'npc' | 'quest' | 'item' | 'event'
    content TEXT NOT NULL,
    importance_score REAL DEFAULT 0.5,  -- 0.0 to 1.0
    session_number INTEGER,
    entity_names TEXT,          -- JSON array of entity names mentioned
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE VIRTUAL TABLE fts_memories USING fts5(content, entity_names);
-- vec_memories created with sqlite-vec for embeddings
```

---

## 5. Knowledge Graph for World State

### The Problem

The current relational schema stores entities (characters, NPCs, locations, quests, items) in separate tables with limited cross-referencing. NPC memory is a flat JSON array. There's no way to query "What does Gundren know about the missing amulet?" or "What locations are connected to the thieves' guild?" without loading everything and letting the LLM figure it out.

### Lightweight Graph Overlay on SQLite

Rather than replacing the existing schema, add a **relationship table** as a graph overlay, inspired by the [simple-graph-sqlite](https://github.com/dpapathanasiou/simple-graph) pattern:

```sql
CREATE TABLE rpg_relationships (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES rpg_game_sessions(id),
    source_type TEXT NOT NULL,   -- 'character', 'npc', 'location', 'quest', 'item'
    source_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relationship TEXT NOT NULL,  -- 'knows_about', 'located_at', 'enemy_of', 'allied_with',
                                 -- 'quest_giver', 'guards', 'owns', 'fears', 'seeks'
    strength INTEGER DEFAULT 50, -- 0-100 (0 = weak, 100 = defining)
    metadata TEXT DEFAULT '{}',  -- JSON: additional context, timestamps, evidence
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rel_source ON rpg_relationships(session_id, source_type, source_id);
CREATE INDEX idx_rel_target ON rpg_relationships(session_id, target_type, target_id);
CREATE INDEX idx_rel_type ON rpg_relationships(session_id, relationship);
```

### Relationship Types

| Category | Relationships | Example |
|----------|--------------|---------|
| Social | `knows`, `allied_with`, `enemy_of`, `fears`, `trusts`, `employs` | Gundren `trusts` → Arin |
| Spatial | `located_at`, `connected_to`, `guards`, `hidden_in` | Dragon `guards` → Cave |
| Quest | `quest_giver`, `seeks`, `requires`, `rewards` | Merchant `quest_giver` → Find Amulet |
| Ownership | `owns`, `carries`, `created` | Arin `owns` → Silver Sword |
| Knowledge | `knows_about`, `witnessed`, `suspects` | Bartender `knows_about` → Thieves' Guild |
| Temporal | `happened_before`, `caused`, `resulted_in` | Cave Battle `caused` → Dragon Awakening |

### Graph Traversal with Recursive CTEs

SQLite's recursive CTEs enable multi-hop graph queries:

```sql
-- Find all entities connected to "Thieves' Guild" within 2 hops
WITH RECURSIVE connected(entity_type, entity_id, depth, path) AS (
    SELECT target_type, target_id, 1,
           source_type || ':' || source_id || ' -> ' || target_type || ':' || target_id
    FROM rpg_relationships
    WHERE source_id = :thieves_guild_id AND session_id = :session_id
    UNION ALL
    SELECT r.target_type, r.target_id, c.depth + 1,
           c.path || ' -> ' || r.target_type || ':' || r.target_id
    FROM rpg_relationships r
    JOIN connected c ON r.source_id = c.entity_id
    WHERE c.depth < 2
    AND c.path NOT LIKE '%' || r.target_id || '%'  -- prevent cycles
)
SELECT DISTINCT entity_type, entity_id, depth, path FROM connected;
```

### Context Injection from Graph

When the player interacts with an entity, retrieve its subgraph and inject a compact summary:

```
WORLD STATE:
- Location: Rusty Tavern (town, connected: Market Square[E], Docks[S])
- NPCs here: Bartender Grim (friendly, knows_about: Thieves' Guild, Merchant disappearance)
- Active quest: Find Missing Merchant (objective: investigate tavern rumors [incomplete])
- Party: Arin L3 Fighter HP:28/28, carrying: Silver Sword, Healing Potion x2
```

### New Tools for Graph Management

- `add_relationship(source, target, relationship, strength)` — create/update a graph edge
- `query_relationships(entity, depth=1)` — retrieve an entity's relationship subgraph
- `get_entity_context(entity)` — compile a compact context summary from graph + memories

### GraphRAG Integration

Following [Stephen Collins' GraphRAG with SQLite guide](https://dev.to/stephenc222/how-to-build-lightweight-graphrag-with-sqlite-53le):

1. Extract entities and relationships from game events (LLM-assisted or rule-based)
2. Store in `rpg_relationships` table
3. At retrieval time, identify mentioned entities → query their subgraph → inject as structured context
4. This complements vector-based RAG with structured relational context

---

## 6. Context Engineering

### The 8192-Token Budget

With `num_ctx: 8192` on qwen3.5:9b, every token counts. Here is the recommended allocation:

| Component | Tokens | % | Notes |
|-----------|--------|---|-------|
| System Prompt (core) | 250 | 3% | Identity + rules contract + response format |
| State Injection | 200 | 2.5% | Compact game state from graph/DB |
| JIT Rules | 0-200 | 0-2.5% | Conditional (combat, spells, social) |
| Tool Definitions | 400-800 | 5-10% | Only active-phase tools (not all 41) |
| RAG Context | 1,000-1,700 | 12-21% | Three-tier memory (procedural + episodic + semantic) |
| Conversation History | 1,500-2,500 | 18-30% | Summarized older + recent raw turns |
| **Response Reserve** | **2,000** | **24%** | Must be reserved, not filled by input |
| Safety Buffer | 300 | 4% | Prevents overflow edge cases |

**Total input budget**: ~5,900 tokens (72% of 8192)
**Response budget**: ~2,300 tokens (28%)

### Dynamic Tool Injection

Instead of sending all 41 tools every turn, inject only tools relevant to the current game phase:

| Game Phase | Tools Injected | Approximate Tokens |
|-----------|---------------|-------------------|
| Exploration | `look_around`, `move_to`, `create_location`, `connect_locations`, `set_environment`, `talk_to_npc`, `create_npc` | ~400 |
| Combat | `attack`, `cast_spell`, `heal`, `take_damage`, `death_save`, `combat_action`, `next_turn`, `end_combat`, `get_combat_status` | ~500 |
| Social | `talk_to_npc`, `update_npc_relationship`, `npc_remember`, `create_npc` | ~250 |
| Inventory | `create_item`, `give_item`, `equip_item`, `unequip_item`, `get_inventory`, `transfer_item` | ~350 |
| Rest/Camp | `short_rest`, `long_rest`, `get_game_state`, `get_quest_journal` | ~200 |
| Session Start | `init_game_session`, `create_character`, `create_location` | ~200 |

**Always available**: `roll_dice`, `roll_check`, `roll_save`, `get_character`, `update_character` (~300 tokens)

Detection logic: Check `combat_state` for combat, use LLM intent classification or keyword heuristics for other phases.

### Conversation History Management

Implement a **sliding window with recursive summarization** (MemGPT pattern):

1. Keep the **last 4-6 message pairs** in full (user + assistant + tool results)
2. **Summarize** older exchanges into a rolling summary (~200 tokens)
3. **Trigger summarization** when history exceeds 70% of its budget (~1,750 tokens)
4. **Flush** oldest messages when at 100%, replacing with recursive summary
5. Store all messages in the database for recall

### Token Counting

Add approximate token counting (character-based heuristic is sufficient):

```python
def estimate_tokens(text: str) -> int:
    """Approximate token count. ~4 chars per token for English."""
    return len(text) // 4 + 1
```

For tool definitions, pre-calculate token cost at registration time and cache it.

### Token-Efficient Formatting

Research shows bullet points use ~70-80% of the tokens that prose uses, and abbreviated key-value format uses even less:

```
# BEFORE (~120 tokens):
"The current game state is as follows: The party is currently located at the
Rusty Tavern. The party consists of Arin who is a Level 3 Fighter with 28
out of 28 hit points..."

# AFTER (~50 tokens):
"STATE: loc=Rusty Tavern | party=[Arin L3 Fighter HP:28/28] | combat=false |
quests=[Find Amulet(active)]"
```

**Reference**: [TOON Format](https://toonformat.dev/) achieves 40-60% fewer tokens than JSON for tabular data.

---

## 7. Ollama Optimizations

### Model Recommendations

#### Primary Agent: qwen3.5:9b

| Parameter | Value | Source |
|-----------|-------|--------|
| Parameters | 9 billion | HuggingFace |
| Context Window | 262,144 native | HuggingFace |
| Tool Calling | Strong (BFCL-V4 benchmark) | Qwen team |
| GPQA Diamond | 81.7 (beats gpt-oss-120B) | VentureBeat |
| Release | March 2026 | Qwen 3.5 Small Series |
| Focus | Agentic use cases, automation | HuggingFace |

qwen3.5:9b is specifically optimized for agentic/tool-calling workloads and outperforms the previous Qwen3-30B on most benchmarks while being far smaller.

#### Embedding Model: nomic-embed-text (v1.5 recommended)

| Parameter | Value |
|-----------|-------|
| Parameters | 137M |
| Dimensions | 768 (or 256 with Matryoshka truncation) |
| Max Tokens | 8,192 |
| MTEB Score | 62.28 (768d) / 61.04 (256d) |

**Critical**: nomic-embed-text requires task prefixes:
- `search_document: <text>` — when embedding documents/chunks
- `search_query: <text>` — when embedding queries at retrieval time

Without these prefixes, retrieval quality degrades significantly.

**Matryoshka optimization**: Using 256 dimensions instead of 768 gives 3x storage savings and faster distance calculations with only 1.24 MTEB points penalty. This is the recommended configuration.

### Ollama Parameters for qwen3.5:9b

```python
# Recommended parameters
{
    "num_ctx": 8192,          # Context window (limit to save VRAM)
    "temperature": 0.7,       # CRITICAL: Do NOT use 0 with Qwen3 family
    "top_p": 0.8,             # Nucleus sampling
    "top_k": 20,              # Top-K sampling
    "repeat_penalty": 1.0,    # Default
    "presence_penalty": 1.5,  # Prevents repetition (recommended by Qwen team)
    "num_predict": 2048,      # Max output tokens
}
```

**WARNING**: Qwen3 model cards explicitly warn that temperature=0 (greedy decoding) leads to performance degradation and endless repetitions. Always use temperature >= 0.6.

### Thinking Mode

For tool calling, **disable thinking mode** to save tokens:
- Include `/nothink` in the system prompt
- Or set `think: false` in the Ollama API call
- Thinking mode wastes context window tokens and is unnecessary for structured tool calls
- Known issue: Some Qwen3 versions still produce `<think>` tags; strip them in post-processing

### Structured Output

For enforcing JSON output format:

```python
response = await ollama.chat(
    model="qwen3.5:9b",
    messages=messages,
    tools=tool_definitions,
    format="json"  # OR pass a JSON schema object
)
```

### Tool Calling Reliability

Research on tool-calling failures with small models (UW AST 2025, PALADIN arXiv:2509.25238):

| Failure Type | Frequency | Mitigation |
|-------------|-----------|------------|
| Tool name hallucination | High in small models | Fuzzy match against registry |
| Parameter hallucination | High | Validate against schema |
| Missing required params | Medium | Check and re-prompt |
| Malformed JSON | High in small models | Use `json_repair` library |
| Wrong tool selection | Medium | Reduce tool count per phase |
| No tool call when needed | Common | Stronger system prompt rules |

**PALADIN** (arXiv:2509.25238) raises tool success rates from 17.5% to 78.7% on LLaMA-8B through self-correction — feeding error messages back to the model. This is directly applicable to our agent loop.

**Recommended validation pipeline**:

```python
import json_repair

def validate_tool_call(tool_call, available_tools):
    name = tool_call["function"]["name"]
    args = tool_call["function"]["arguments"]

    # 1. Fuzzy match tool name
    if name not in available_tools:
        for t_name in available_tools:
            if t_name.lower() == name.lower():
                name = t_name
                break

    # 2. Repair malformed JSON
    if isinstance(args, str):
        args = json_repair.loads(args)

    # 3. Validate required parameters
    schema = available_tools[name].parameters_schema
    missing = [p for p in schema.get("required", []) if p not in args]
    if missing:
        return None, f"Missing: {missing}"

    # 4. Type coercion (string → int, etc.)
    for key, value in args.items():
        expected = schema["properties"].get(key, {}).get("type")
        if expected == "integer" and isinstance(value, str):
            args[key] = int(value)

    return {"function": {"name": name, "arguments": args}}, None
```

---

## 8. Enhanced System Prompt

### Four-Layer Prompt Architecture

Replace the current monolithic prompt with a dynamic, layered system:

#### Layer 1: Identity & Rules Contract (~150 tokens, always present)

```
/nothink
You are a D&D 5e Dungeon Master. You MUST use tools for ALL mechanical actions.

ABSOLUTE RULES:
- NEVER narrate dice results without calling roll_dice/roll_check/roll_save
- NEVER modify HP, conditions, or inventory without the appropriate tool
- NEVER invent NPC dialogue without checking npc_remember for context
- Tool results are canonical — narrate based on them, do not override
- If a tool call fails, inform the player and suggest alternatives
```

#### Layer 2: JIT Rules (0-200 tokens, conditional)

Injected based on game phase detection:

**Combat mode** (when `combat_state` is not null):
```
COMBAT RULES:
- Use get_combat_status to check turn order before acting
- Use next_turn to advance turns — do not skip
- Use attack/cast_spell for offensive actions, combat_action for dodge/dash/disengage
- Track death saves with death_save tool when HP reaches 0
- End combat with end_combat when all enemies defeated or fled
```

**Social mode** (when `talk_to_npc` was recently called):
```
SOCIAL RULES:
- Use talk_to_npc with context about the conversation topic
- Use npc_remember to record important information shared
- Use update_npc_relationship when disposition changes
- Consider NPC disposition and familiarity in dialogue tone
```

**Exploration mode** (default):
```
EXPLORATION RULES:
- Use look_around when players examine surroundings
- Use move_to for travel between locations
- Call for roll_check when players attempt skill-based actions
- Use set_environment to update time/weather as appropriate
```

#### Layer 3: State Injection (~200 tokens, dynamic)

Compiled from database queries and knowledge graph:

```
CURRENT STATE:
- Location: Rusty Tavern (town) | Exits: Market Square[E], Docks[S], Inn[N]
- Party: Arin L3 Fighter HP:28/28 AC:16 | Mira L2 Wizard HP:14/14 AC:12
- NPCs here: Bartender Grim (friendly, knows: thieves guild, missing merchant)
- Combat: inactive
- Time: evening | Weather: rain | Season: autumn
- Active quests: Find Missing Merchant (investigate tavern[incomplete], search docks[pending])
- Recent: Party arrived from Market Square. Grim mentioned strange visitors at the docks.
```

#### Layer 4: Response Format (~50 tokens, always present)

```
RESPONSE FORMAT:
- Narrate dramatically in second person ("You enter the dim tavern...")
- After tool results, describe outcomes vividly
- End with 2-3 suggested actions: **[ACTION: description]**
- Keep responses under 200 words unless combat requires detail
```

### Total Prompt Size

| Layer | Tokens | Condition |
|-------|--------|-----------|
| Identity & Rules | ~150 | Always |
| JIT Rules | ~100 | Phase-dependent |
| State Injection | ~200 | Always (dynamic content) |
| Response Format | ~50 | Always |
| **Total** | **~500** | **~6% of 8192** |

This is a 4x improvement over the current approach where the prompt is only 130 tokens but lacks state awareness, and tool definitions consume 2,000-3,000 tokens unnecessarily.

---

## 9. Proposed Development Tasks

### Phase 1: Foundation (Context & Prompt Engineering)

> Goal: Fix the immediate problems — context overflow, basic prompt, all-tools-always — without architectural changes.

| # | Task | Priority | Complexity | Dependencies |
|---|------|----------|------------|--------------|
| 1.1 | **Implement token counting** — Add `estimate_tokens()` utility and token budget tracking to `chat_service.py` | P0 | Low | None |
| 1.2 | **Add conversation history management** — Sliding window with summarization. Keep last 4-6 exchanges in full, summarize older turns. Trigger at 70% of history budget. | P0 | Medium | 1.1 |
| 1.3 | **Build dynamic system prompt** — Replace `RPG_SYSTEM_PROMPT` with 4-layer builder that queries DB for current state and conditionally injects phase-specific rules | P0 | Medium | None |
| 1.4 | **Implement dynamic tool injection** — Detect game phase (combat/exploration/social) and only send relevant tools. Add phase detection heuristic. | P1 | Medium | None |
| 1.5 | **Configure Qwen3.5:9b parameters** — Set temperature=0.7, top_p=0.8, top_k=20, presence_penalty=1.5, `/nothink`. Update default model config. | P0 | Low | None |
| 1.6 | **Add tool call validation** — Implement fuzzy name matching, schema validation, type coercion, `json_repair` fallback in `tool_service.py` | P1 | Low | None |
| 1.7 | **Add nomic-embed-text task prefixes** — Ensure `search_document:` and `search_query:` prefixes in `rag_service.py` | P1 | Low | None |

### Phase 2: Enhanced Memory & RAG

> Goal: Give the system long-term memory with three-tier architecture and hybrid search.

| # | Task | Priority | Complexity | Dependencies |
|---|------|----------|------------|--------------|
| 2.1 | **Create `game_memories` table** — Schema with memory_type, entity_type, importance_score, session_number, entity_names, timestamps | P0 | Low | None |
| 2.2 | **Implement FTS5 for game memories** — Create `fts_memories` virtual table mirroring `game_memories` content | P0 | Low | 2.1 |
| 2.3 | **Build hybrid search (RRF)** — Combine sqlite-vec + FTS5 with Reciprocal Rank Fusion scoring | P0 | Medium | 2.1, 2.2 |
| 2.4 | **Implement Stanford retrieval scoring** — Combine recency decay + importance score + relevance similarity | P1 | Medium | 2.3 |
| 2.5 | **Add memory management tools** — `archive_event`, `search_memory`, `get_session_summary` as new builtin tools | P1 | Medium | 2.1 |
| 2.6 | **Implement session summarization** — Auto-summarize at session end with hierarchical levels (encounter → session → campaign) | P1 | High | 2.1, 2.5 |
| 2.7 | **Add metadata-enhanced retrieval** — Pre-filter by memory_type, entity_type, session range before vector search | P2 | Medium | 2.3 |
| 2.8 | **Implement MemGPT-style eviction** — 70% warning, 100% flush with recursive summarization, recall storage | P2 | High | 1.1, 1.2, 2.6 |

### Phase 3: Knowledge Graph & World Model

> Goal: Add structured relationship tracking for richer world state context.

| # | Task | Priority | Complexity | Dependencies |
|---|------|----------|------------|--------------|
| 3.1 | **Create `rpg_relationships` table** — Graph overlay schema with source/target types, relationship types, strength scores | P1 | Low | None |
| 3.2 | **Add relationship management tools** — `add_relationship`, `query_relationships`, `get_entity_context` | P1 | Medium | 3.1 |
| 3.3 | **Auto-extract relationships** — When NPCs are created, items given, locations connected, etc., automatically create graph edges | P2 | Medium | 3.1, 3.2 |
| 3.4 | **Graph-to-context compiler** — Query an entity's subgraph and compile a compact text summary for state injection | P1 | Medium | 3.1, 3.2 |
| 3.5 | **Recursive CTE queries** — Implement multi-hop graph traversal for "who knows what" and "what's connected to what" | P2 | Medium | 3.1 |
| 3.6 | **GraphRAG integration** — Combine graph context with vector-based RAG for richer retrieval | P2 | High | 3.4, 2.3 |

### Phase 4: Multi-Agent Pipeline

> Goal: Separate concerns across specialized agents for better gameplay quality.

| # | Task | Priority | Complexity | Dependencies |
|---|------|----------|------------|--------------|
| 4.1 | **Design agent orchestrator** — Refactor `chat_service.py` to support sequential multi-agent pipeline | P1 | High | Phase 1 |
| 4.2 | **Implement Narrator agent** — Storytelling agent with exploration/social tools and narrative focus | P1 | High | 4.1 |
| 4.3 | **Implement Rules Engine agent** — Mechanical agent with combat/dice/character tools and strict rules enforcement | P1 | High | 4.1 |
| 4.4 | **Implement Archivist agent** — Memory agent with summarization, relationship tracking, and state persistence | P2 | High | 4.1, Phase 2, Phase 3 |
| 4.5 | **Add agent-specific prompts** — Each agent gets its own tailored system prompt with role-specific rules | P1 | Medium | 4.2, 4.3, 4.4 |
| 4.6 | **Implement agent communication** — Tool results from one agent feed as context to the next | P1 | Medium | 4.1 |
| 4.7 | **Add PALADIN self-correction** — Feed tool call errors back to the agent for self-correction (raises success 17.5% → 78.7%) | P2 | Medium | 1.6 |

### Phase 5: Polish & Advanced Features

> Goal: Quality-of-life improvements and advanced capabilities.

| # | Task | Priority | Complexity | Dependencies |
|---|------|----------|------------|--------------|
| 5.1 | **Cross-session campaign persistence** — Load/resume campaigns across conversations with full state | P1 | Medium | Phase 2, Phase 3 |
| 5.2 | **Matryoshka embedding optimization** — Switch to 256-dim embeddings for 3x storage/speed improvement | P2 | Low | 2.1 |
| 5.3 | **NPC personality via memory** — NPCs use their memory + relationship graph to generate contextual dialogue | P2 | Medium | Phase 3 |
| 5.4 | **Automated encounter balancing** — Use party level, size, and HP to suggest appropriate encounters | P3 | Medium | Phase 4 |
| 5.5 | **Session recap generation** — Auto-generate "previously on..." narrative recap at session start | P2 | Medium | 2.6 |
| 5.6 | **Frontend: memory/graph visualization** — UI panels showing the knowledge graph, memory tiers, and context budget usage | P3 | High | Phase 2, Phase 3 |
| 5.7 | **Benchmark suite** — Automated tests for tool calling accuracy, context overflow detection, narrative coherence | P2 | Medium | Phase 1 |

### Implementation Order

```
Phase 1 (Weeks 1-2): Foundation
  1.1 → 1.2 → 1.3 → 1.4 → 1.5 → 1.6 → 1.7

Phase 2 (Weeks 3-4): Memory & RAG
  2.1 → 2.2 → 2.3 → 2.4 → 2.5 → 2.6 → 2.7 → 2.8

Phase 3 (Weeks 5-6): Knowledge Graph
  3.1 → 3.2 → 3.3 → 3.4 → 3.5 → 3.6

Phase 4 (Weeks 7-9): Multi-Agent
  4.1 → 4.2 + 4.3 (parallel) → 4.4 → 4.5 → 4.6 → 4.7

Phase 5 (Weeks 10+): Polish
  5.1 → 5.2 → 5.3 → 5.4 → 5.5 → 5.6 → 5.7
```

---

## 10. Research Sources

### Academic Papers

| Paper | Authors | Venue | Year | Key Contribution |
|-------|---------|-------|------|-----------------|
| [Static Vs. Agentic Game Master AI](https://arxiv.org/abs/2502.19519) | Jorgensen et al. (Aalborg) | ACM CUI 2025 | 2025 | +243% mastery with multi-agent system |
| [Generative Agents: Interactive Simulacra](https://dl.acm.org/doi/10.1145/3586183.3606763) | Park et al. (Stanford/Google) | UIST 2023 | 2023 | Memory stream + reflection + retrieval |
| [You Have Thirteen Hours: Enhancing AI GMs with Function Calling](https://arxiv.org/html/2409.06949v1) | Song, Zhu, Callison-Burch | 2024 | 2024 | 4.39/5.0 consistency with dice + state functions |
| [CALYPSO: LLMs as DM Assistants](https://arxiv.org/abs/2308.07540) | Zhu et al. (UPenn) | AIIDE 2023 | 2023 | High/low fidelity output patterns |
| [Setting the DC: D&D Agents](https://neurips.cc/virtual/2025/loc/san-diego/128312) | Zeng et al. (UCSD PEARLS) | NeurIPS 2025 | 2025 | Multi-agent D&D combat simulation |
| [FIREBALL: D&D Dataset](https://arxiv.org/abs/2305.01528) | Zhu et al. | ACL 2023 | 2023 | 25K D&D sessions with ground truth state |
| [I Cast Detect Thoughts](https://arxiv.org/abs/2304.01860) | Zhou et al. | ACL 2023 | 2023 | Multi-user collaborative D&D dialogue |
| [MemGPT: Virtual Context Management](https://arxiv.org/abs/2310.08560) | Packer et al. (UC Berkeley) | 2023 | 2023 | OS-inspired memory management for LLMs |
| [Recursively Summarizing for Long-Term Memory](https://arxiv.org/abs/2308.15022) | 2023 | 2023 | 2023 | Recursive summary enables long dialogues |
| [H-MEM: Hierarchical Memory](https://arxiv.org/abs/2507.22925) | 2025 | 2025 | 2025 | Four-layer hierarchical memory for agents |
| [RECOMP: Context Compression](https://arxiv.org/abs/2310.04408) | 2023 | 2023 | 2023 | Extractive + abstractive RAG compression |
| [PALADIN: Self-Correcting Agents](https://arxiv.org/pdf/2509.25238) | 2025 | 2025 | 2025 | Tool success 17.5% → 78.7% via self-correction |
| [Taxonomy of Failures in Tool-Augmented LLMs](https://homes.cs.washington.edu/~rjust/publ/tallm_testing_ast_2025.pdf) | UW | AST 2025 | 2025 | Classification of tool-calling failure modes |
| [Context Window Utilization](https://arxiv.org/html/2407.19794v2) | 2024 | 2024 | 2024 | CWU as RAG hyper-parameter |
| [Nomic Embed Technical Report](https://arxiv.org/abs/2402.01613) | Nomic AI | 2024 | 2024 | Open-source long-context embeddings |

### Open-Source Projects

| Project | URL | Key Feature |
|---------|-----|-------------|
| ChatRPG | [github.com/KarmaKamikaze/ChatRPG](https://github.com/KarmaKamikaze/ChatRPG) | Academically validated 2-agent RPG (C#/.NET) |
| AIDM | [github.com/deusversus/aidm](https://github.com/deusversus/aidm) | 24+ agents, ChromaDB memory, FastAPI |
| CALYPSO | [github.com/northern-lights-province/calypso-aiide-artifact](https://github.com/northern-lights-province/calypso-aiide-artifact) | Discord bot DM assistant |
| FIREBALL | [github.com/zhudotexe/FIREBALL](https://github.com/zhudotexe/FIREBALL) | 25K D&D sessions dataset |
| Generative Agents | [github.com/joonspk-research/generative_agents](https://github.com/joonspk-research/generative_agents) | Memory stream + reflection |
| simple-graph-sqlite | [github.com/dpapathanasiou/simple-graph](https://github.com/dpapathanasiou/simple-graph) | Minimal graph DB on SQLite |
| json_repair | [github.com/mangiucugna/json_repair](https://github.com/mangiucugna/json_repair) | Fix malformed JSON from LLMs |
| Letta (MemGPT) | [docs.letta.com](https://docs.letta.com/concepts/memgpt/) | Virtual context management framework |
| D&D AI Memory | [github.com/chungs10/dnd-ai](https://github.com/chungs10/dnd-ai) | ChromaDB persistent RPG memory |
| dnd-llm-game | [github.com/tegridydev/dnd-llm-game](https://github.com/tegridydev/dnd-llm-game) | Multiple local LLMs via Ollama |
| GraphRAG with SQLite | [github.com/stephenc222/example-graphrag-with-sqlite](https://github.com/stephenc222/example-graphrag-with-sqlite) | Lightweight GraphRAG implementation |

### Technical References

| Topic | URL |
|-------|-----|
| Hybrid search (sqlite-vec + FTS5) | [alexgarcia.xyz/blog/2024/sqlite-vec-hybrid-search](https://alexgarcia.xyz/blog/2024/sqlite-vec-hybrid-search/index.html) |
| Ollama tool calling docs | [docs.ollama.com/capabilities/tool-calling](https://docs.ollama.com/capabilities/tool-calling) |
| Ollama structured outputs | [ollama.com/blog/structured-outputs](https://ollama.com/blog/structured-outputs) |
| Qwen3-8B model card | [huggingface.co/Qwen/Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B) |
| Qwen3.5-9B model card | [huggingface.co/Qwen/Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B) |
| nomic-embed-text-v1.5 | [huggingface.co/nomic-ai/nomic-embed-text-v1.5](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5) |
| SQLite recursive CTEs | [sqlite.org/lang_with.html](https://sqlite.org/lang_with.html) |
| TOON format (token-efficient) | [toonformat.dev](https://toonformat.dev/) |
| Context engineering (Anthropic) | [anthropic.com/engineering/effective-context-engineering-for-ai-agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) |
| Prompt contract pattern | [github.com/m3dcodie/prompt-contract](https://github.com/m3dcodie/prompt-contract) |
| RPGGO technical framework | [blog.rpggo.ai/2025/02/21/technical-overview-rpggos-text-to-game-framework-for-ai-rpg](https://blog.rpggo.ai/2025/02/21/technical-overview-rpggos-text-to-game-framework-for-ai-rpg/) |
| LLM tool calling failures (7 models) | [dev.to/kuroko1t/testing-7-models-tool-calling](https://dev.to/kuroko1t/what-happens-when-local-llms-fail-at-tool-calling-testing-7-models-with-a-rust-coding-agent-cep) |
| Context window management strategies | [getmaxim.ai/articles/context-window-management-strategies](https://www.getmaxim.ai/articles/context-window-management-strategies-for-long-context-ai-agents-and-chatbots/) |
| sqlite-vec benchmarks | [alexgarcia.xyz/blog/2024/sqlite-vec-stable-release](https://alexgarcia.xyz/blog/2024/sqlite-vec-stable-release/index.html) |
