# Deep Analysis: Ollama & Tools Optimization in sqliteRAG

## 1. Current Architecture Analysis

Based on the codebase analysis, `sqliteRAG` integrates with Ollama and manages a large suite of RPG tools (~50 total) using the following mechanisms:

### 1.1 How Tools are Managed
- **Tool Definitions (`services/builtin_tools/`)**: Tools are modularized into categories (dice, combat, memory, npcs, etc.).
- **Ollama Integration (`services/ollama_service.py`)**: Uses the `httpx` async client to communicate with Ollama's `/api/chat` endpoint. Tools are formatted into OpenAI-style JSON schemas via `ToolService.build_ollama_tools()`.
- **Context Management (`services/token_utils.py`)**: Estimates token usage for tool definitions to ensure they fit within the LLM's context window.
- **Phase-Based Filtering (`services/prompt_builder.py`)**: To prevent overwhelming the LLM, the `filter_tools_by_phase` function restricts the active tools based on the current `GamePhase` (COMBAT, EXPLORATION, SOCIAL). It always includes a set of `_CORE_TOOLS` and appends `_PHASE_TOOLS`.
- **Multi-Agent Routing (`services/agent_orchestrator.py`)**: The system delegates tasks to specialized agents (`ArchivistAgent`, `RulesEngineAgent`, `NarratorAgent`), each restricted to a `frozenset` of specific tools to reduce tool overload per agent.

### 1.2 The Performance Bottleneck with `qwen3.5:9b`
When injecting ~50 tools (or even 20-30 after phase filtering) into an LLM via Ollama, the JSON schema for these tools is prepended to the system prompt. For `qwen3.5:9b`:
1. **High Prompt Evaluation Time (Time-To-First-Token - TTFT)**: Qwen 3.5 models process massive JSON tool schemas very slowly in `llama.cpp` (which Ollama uses under the hood) compared to standard text.
2. **KV Cache Invalidation**: Ollama uses Prefix Caching. Because `filter_tools_by_phase` dynamically changes the tool payload as the game state shifts (e.g., entering combat), the prefix changes. This forces Ollama to re-evaluate the *entire* prompt from scratch on many turns, destroying TTFT.
3. **Context Dilution**: Too many tools confuse 9B parameter models, leading to hallucinated tool arguments or the LLM narrating actions without calling the tool (which triggered the creation of `Paladin` self-correction in this codebase).

---

## 2. Real Working Solutions for Optimization

To drastically reduce response time (TTFT) and improve reliability for `qwen3.5:9b`, you must address the **KV Cache** and **Prompt Size**.

### Solution A: Maximize Ollama KV Cache Hits (Quickest Win)
Ollama caches the evaluation of prompts based on their prefix. If the tools keep changing, the cache misses.
1. **Stop Dynamic Phase Filtering for Tools**: Instead of changing the tools array every phase (which invalidates the cache), give the model a **static** list of tools for the entire session, but enforce phase rules in the *system prompt text* at the end of the context.
2. **Increase `num_ctx` and `keep_alive`**: Ensure Ollama keeps the model and its massive KV cache in memory.
   *In `config.py` or your API payload:*
   ```python
   # In ollama_service.py chat kwargs
   "options": {
       "num_ctx": 16384,     # Ensure enough space for all tools + history
       "num_predict": 1024,
   },
   "keep_alive": "60m"       # Keep loaded in VRAM
   ```

### Solution B: Semantic Tool Retrieval (RAG for Tools - High Impact)
Passing 50 tools is too much for a 9B model. Instead of injecting all tools, use a semantic router:
1. **Embed Tool Descriptions**: At startup, embed the description of each tool using your existing `embedding_model`.
2. **Retrieve Top-K Tools**: When the user sends a message, compute its embedding. Do a cosine similarity search against the tools and retrieve only the **Top 5 most relevant tools**.
3. **Inject dynamically**: Add these 5 tools + Core memory tools (like `archive_event`) to the LLM context.
*Why it works:* It reduces the tool payload by 80%, dropping prompt eval time from seconds to milliseconds.

### Solution C: Hierarchical Tool Architecture (The Advanced Fix)
Refactor your 50 tools into a single "God Tool" or a few "Category Tools".
Instead of: `attack()`, `cast_spell()`, `take_damage()`, `heal()`
Create one tool: `execute_combat_action(action_type: str, target: str, amount: int)`
1. The LLM only has to understand **1 tool schema** instead of 4.
2. The `ToolService` in the Python backend interprets `action_type="attack"` and routes it to the correct Python function.
*Why it works:* `qwen3.5:9b` handles 5 broad tools much better than 50 granular tools.

### Solution D: Swap Backend to vLLM (Infrastructure Fix)
If you must load 50 tools simultaneously, Ollama (`llama.cpp`) CPU/GPU prompt ingestion is a bottleneck.
- Run `qwen3.5:9b` using **vLLM** instead of Ollama.
- vLLM uses PagedAttention and highly optimized FlashAttention-2, which ingests massive tool schemas 3x to 5x faster than Ollama. You can use vLLM's OpenAI-compatible server and seamlessly swap your `base_url` in `OllamaService` to point to vLLM.

---

## 3. Recommended Implementation Plan for sqliteRAG

1. **Immediate fix:** Go into `services/ollama_service.py` and ensure `"keep_alive": "-1"` is set in the payload to prevent model unloading.
2. **Short-term fix:** Review `prompt_builder.py`. The `filter_tools_by_phase` is destroying your KV cache. Try disabling it to see if a static tool list allows Ollama to cache the prompt evaluation between turns.
3. **Long-term fix:** Implement **Solution C (Hierarchical Tools)**. Group your combat tools into `combat_system_tool` and your exploration tools into `exploration_system_tool`. Parse the arguments in Python. This guarantees low latency and high accuracy for 9B models.
