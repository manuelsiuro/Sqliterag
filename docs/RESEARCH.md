# Ollama D&D Tool Calling & Model Research Report

## Context

Research into the existing ecosystem of Ollama-based tool-calling projects for Dungeons & Dragons, and the best locally-runnable models optimized for D&D gameplay.

---

## Part 1: D&D Tool-Calling Projects for Ollama

### Key Finding

**No single mature project** combines Ollama + native tool calling + full D&D mechanics in one package. The ecosystem splits into: (A) projects using Ollama's tool calling for RPG, (B) Ollama D&D games without tool calling, and (C) MCP servers providing D&D tools that can be connected to Ollama via MCP clients.

---

### A. Projects Using Ollama Tool/Function Calling for RPG

| Project | Stack | What It Does | Maturity |
|---------|-------|--------------|----------|
| **[Quarkus + LangChain4j AI DM](https://www.the-main-thread.com/p/ai-dungeon-master-quarkus-langchain4j-java)** | Java, Quarkus, LangChain4j, Ollama | Exposes game-logic methods (skill checks, HP, inventory) as `@Tool` annotations. LLM decides which tool to call based on player input. | Tutorial / reference implementation |
| **[Al-Scripting/Local-AI-Dungeon-Ollama-Python](https://github.com/Al-Scripting/Local-AI-Dungeon-Ollama-Python)** | Python, Ollama, Gemma 3 | Uses JSON structured output (not formal tool calling). LLM proposes state changes, Python engine validates. Handles locks, inventory, HP, quests. | Demo / PoC |

### B. Ollama D&D Games (Prompt-Based, No Tool Calling)

| Project | Stack | What It Does | Maturity |
|---------|-------|--------------|----------|
| **[tegridydev/dnd-llm-game](https://github.com/tegridydev/dnd-llm-game)** | Python, Streamlit, LangChain, Ollama | Character gen, turn-based D&D adventures, AI party members. Web UI. | MVP |
| **[cyberofficial/Ollama-Dungeon](https://github.com/cyberofficial/Ollama-Dungeon)** | Python 3.12, Ollama (qwen3:8b) | Filesystem-based world, CSV memory, context compression, session persistence. | Active |
| **[Laszlobeer/Dungeo_ai](https://github.com/Laszlobeer/Dungeo_ai)** | Python, Ollama | 2-5 multiplayer, genre selection, save/load, GUI version available. Custom "bob-silly-dungeon-master" model. | Has CLI + GUI |
| **[igorbenav/clientai-dungeon-master](https://github.com/igorbenav/clientai-dungeon-master)** | Python, ClientAI, Ollama | Text RPG with character creation, exploration, NPC interaction. Multi-provider support. | Example project |
| **[davidpm1021/ai-dungeon-master](https://github.com/davidpm1021/ai-dungeon-master)** | Node/TS, Discord, pgvector, Ollama + Claude-3 | Discord bot DM with vector memory. Dual-model: Claude-3 critic + Mistral-7B via Ollama. | Sophisticated architecture |

### C. MCP Servers for D&D (Connectable to Ollama via MCP Clients)

These are the most promising for tool-calling D&D. They expose D&D tools via MCP protocol and can work with any MCP-compatible client backed by Ollama.

| Project | Tools | What It Does | Maturity |
|---------|-------|--------------|----------|
| **[Mnehmos/rpg-mcp](https://github.com/Mnehmos/rpg-mcp)** | **145+ tools** | **The most complete option.** Rules-enforced RPG backend: real dice rolls, AC checks, damage calc, HP tracking, 15+ SRD spells with slot tracking, pathfinding movement, 1100+ creature presets, 50+ encounter presets. LLM cannot cheat. | **Very mature** (800+ tests, white paper) |
| **[study-flamingo/gamemaster-mcp](https://github.com/study-flamingo/gamemaster-mcp)** | Campaign, character, encounter, world tools | Campaign management, character tracking, encounter building, worldbuilding. JSON file storage. | Active |
| **[heffrey78/dnd-mcp](https://github.com/heffrey78/dnd-mcp)** | `unified_search`, `search_spells`, caching | D&D 5e content lookup via Open5e REST API. Spells, classes, races, monsters, equipment. | Lightweight |
| **[procload/dnd-mcp](https://github.com/procload/dnd-mcp)** | D&D 5e API tools + templates | D&D 5e API with markdown templates, source attribution, query enhancement for D&D terminology. | Well-structured |
| **[jnaskali/rpg-mcp](https://github.com/jnaskali/rpg-mcp)** | `roll_dice`, `check_success`, `generate_event` | Simple dice rolling and success checks. Good lightweight starting point. | Small |
| **[saidsurucu/d20-mcp](https://lobehub.com/mcp/saidsurucu-d20-mcp)** | Dice rolling (D&D, Pathfinder, etc.) | Advanced dice: keep/drop, reroll, exploding, AST breakdown, batch rolling. | Focused utility |

### D. Foundry VTT Integration

| Project | What It Does |
|---------|--------------|
| **[RPGX AI Assistant](https://foundryvtt.com/packages/rpgx-ai-assistant)** | Local Ollama integration directly inside Foundry VTT. Chat commands for story gen, NPC dialogue, rules clarification. Optional RAG extension for world lore. |
| **[adambdooley/foundry-vtt-mcp](https://github.com/adambdooley/foundry-vtt-mcp)** | MCP bridge to Foundry VTT data. 20 tools for journals, characters, actors, scenes. D&D 5e + PF2e. |

---

### Recommended Architecture (If Building)

The strongest approach is: **Ollama (with a good model) + MCP client + Mnehmos/rpg-mcp**

- **Mnehmos/rpg-mcp** provides 145+ verified game tools (dice, combat, spells, movement, creatures)
- An MCP client backed by Ollama makes the tool calls
- The LLM handles narrative; the engine handles rules deterministically
- 800+ tests ensure rule correctness

---

## Part 2: Best Ollama Models for D&D

### Top Picks by Category

#### Best D&D-Specific Model
**Wayfarer-12B** — `ollama run Desmon2D/Wayfarer-12B`
- **Size:** 12B (~7 GB Q4_K_M)
- **Base:** Mistral Nemo 12B
- **Why:** Built by the **AI Dungeon team** (Latitude Games). Trained on 50/50 mix of synthetic text adventures and roleplay playthroughs. Second-person present tense ("you"). Pessimistic tone where failure is frequent and plot armor doesn't exist — perfect for authentic D&D stakes.
- **Tool calling:** No
- **Community verdict:** "Significantly superior" for RP responses in head-to-head comparison tests.

#### Best Tool Calling + D&D Hybrid
**Qwen3 8B** — `ollama run qwen3`
- **Size:** 8B (~4.7 GB)
- **Context:** 128K tokens, generates up to 8K
- **Why:** The **only model that genuinely excels at both creative RP and tool calling**. Officially in Ollama's tools category. Community notes it "excels in creative writing and role-playing" with "expertise in agent capabilities with tool calling support."
- **Tool calling:** Yes
- **Best for:** Pairing with MCP D&D tool servers.

#### Best RP Quality (12B Range)
**Mag Mell R1 12B** — `ollama run nchapman/mn-12b-mag-mell-r1`
- **Size:** 12B
- **Base:** 6-model merge on Mistral Nemo (Chronos Gold, Sunrose, Bophades, Wissenschaft, Gutenberg v4, Magnum 2.5)
- **Why:** "Worldbuilding capabilities unlike any model in its class," "prose that exhibits minimal slop," "electrifying metaphors." Perfect for GMs and players. Excellent character consistency.
- **Tool calling:** No
- **Recommended settings:** Temp 1.25, MinP 0.2

#### Best for NPC Emotional Depth
**Psyfighter 13B** — search Ollama for "psyfighter"
- **Size:** 13B (8-12 GB VRAM)
- **Base:** Llama 2 13B
- **Why:** Fine-tuned on emotional expression datasets. "Mood shifts — when sad scenes were written, it reacted with hesitation or support." Rarely breaks character even in long sessions.
- **Tool calling:** No

#### Budget Pick (Low Hardware)
**ALIENTELLIGENCE/gamemasterroleplaying** — `ollama run ALIENTELLIGENCE/gamemasterroleplaying`
- **Size:** ~4.7 GB
- **Context:** 128K tokens
- **Why:** Purpose-built for game mastering. Fast. Specifically designed for D&D/RPG scenarios.
- **Tool calling:** No
- **Caveat:** "Sometimes the narrator likes to act like a cheerleader praising the story."

#### If Hardware Is No Concern (70B)
**Euryale L3.3 70B v2.3** — `ollama run nchapman/l3.3-70b-euryale-v2.3`
- **Size:** 70B (~40 GB Q4)
- **Base:** Llama 3.3 70B Instruct
- **Why:** Regarded as the gold standard for creative RP. Top-tier output quality.
- **Tool calling:** No

---

### Full Model Comparison Table

| Model | Size | Tool Calling | D&D Quality | Ollama Command |
|-------|------|-------------|-------------|----------------|
| **Qwen3** | 8B | Yes | High | `ollama run qwen3` |
| **Llama 3.1** | 8B | Yes | Good | `ollama run llama3.1` |
| **Mistral Nemo** | 12B | Yes | Good | `ollama run mistral-nemo` |
| **Wayfarer-12B** | 12B | No | Excellent (D&D-specific) | `ollama run Desmon2D/Wayfarer-12B` |
| **Mag Mell R1** | 12B | No | Excellent (worldbuilding) | `ollama run nchapman/mn-12b-mag-mell-r1` |
| **Psyfighter** | 13B | No | Excellent (NPCs) | Search "psyfighter" |
| **ALIENTELLIGENCE/gamemasterroleplaying** | ~8B | No | Good (purpose-built) | `ollama run ALIENTELLIGENCE/gamemasterroleplaying` |
| **Natsumura-storytelling-rp** | 8B | No | Very Good | `ollama run Tohur/natsumura-storytelling-rp-llama-3.1` |
| **Euryale L3.3 70B** | 70B | No | Best-in-class | `ollama run nchapman/l3.3-70b-euryale-v2.3` |
| **OpenHermes 2.5** | 7B | No | Decent (lightweight) | `ollama run openhermes` |

---

### Size Recommendations by Hardware

| RAM / VRAM | Recommended Models |
|------------|-------------------|
| **8-16 GB** | Qwen3 8B (tool calling), Natsumura 8B (RP), OpenHermes 7B (lightweight) |
| **16-24 GB** | Wayfarer-12B (D&D-specific), Mag Mell 12B (worldbuilding), Psyfighter 13B (NPCs) |
| **64+ GB** | Euryale 70B (gold standard), Wayfarer-Large 70B (D&D at scale), Llama 3.3 70B (tool calling) |

---

## Key Takeaways

1. **For tool calling + D&D**: Use **Qwen3 8B** with **Mnehmos/rpg-mcp** (145+ game tools, 800+ tests). This is the most robust architecture.

2. **For pure narrative DM quality**: **Wayfarer-12B** (D&D-specific) or **Mag Mell R1 12B** (worldbuilding) are the community favorites in the 12B range.

3. **The ecosystem gap**: No single project combines Ollama native tool calling + full D&D mechanics + a polished UI. The closest is connecting Mnehmos/rpg-mcp to an Ollama-backed MCP client.

4. **Important caveat**: LLMs as autonomous DMs are "insanely suggestible and have poor memory" ([research](https://arxiv.org/abs/2308.07540)). Best results come from pairing the LLM with deterministic game engines (like rpg-mcp) rather than letting it handle rules alone.

---

## Sources

**Projects:**
- [Mnehmos/rpg-mcp](https://github.com/Mnehmos/rpg-mcp) — Most complete rules-enforced RPG engine
- [tegridydev/dnd-llm-game](https://github.com/tegridydev/dnd-llm-game) — Streamlit D&D game
- [cyberofficial/Ollama-Dungeon](https://github.com/cyberofficial/Ollama-Dungeon) — Text adventure with memory
- [Al-Scripting/Local-AI-Dungeon-Ollama-Python](https://github.com/Al-Scripting/Local-AI-Dungeon-Ollama-Python) — JSON rules engine
- [study-flamingo/gamemaster-mcp](https://github.com/study-flamingo/gamemaster-mcp) — Campaign management MCP
- [RPGX AI Assistant](https://foundryvtt.com/packages/rpgx-ai-assistant) — Foundry VTT + Ollama
- [Quarkus LangChain4j DM Tutorial](https://www.the-main-thread.com/p/ai-dungeon-master-quarkus-langchain4j-java)

**Models:**
- [Wayfarer-12B on HuggingFace](https://huggingface.co/LatitudeGames/Wayfarer-12B)
- [Qwen3 on Ollama](https://ollama.com/library/qwen3)
- [Mag Mell R1 on Ollama](https://ollama.com/nchapman/mn-12b-mag-mell-r1)
- [Euryale L3.3 70B on Ollama](https://ollama.com/nchapman/l3.3-70b-euryale-v2.3)
- [ALIENTELLIGENCE/gamemasterroleplaying on Ollama](https://ollama.com/ALIENTELLIGENCE/gamemasterroleplaying)
- [itch.io Model Comparison Test](https://itch.io/t/5243662/local-ai-ollama-comparision-test-mistral-nemo-wayfarer-12b-alientelligence)

**Research:**
- [CALYPSO: LLMs as DM Assistants (UPenn)](https://arxiv.org/abs/2308.07540)
- [Ollama Tool Calling Docs](https://docs.ollama.com/capabilities/tool-calling)
- [Best Ollama Models for Creative Writing & RP](https://www.arsturn.com/blog/a-guide-to-the-best-ollama-models-for-creative-writing-and-rp)
