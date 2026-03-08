# LLM Image Generation for sqliteRAG — Research & Architecture Document

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Model Comparison](#model-comparison)
4. [Apple Silicon Performance](#apple-silicon-performance)
5. [Provider Options Analysis](#provider-options-analysis)
6. [Prompt Engineering for D&D Art](#prompt-engineering-for-dd-art)
7. [Implementation Details](#implementation-details)
8. [Setup & Prerequisites](#setup--prerequisites)

---

## Overview

This document covers the integration of local image generation into the sqliteRAG D&D RPG application. The system generates character portraits, location scenes, item illustrations, and battle scenes using Stable Diffusion XL (SDXL) via the HuggingFace Diffusers library, running locally on Apple Silicon (MPS).

### Goals

- Generate contextual artwork during D&D gameplay (portraits, locations, items, battles)
- Fully local — no cloud dependencies, no API keys required
- Integrated into the existing agent tool loop — the LLM (DM) decides when to generate images
- Cached on the filesystem for instant re-display
- Rendered in the chat UI alongside other tool results

### Chosen Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Library | HuggingFace Diffusers | Native Python, direct pipeline control, LoRA support |
| Model | SDXL (stable-diffusion-xl-base-1.0) | Best D&D LoRA ecosystem, good quality/speed balance |
| Device | MPS (Metal Performance Shaders) | Apple Silicon GPU acceleration |
| Serving | FastAPI StaticFiles | Matches local-first architecture |
| Trigger | LLM tool calls | Natural integration with agent loop |

---

## Architecture

```
User Message → LLM (Ollama/qwen3.5) → Tool Call: generate_portrait(character_name="Sylvani")
                                           │
                                           ▼
                                     ToolService._execute_builtin()
                                           │
                                           ▼
                                  imaging.generate_portrait()
                                     │                  │
                                     ▼                  ▼
                              Character DB lookup    ImageGenerationService.generate()
                              (race, class, desc)         │
                                     │                    ▼
                                     ▼              Check cache (SHA-256 hash)
                              Build prompt              │
                              from game state    ┌──────┴──────┐
                                                 │ Cached      │ Not cached
                                                 ▼             ▼
                                           Return URL    asyncio.Lock → to_thread()
                                                              │
                                                              ▼
                                                   SDXL Pipeline (MPS)
                                                              │
                                                              ▼
                                                   Save PNG → image_cache/
                                                              │
                                                              ▼
                                              Return {"type": "generated_image", "url": "/api/images/abc123.png"}
                                                              │
                                                              ▼
                                              SSE tool_result event → Frontend
                                                              │
                                                              ▼
                                              GeneratedImageRenderer → <img src="...">
```

### Key Design Decisions

1. **Lazy Loading**: The SDXL pipeline (~6.5GB model) loads on first image generation request, not at app startup. Users who don't use image generation pay zero startup cost.

2. **Single-Generation Lock**: An `asyncio.Lock` ensures only one image generates at a time. This prevents GPU memory exhaustion on Apple Silicon's unified memory.

3. **Thread Offloading**: Diffusers' synchronous pipeline runs via `asyncio.to_thread()`, keeping the FastAPI event loop responsive during the 30-60s generation.

4. **Prompt-Based Caching**: Images are cached by `SHA-256(prompt + seed + dimensions)`. Identical requests return the cached file instantly.

5. **Game-Aware Prompts**: Portrait prompts are built from the character's database record (race, class, equipment), not just the LLM's description. This ensures accuracy.

---

## Model Comparison

### Stable Diffusion XL (SDXL) — Chosen

| Property | Value |
|----------|-------|
| Model size | ~6.5GB |
| Resolution | 1024x1024 native |
| VRAM required | 6-8GB (fits in 16GB unified memory) |
| Generation time (M2 Pro) | ~35-50s at 30 steps |
| LoRA ecosystem | Extensive — many D&D/fantasy LoRAs on CivitAI |
| Quality | High — good detail, lighting, composition |
| Hands/faces | Moderate — better than SD 1.5, worse than Flux |

**Why SDXL**: Best balance of quality, speed, and LoRA availability for D&D art. The CivitAI ecosystem has numerous fantasy art LoRAs specifically trained for character portraits, medieval environments, and item illustrations.

### FLUX.1 [dev]

| Property | Value |
|----------|-------|
| Model size | ~12GB (full) / ~4GB (quantized) |
| Resolution | Up to 2048x2048 |
| VRAM required | 12-24GB (full) / 8GB (quantized) |
| Generation time (M2 Pro) | 85-145s |
| LoRA ecosystem | Growing but smaller than SDXL |
| Quality | Excellent — best hands, faces, text rendering |
| Hands/faces | Best in class |

**Trade-off**: Superior quality but 2-3x slower, much larger model, fewer fantasy LoRAs. The user's gamebook project uses FLUX.1 [dev] via Draw Things — could be a future upgrade path.

### Stable Diffusion 1.5

| Property | Value |
|----------|-------|
| Model size | ~4GB |
| Resolution | 512x512 native |
| VRAM required | 4-6GB |
| Generation time (M2 Pro) | 8-15s |
| LoRA ecosystem | Largest (legacy) |
| Quality | Moderate — lower resolution, less detail |

**Trade-off**: Fastest generation but 512x512 output looks dated. Massive LoRA library but many are legacy quality.

### Stable Diffusion 3.x

| Property | Value |
|----------|-------|
| Model size | ~6GB |
| Resolution | 1024x1024 |
| VRAM required | 8-10GB |
| Quality | High — improved text, better coherence |

**Trade-off**: Newer architecture, good quality, but restrictive licensing for some variants and less community LoRA support than SDXL.

### Recommendation Matrix

| Use Case | Best Model | Why |
|----------|-----------|-----|
| D&D character portraits | SDXL + LoRA | Rich fantasy LoRA ecosystem |
| Location landscapes | SDXL | Good composition, fast enough |
| Item illustrations | SDXL | Square format works well |
| Battle scenes | SDXL | Action poses, dynamic composition |
| Maximum portrait quality | Flux.1 [dev] | Best faces/hands (future upgrade) |
| Fast iteration/prototyping | SD 1.5 | 8-15s per image |

---

## Apple Silicon Performance

### Device Support

| Framework | MPS Support | Status |
|-----------|------------|--------|
| PyTorch (torch) | Full | Stable since PyTorch 2.0 |
| HuggingFace Diffusers | Full | Native MPS pipeline support |
| MLX (Apple) | Full | Faster than PyTorch+MPS for some ops |
| Core ML | Full | Requires model conversion |
| ComfyUI | Full | PyTorch MPS backend |
| Draw Things | Native (gRPC) | Fastest native option |

### Benchmarks (SDXL, 1024x1024, 30 steps)

| Chip | Unified Memory | Generation Time | Notes |
|------|---------------|-----------------|-------|
| M1 | 8GB | Not recommended | Model doesn't fit comfortably |
| M1 | 16GB | ~60-80s | Works with attention slicing |
| M1 Pro | 16GB | ~45-55s | Good baseline |
| M2 Pro | 16GB | ~35-50s | Sweet spot for SDXL |
| M2 Pro | 32GB | ~30-45s | Comfortable, room for LoRAs |
| M3 Pro | 18GB | ~25-40s | Improved GPU cores |
| M3 Max | 36GB+ | ~15-25s | Can run Flux comfortably too |

### Memory Optimization Techniques

1. **`enable_attention_slicing()`** — Reduces peak memory by computing attention in steps. ~10% slower but fits in 16GB.
2. **`enable_vae_tiling()`** — Tiles VAE decode for large images. Needed for >1024px on 16GB.
3. **`torch.float16` dtype** — Half precision on MPS. Essential for fitting SDXL in memory.
4. **`pipe.to("mps")` + `torch.mps.empty_cache()`** — Explicit MPS placement and cache clearing between generations.
5. **Pipeline offloading** — Move components to CPU when not in use (advanced, not needed for SDXL on 16GB+).

### Known MPS Limitations

- Some operations may fall back to CPU silently (minor performance impact)
- `torch.Generator("mps")` seed behavior can differ from CUDA — same seed may produce slightly different images than on NVIDIA
- No native support for some ControlNet operations (workaround: run on CPU)
- Occasional MPS-specific bugs in newer PyTorch versions — pin PyTorch version if needed

---

## Provider Options Analysis

We evaluated 6 local image generation approaches. Here's the full comparison:

### 1. HuggingFace Diffusers (Python) — CHOSEN

**How it works**: Import `diffusers` library directly in the FastAPI backend. Load SDXL pipeline, call `pipeline(prompt=...)`, get PIL Image.

**Pros**:
- Native Python — no external processes or HTTP APIs to manage
- Full control over pipeline, schedulers, LoRA loading, guidance scale
- Direct MPS integration via PyTorch
- Active development, excellent documentation
- LoRA/textual inversion support built-in

**Cons**:
- Heavy dependencies (~2GB pip install for torch+diffusers+transformers)
- Pipeline loading is slow (~30s first time)
- Model download on first use (~6.5GB for SDXL)

**Integration effort**: Medium — new service class, asyncio wrapper

### 2. Draw Things (macOS App + HTTP API)

**How it works**: Native macOS app with A1111-compatible HTTP API at `localhost:7860`. Send POST requests with prompt/parameters, receive base64-encoded images.

**Pros**:
- Native macOS optimization (Metal, gRPC internally)
- Fastest performance on Apple Silicon
- No Python ML dependencies needed
- User's gamebook project already uses this

**Cons**:
- Requires Draw Things app running separately
- Not headless — needs macOS GUI session
- Dependent on third-party app updates
- API compatibility may break between versions

**Why not chosen**: Requires external app management. Users must manually launch Draw Things and load the correct model. Not suitable for a self-contained backend.

### 3. Pollinations.ai (Cloud API)

**How it works**: Free cloud API — encode prompt in URL, GET request returns image bytes directly. Supports Flux models.

**Pros**:
- Zero setup, no local compute needed
- Free, no API key
- 3-5s generation time
- Multiple model options (flux, flux-realism, flux-anime)

**Cons**:
- Requires internet
- No control over model, LoRAs, or pipeline
- Quality/consistency varies
- Terms of service may change

**Why not chosen**: User specifically requested local-only, no cloud fallback.

### 4. ComfyUI (API Mode)

**How it works**: ComfyUI runs as a server, accepts workflow JSON via API, returns generated images. Supports complex multi-step pipelines.

**Pros**:
- Most powerful pipeline composition (IP-Adapter, ControlNet, LoRA stacking)
- Visual workflow editor for prompt engineering
- Active community with workflow sharing
- Supports all model architectures

**Cons**:
- Requires separate process (ComfyUI server)
- Complex API (workflow JSON, not simple prompt→image)
- Heavy install (~4GB+ for ComfyUI + dependencies)
- Steeper learning curve

**Potential future upgrade**: ComfyUI would be valuable for advanced features like IP-Adapter (character consistency across multiple portraits) or ControlNet (pose-guided generation).

### 5. Ollama Image Generation (Experimental)

**How it works**: As of January 2026, Ollama added experimental image generation support on macOS. Same `/api/generate` endpoint, but with image models like `x/flux2-klein:4b`.

**Pros**:
- Ollama is already a dependency of sqliteRAG
- Same API pattern as LLM inference
- Quantized models (smaller downloads)

**Cons**:
- Experimental, macOS-only
- Limited model selection
- Lower quality than full SDXL/Flux
- Less control over generation parameters

**Potential future option**: If Ollama's image generation matures, it could be the simplest integration path since Ollama is already used for LLM inference.

### 6. LocalAI

**How it works**: OpenAI-compatible API server that runs local models. Supports image generation alongside LLM inference.

**Pros**:
- OpenAI-compatible API
- Multi-model support
- Docker-friendly

**Cons**:
- Requires separate server process
- Less community support than diffusers/ComfyUI
- macOS/MPS support is secondary

**Why not chosen**: Adds operational complexity without clear benefits over direct diffusers integration.

### Decision Summary

| Provider | Setup | Performance | Control | Local-Only | Chosen? |
|----------|-------|------------|---------|------------|---------|
| Diffusers | Medium | Good | Full | Yes | YES |
| Draw Things | Low (if installed) | Best | Limited | Yes | No — external dependency |
| Pollinations | None | Fast (cloud) | None | No | No — requires internet |
| ComfyUI | High | Good | Maximum | Yes | No — too complex for v1 |
| Ollama | Low | Moderate | Low | Yes | No — experimental |
| LocalAI | High | Moderate | Moderate | Yes | No — unnecessary complexity |

---

## Prompt Engineering for D&D Art

### Character Portraits

**Template**:
```
{style} portrait of a {race} {class}, {physical_description}, {equipment_highlights},
medieval fantasy art, detailed face, dramatic lighting, dark background,
high quality, 4k, detailed
```

**Example**:
```
Fantasy portrait of a half-elf ranger, green eyes, long silver hair, leather armor,
carrying a longbow, forest background, medieval fantasy art, detailed face,
dramatic lighting, high quality, 4k
```

**Tips**:
- Start with art style qualifier ("oil painting", "digital art", "dark fantasy")
- Include race and class for immediate context
- Mention 2-3 physical features max (eyes, hair, distinguishing marks)
- Reference key equipment (weapon, armor type)
- Use static poses — "portrait", "bust", "headshot" — not action verbs
- End with quality boosters: "high quality, 4k, detailed, masterwork"

**Negative prompt**:
```
blurry, deformed, extra limbs, bad anatomy, bad hands, missing fingers,
extra fingers, text, watermark, logo, signature, low quality, jpeg artifacts,
disfigured, ugly, duplicate, morbid, mutilated
```

### Location Scenes

**Template**:
```
{style} of a {biome_atmosphere} {location_type}, {description_highlights},
{time_of_day} lighting, {weather}, epic fantasy landscape, wide angle,
atmospheric perspective, high detail
```

**Example**:
```
Fantasy landscape of a dark ancient forest, massive twisted oak trees,
glowing mushrooms on the forest floor, misty atmosphere, moonlight filtering
through canopy, mysterious and foreboding, epic fantasy, wide angle, 4k
```

**Biome-specific atmosphere keywords**:

| Biome | Keywords |
|-------|----------|
| Forest | ancient trees, dappled sunlight, mystical, moss-covered |
| Dungeon | torchlit, stone walls, dark corridors, ominous shadows |
| Town | medieval buildings, cobblestone streets, market stalls, warm light |
| Mountain | snow-capped peaks, dramatic clouds, vast valleys, alpine |
| Desert | endless dunes, harsh sun, ancient ruins, mirage |
| Swamp | murky water, twisted trees, fog, eerie green light |
| Coast | crashing waves, sea cliffs, lighthouse, salt spray |
| Cavern | stalactites, underground lake, bioluminescence, crystal formations |

### Item Illustrations

**Template**:
```
{style} illustration of a {rarity_modifier} {item_type}, {item_name},
{description}, {material_details}, dark background, centered composition,
fantasy RPG item, detailed, high quality
```

**Rarity modifiers**:

| Rarity | Visual Keywords |
|--------|----------------|
| Common | simple, rustic, well-worn, practical |
| Uncommon | well-crafted, polished, subtle glow |
| Rare | intricate engravings, faint blue glow, masterwork |
| Very Rare | ethereal purple aura, magical runes, otherworldly |
| Legendary | radiant golden glow, divine craftsmanship, ancient power, ornate |

### Battle Scenes

**Template**:
```
{style} battle scene, {combatants_description}, {setting},
dynamic action pose, dramatic lighting, motion blur on weapons,
epic fantasy combat, cinematic composition, high detail
```

### Style Consistency

To maintain visual consistency across multiple generations in a session:

1. **Use a fixed seed** — same seed + similar prompt = consistent art style
2. **Standardize style prefix** — always use the same style qualifier (e.g., "dark fantasy digital art")
3. **Maintain negative prompts** — use identical negative prompts across all generations
4. **Future: LoRA models** — load a D&D-specific LoRA for consistent fantasy art style

### Recommended Art Style Presets

| Preset Name | Style Qualifier |
|-------------|----------------|
| Classic D&D | "detailed fantasy illustration, dungeons and dragons art style, medieval, rich colors" |
| Dark Fantasy | "dark fantasy digital art, grim, muted colors, dramatic shadows, gothic" |
| Watercolor | "watercolor painting, fantasy illustration, soft colors, flowing brushstrokes" |
| Oil Painting | "oil painting, classical fantasy art, rich textures, chiaroscuro lighting" |
| Comic Book | "fantasy comic book art, bold lines, vibrant colors, dynamic composition" |

---

## Implementation Details

### New Files

| File | Purpose |
|------|---------|
| `backend/app/services/image_generation_service.py` | SDXL pipeline wrapper (lazy load, cache, async) |
| `backend/app/services/builtin_tools/imaging.py` | 4 tool functions (portrait, location, item, scene) |
| `frontend/src/components/tools/renderers/GeneratedImageRenderer.tsx` | React renderer for `generated_image` type |

### Modified Files

| File | Change |
|------|--------|
| `backend/pyproject.toml` | Add torch, diffusers, transformers, accelerate, safetensors, Pillow |
| `backend/app/config.py` | Add image generation settings block |
| `backend/app/dependencies.py` | Register `get_image_service()` singleton |
| `backend/app/main.py` | Mount StaticFiles at `/api/images` |
| `backend/app/services/builtin_tools/__init__.py` | Register 4 image tools in BUILTIN_REGISTRY |
| `backend/app/database.py` | Seed 4 tool definitions |
| `backend/app/services/tool_service.py` | Inject `image_service` + argument aliases |
| `backend/app/services/prompt_builder.py` | Add to RPG_TOOL_NAMES, _PHASE_TOOLS, identity layer |
| `frontend/src/components/tools/renderers/index.ts` | Register GeneratedImageRenderer |

### Tool JSON Contract

All 4 tools return the same `generated_image` type:

```json
{
  "type": "generated_image",
  "image_type": "portrait | location | item | scene",
  "url": "/api/images/abc123def456.png",
  "prompt": "fantasy portrait of a half-elf ranger...",
  "negative_prompt": "blurry, deformed...",
  "subject": "Sylvani",
  "width": 1024,
  "height": 1024,
  "steps": 30,
  "guidance": 7.5,
  "seed": 42,
  "generation_time": 38.5,
  "cached": false,
  "model": "stabilityai/stable-diffusion-xl-base-1.0"
}
```

Error case:
```json
{
  "type": "generated_image",
  "error": "Image generation not available: torch not installed"
}
```

---

## Setup & Prerequisites

### System Requirements

| Requirement | Minimum | Recommended |
|------------|---------|-------------|
| macOS | 13.0 (Ventura) | 14.0+ (Sonoma) |
| Apple Silicon | M1 | M2 Pro or newer |
| Unified Memory | 16GB | 32GB |
| Disk Space | 10GB free | 20GB free |
| Python | 3.10+ | 3.11+ |

### Installation

1. **Install Python dependencies**:
   ```bash
   cd backend
   pip install torch diffusers transformers accelerate safetensors Pillow
   ```

2. **Pre-download the model** (optional, avoids first-use delay):
   ```bash
   python -c "
   from diffusers import StableDiffusionXLPipeline
   pipe = StableDiffusionXLPipeline.from_pretrained(
       'stabilityai/stable-diffusion-xl-base-1.0',
       use_safetensors=True,
   )
   print('Model downloaded successfully')
   "
   ```
   This downloads ~6.5GB to `~/.cache/huggingface/hub/`.

3. **Verify MPS availability**:
   ```bash
   python -c "import torch; print('MPS available:', torch.backends.mps.is_available())"
   ```

4. **Start the backend**:
   ```bash
   cd backend
   uvicorn app.main:app --reload
   ```

### Configuration

Environment variables (in `backend/.env`):

```env
# Enable/disable image generation
IMAGE_GENERATION_ENABLED=true

# Model (HuggingFace model ID or local path)
IMAGE_MODEL_ID=stabilityai/stable-diffusion-xl-base-1.0

# Generation defaults
IMAGE_DEFAULT_STEPS=30
IMAGE_DEFAULT_GUIDANCE=7.5
IMAGE_DEFAULT_WIDTH=1024
IMAGE_DEFAULT_HEIGHT=1024

# Cache directory
IMAGE_CACHE_DIR=/path/to/backend/image_cache

# Timeout (seconds)
IMAGE_GENERATION_TIMEOUT=300
```

### Using a Local Model File

If you have a `.safetensors` file locally (e.g., from CivitAI), point to it:

```env
IMAGE_MODEL_ID=/path/to/your/model.safetensors
```

The service will use `from_single_file()` instead of `from_pretrained()` for local files.

### Adding LoRA Models (Future)

To add a D&D-specific LoRA for better fantasy art:

```python
# In image_generation_service.py (future enhancement)
pipeline.load_lora_weights("path/to/dnd_fantasy_lora.safetensors")
pipeline.fuse_lora(lora_scale=0.7)
```

### Troubleshooting

| Issue | Solution |
|-------|----------|
| `ModuleNotFoundError: torch` | Run `pip install torch` |
| `MPS not available` | Ensure macOS 13+ on Apple Silicon |
| Out of memory during generation | Reduce `IMAGE_DEFAULT_WIDTH/HEIGHT` to 768 |
| Slow first generation | Normal — pipeline loads on first call (~30s) |
| Model download stalls | Check internet; try `huggingface-cli download stabilityai/stable-diffusion-xl-base-1.0` |
| Black images on MPS | Known PyTorch bug — try `torch.mps.empty_cache()` or update PyTorch |

---

## Future Enhancements

1. **LoRA Support**: Load D&D-specific LoRA models for consistent fantasy art style
2. **IP-Adapter**: Character consistency across multiple portraits (requires ComfyUI or advanced diffusers)
3. **ControlNet**: Pose-guided generation for battle scenes
4. **Image-to-Image**: Refine existing images with new prompts
5. **Thumbnail Generation**: Auto-generate smaller versions for game state cards
6. **Flux Upgrade**: Switch to Flux.1 when Apple Silicon support and LoRA ecosystem mature
7. **Gallery View**: Frontend component to browse all generated images for a session
8. **Portrait Storage**: Save portrait URLs on Character model for persistent display in GamePanel
