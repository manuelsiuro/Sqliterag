# D&D / RPG Tools & SDK Research Report

> Compiled: March 2026 | For: sqliteRAG project

---

## Executive Summary

This report catalogs the major free and open-source tools, APIs, SDKs, datasets, and platforms in the D&D / tabletop RPG ecosystem. The goal is to identify resources that can enhance sqliteRAG's AI-powered D&D 5e game engine — whether through data enrichment (SRD APIs, monster databases), procedural content generation (maps, names, loot), integration pathways (VTT exports, Discord bots), or inspiration from peer AI-DM projects.

**Key takeaways:**
- **D&D 5e API** and **Open5e** provide free, no-auth REST APIs covering the entire SRD — ideal for enriching sqliteRAG's RAG pipeline with canonical spell/monster/item data.
- **Python libraries** like `d20`, `dice`, and `dnd-character` can replace or supplement hand-rolled mechanics.
- **Procedural generation** libraries (tcod, Wave Function Collapse) offer algorithmic map/dungeon generation that could feed into sqliteRAG's location system.
- Several **AI Dungeon Master** projects demonstrate LLM + D&D patterns directly relevant to our architecture.

---

## 1. Free D&D 5e APIs

### 1.1 D&D 5e API (dnd5eapi.co)

| Field | Detail |
|-------|--------|
| **URL** | https://www.dnd5eapi.co/ |
| **GitHub** | https://github.com/5e-bits/5e-srd-api |
| **License** | MIT (API code) / OGL 1.0a (SRD data) |
| **Auth** | None required |
| **Format** | REST JSON + GraphQL |
| **Docs** | https://5e-bits.github.io/docs/ |

The most widely used D&D 5e API. Covers the complete SRD: classes, races, spells, monsters, equipment, conditions, traits, features, and more. Fully open, no rate limits for reasonable use. Returns richly structured JSON with cross-references between resources. Also provides a GraphQL endpoint at `https://www.dnd5eapi.co/graphql`.

**Endpoints include:** `/api/spells`, `/api/monsters`, `/api/equipment`, `/api/classes`, `/api/races`, `/api/conditions`, `/api/magic-items`, `/api/features`, `/api/traits`, `/api/proficiencies`, `/api/skills`, `/api/ability-scores`

**Example:**
```
GET https://www.dnd5eapi.co/api/monsters/adult-red-dragon
```

### 1.2 Open5e

| Field | Detail |
|-------|--------|
| **URL** | https://open5e.com/ |
| **API** | https://api.open5e.com/ |
| **GitHub** | https://github.com/open5e/open5e-api |
| **License** | MIT (code) / OGL 1.0a (SRD data) |
| **Auth** | None required |

Goes beyond the base SRD by including third-party OGL content from publishers like Kobold Press (Tome of Beasts, Creature Codex, Deep Magic). Supports search, filtering, and pagination. Django REST Framework backend with SQLite — architecturally analogous to sqliteRAG.

**Key advantage:** Access to 1000+ monsters (vs ~300 in base SRD), additional spells, magic items, and class options from third-party publishers.

**Endpoints:** `/monsters/`, `/spells/`, `/magicitems/`, `/weapons/`, `/armor/`, `/sections/`, `/conditions/`, `/backgrounds/`, `/classes/`, `/races/`, `/feats/`

### 1.3 D&D Beyond (Unofficial / Limited)

D&D Beyond does not provide an official public API. Some community tools scrape or reverse-engineer endpoints, but these are fragile and may violate ToS. **Not recommended** for integration.

### 1.4 Pathfinder / Other Systems

| API | URL | System | License |
|-----|-----|--------|---------|
| **PF2e API (pathfinder2eapi)** | https://api.pathfinder2.fr/ | Pathfinder 2e | OGL |
| **Open Game Content API** | Various community efforts | Multiple | OGL |

---

## 2. Python SDKs & Libraries

### 2.1 Dice Rolling

| Library | PyPI | Description | License |
|---------|------|-------------|---------|
| **d20** | https://pypi.org/project/d20/ | Full dice expression parser (used by Avrae Discord bot). Supports complex notation: `4d6kh3`, `2d20kl1+5`, `8d6ro<3`. Returns structured results with individual rolls. | MIT |
| **dice** | https://pypi.org/project/dice/ | Simple dice roller supporting standard notation (`3d6+2`). Lightweight, no dependencies. | MIT |
| **python-dice** | https://pypi.org/project/python-dice/ | Dice probability calculator — can compute probability distributions, not just roll. Useful for balance analysis. | MIT |
| **xdice** | https://pypi.org/project/xdice/ | Extensive notation: `3d%`, `1d20//2`, `max(1d4+1,1d6)`, `3D6L2` (drop lowest), Fudge dice. | MIT |
| **dndice** | https://rolling.readthedocs.io/ | Python dice roller with D&D-specific notation support. | MIT |
| **rolldice** | https://pypi.org/project/rolldice/ | Minimal dice roller with standard notation support. | MIT |

**Recommendation for sqliteRAG:** `d20` is the gold standard — same library powering Avrae (1M+ Discord servers). Its expression parser handles every D&D notation edge case.

### 2.2 D&D 5e API Wrappers

| Library | PyPI | Description |
|---------|------|-------------|
| **dnd5epy** | https://pypi.org/project/dnd5epy/ | Auto-generated OpenAPI client for dnd5eapi.co. Provides typed Python classes for all SRD resources. |
| **dnd-5e-api-wrapper** | https://github.com/menzenski/dnd-5e-api-wrapper | Simpler Python wrapper around the 5e API. |

### 2.3 Character & Rules Libraries

| Library | PyPI / GitHub | Description | License |
|---------|---------------|-------------|---------|
| **dnd-character** | https://pypi.org/project/dnd-character/ | Create and manage 5e character sheets programmatically. Handles ability scores, HP, proficiencies, leveling. | MIT |
| **dungeonsheets** | https://pypi.org/project/dungeonsheets/ | Generates PDF character sheets from Python/JSON. Auto-calculates attack bonuses and damage. Includes standard weapon/spell definitions. | GPL-3.0 |
| **fantasynames** | https://pypi.org/project/fantasynames/ | Fantasy name generator aligned with D&D/WoW conventions. Pip-installable. | MIT |
| **fictional_names_package** | https://github.com/a-tsagkalidis/fictional_names_package | Race-specific name generation: dragonborn, drow, dwarven, elven, and more. | MIT |
| **dnd5e-srd** | GitHub repos | Various packages providing SRD data as importable Python dicts/dataclasses. | OGL |

### 2.4 General RPG / Game Libraries

| Library | URL | Description | License |
|---------|-----|-------------|---------|
| **tcod (python-tcod)** | https://pypi.org/project/tcod/ | Python bindings for libtcod — roguelike development toolkit. Includes dungeon generation, FOV, pathfinding, BSP trees. | BSD-2 |
| **pygame** | https://pypi.org/project/pygame/ | Game development framework. Useful for rendering maps or prototyping visual components. | LGPL |
| **Hy** | https://hylang.org/ | Lisp dialect for Python — used by some AI game experiments for declarative rule systems. | MIT |

---

## 3. Open Datasets & SRD Resources

### 3.1 5e-database (Canonical SRD JSON)

| Field | Detail |
|-------|--------|
| **GitHub** | https://github.com/5e-bits/5e-database |
| **Format** | JSON files, MongoDB-ready |
| **License** | OGL 1.0a |
| **Size** | ~300 monsters, ~319 spells, ~237 equipment items, 12 classes, 9 races |

The authoritative JSON representation of the D&D 5e SRD. Used as the data source for dnd5eapi.co. Files are organized by resource type: `5e-SRD-Monsters.json`, `5e-SRD-Spells.json`, etc. Can be directly imported into SQLite for local RAG.

### 3.2 Additional Datasets

| Dataset | URL | Description | Format | License |
|---------|-----|-------------|--------|---------|
| **nick-aschenbach/dnd-data** | https://github.com/nick-aschenbach/dnd-data | 5,849 spells, plus monsters, items, classes, backgrounds, species. NPM package. Rich metadata (school, components, damage type). | JSON | MIT |
| **BTMorton/dnd-5e-srd** | https://github.com/BTMorton/dnd-5e-srd | Full SRD in Markdown, JSON, and YAML. Organized by chapter. | JSON/YAML/MD | OGL |
| **tkfu Monster Gist** | https://gist.github.com/tkfu/9819e4ac6d529e225e9fc58b358c3479 | Single JSON file with all SRD monsters. Also available as CSV. | JSON/CSV | OGL |
| **CritterDB** | https://critterdb.com/ | Community monster database with homebrew creatures | JSON export | CC |
| **5e.tools Data** | https://github.com/5etools-mirror-2/5etools-mirror-2.github.io | Comprehensive 5e data (extends beyond SRD) | JSON | Community / Fair Use |
| **Kaggle D&D Datasets** | https://www.kaggle.com/search?q=dungeons+and+dragons | Monsters, spells, items in CSV format — useful for ML/analysis | CSV | Various |
| **D&D Spells JSON** | https://github.com/vorpalhex/srd_spells | All SRD spells in clean, focused JSON | JSON | MIT |
| **Bestiary** | https://github.com/chisaipete/bestiary | D&D monster data with extended fields | JSON | OGL |
| **dnd5e_json_schema** | https://brianwendt.github.io/dnd5e_json_schema/ | Formal JSON Schema for 5e monsters, spells, equipment. Useful for validation. | JSON Schema | MIT |

### 3.3 SRD / OGL Legal Notes

The **Systems Reference Document (SRD) 5.1** is published under the **Open Gaming License (OGL) 1.0a** by Wizards of the Coast. In 2023, WotC also released the SRD 5.1 under **Creative Commons Attribution 4.0 (CC-BY-4.0)**. This means:
- SRD content can be freely used, modified, and redistributed
- Must include OGL notice or CC-BY attribution
- **Required CC-BY-4.0 attribution**: "This work includes material taken from the System Reference Document 5.1 by Wizards of the Coast LLC, available at https://dnd.wizards.com/resources/systems-reference-document. The SRD 5.1 is licensed under the Creative Commons Attribution 4.0 International License."
- Cannot use D&D trademarks (e.g., "Dungeons & Dragons", "D&D Beyond")
- Non-SRD content (e.g., Beholders, Mind Flayers) remains proprietary

---

## 4. Map Generation Tools

### 4.1 Web-Based Generators

| Tool | URL | Type | Cost | Key Features |
|------|-----|------|------|--------------|
| **donjon** | https://donjon.bin.sh/ | Dungeon/World/Encounter | Free | Random dungeon generator, world maps, encounter tables, treasure, NPC names, calendar. No API but output is scrapable HTML/SVG. |
| **Watabou's Generators** | https://watabou.github.io/ | City/Dungeon/Village/Region | Free | Procedural medieval city maps (`city.html`), one-page dungeons, village maps, and **Perilous Shores** (region maps with settlements, dungeons, roads). All export PNG/SVG/JSON. Images free for commercial use. |
| **Azgaar's Fantasy Map Generator** | https://azgaar.github.io/Fantasy-Map-Generator/ | World Map | Free / Open Source | Full-featured world generator: heightmaps, biomes, rivers, nations, religions, trade routes. Exports JSON, SVG, PNG. GitHub: https://github.com/Azgaar/Fantasy-Map-Generator |
| **Dungeon Scrawl** | https://dungeonscrawl.com/ | Battle Map | Free tier / Pro $5/mo | Draw dungeon maps with auto-walls and hatching. Clean export to PNG/SVG. |
| **Inkarnate** | https://inkarnate.com/ | World/Region/Battle Map | Free tier / Pro $25/yr | Professional-quality fantasy maps. Stamp-based editor with art assets. |
| **Wonderdraft** | https://www.wonderdraft.net/ | World/Region Map | $29.99 one-time | Desktop app for world/regional maps. Custom assets supported. |
| **Dungeon Alchemist** | https://www.dungeonalchemist.com/ | Battle Map (AI) | $44.99 one-time (Steam) | AI-powered mapmaker: draw rooms, auto-fills furniture/lighting/walls. 3D view. Exports to VTTs. |
| **Dungeon Fog** | https://www.dungeonfog.com/ | Battle/City Map | Free tier / Pro | Online battle map editor with asset library. |
| **RPG Map Editor II** | https://deepnight.net/tools/rpg-map/ | Dungeon Map | Free | Simple browser-based dungeon drawing tool. |

### 4.2 Programmatic / API-Accessible

| Tool | URL | API? | Notes |
|------|-----|------|-------|
| **donjon** | https://donjon.bin.sh/ | No official API | Parameters in URL allow programmatic generation; output is HTML/image. |
| **Azgaar's FMG** | GitHub repo | JSON export | Can generate maps via headless browser automation; JSON format is well-documented. |
| **Watabou** | GitHub | SVG output | Some generators have URL parameters for seeds. |

---

## 5. Procedural Map Generation Libraries

### 5.1 Python Libraries

| Library | URL | Algorithm | Description |
|---------|-----|-----------|-------------|
| **python-tcod** | https://pypi.org/project/tcod/ | BSP, cellular automata, Dijkstra, A*, FOV | The go-to roguelike library. BSP dungeon generation, field-of-view calculations, pathfinding. Well-documented tutorial: https://rogueliketutorials.com/ |
| **mapgen** | https://github.com/topics/mapgen | Various | Multiple small Python map generators on GitHub |
| **noise** | https://pypi.org/project/noise/ | Perlin/Simplex noise | Generate heightmaps and terrain for world maps |
| **opensimplex** | https://pypi.org/project/opensimplex/ | OpenSimplex noise | Alternative noise library for terrain generation |
| **pywfc** | https://pypi.org/project/pywfc/ | Wave Function Collapse | Python WFC implementation. Generates tilemaps from adjacency rules. Pip-installable. |
| **numpy + scipy** | PyPI | Cellular automata, Voronoi | Cave generation via cellular automata; Voronoi diagrams for region maps |

**Reference repo:** [AtTheMatinee/dungeon-generation](https://github.com/AtTheMatinee/dungeon-generation) — Python implementations of BSP, cellular automata, and random rooms+tunnels algorithms using libtcod.

### 5.2 Algorithms (Language-Agnostic)

| Algorithm | Use Case | Complexity | Description |
|-----------|----------|------------|-------------|
| **BSP (Binary Space Partitioning)** | Dungeons | Low | Recursively subdivides a rectangle into rooms. Classic roguelike technique. |
| **Cellular Automata** | Caves | Low | Random fill → iterative smoothing → organic cave shapes. |
| **Wave Function Collapse (WFC)** | Tile maps | Medium | Constraint-based generation from example patterns. Produces coherent tiled maps. |
| **Drunkard's Walk** | Caves/Tunnels | Low | Random walk carves out organic passages. |
| **Voronoi Diagrams** | Region/World maps | Medium | Divides space into regions — natural for biomes, territories, political boundaries. |
| **Perlin/Simplex Noise** | Terrain | Low | Heightmap generation for continents, mountains, coastlines. |
| **L-systems** | Trees/Rivers/Roads | Medium | Grammar-based generation of branching structures. |
| **Poisson Disk Sampling** | Object placement | Low | Evenly-spaced random placement for towns, forests, POIs on a map. |

### 5.3 JavaScript Libraries

| Library | URL | Description |
|---------|-----|-------------|
| **rot.js** | https://ondras.github.io/rot.js/ | ROguelike Toolkit for JS. Dungeon generation (uniform, digger, cellular), FOV, pathfinding, RNG, scheduling. |
| **wavefunctioncollapse** | npm / GitHub | JS implementations of WFC for tile-based map generation. |
| **simplex-noise** | npm | Simplex noise for terrain heightmaps. |

---

## 6. Virtual Tabletop (VTT) Platforms

### 6.1 Roll20

| Field | Detail |
|-------|--------|
| **URL** | https://roll20.net/ |
| **Cost** | Free tier / Plus $5.99/mo / Pro $9.99/mo |
| **API** | Roll20 API (Pro subscribers) — JavaScript sandbox for custom scripts |
| **Extensibility** | Custom character sheets (HTML/CSS/JS), API scripts, macros |

Market leader with 10M+ users. API allows custom turn trackers, automated combat, dynamic lighting scripts. Character sheet system is highly customizable.

### 6.2 Foundry VTT

| Field | Detail |
|-------|--------|
| **URL** | https://foundryvtt.com/ |
| **Cost** | $50 one-time |
| **API** | Full JavaScript API, module system |
| **GitHub** | Thousands of community modules |

Self-hosted VTT with the most powerful extensibility. Module system allows deep customization: custom systems, automated combat, AI integration modules, REST API bridges. The **dnd5e system module** is the most popular game system.

**Relevant modules:**
- `fvtt-module-furnace` — Advanced macros
- `combat-utility-belt` — Automated combat conditions
- `fvtt-module-api` — [REST API bridge](https://github.com/kakaroto/fvtt-module-api) enabling external HTTP calls to Foundry (push game state from Python backend)
- `azgaar-foundry` — Import Azgaar Fantasy Map Generator maps directly
- Various AI/LLM integration modules emerging

### 6.3 Owlbear Rodeo

| Field | Detail |
|-------|--------|
| **URL** | https://www.owlbear.rodeo/ |
| **Cost** | Free (v1) / Startled Owl $7.99/mo (v2) |
| **API** | Extensions SDK (v2) |
| **GitHub** | https://github.com/owlbear-rodeo |

Lightweight, no-account-needed VTT focused on simplicity. v2 introduced an Extensions SDK for custom tools and integrations.

### 6.4 Other VTTs

| Platform | URL | Cost | Notes |
|----------|-----|------|-------|
| **Talespire** | https://talespire.com/ | $24.99 (Steam) | 3D VTT with mod support |
| **Shmeppy** | https://shmeppy.com/ | Free / $5/mo | Minimalist whiteboard-style VTT |
| **Let's Role** | https://lets-role.com/ | Free tier / Premium | Browser-based, system-agnostic, scriptable |
| **Alchemy RPG** | https://alchemyrpg.com/ | Free tier / Pro | D&D Beyond integration |

---

## 7. RPG Engines & Frameworks

### 7.1 MUD / Text RPG Engines

| Engine | URL | Language | License | Description |
|--------|-----|----------|---------|-------------|
| **Evennia** | https://www.evennia.com/ | Python | BSD-3 | Full-featured MUD/MU* engine built on Django + Twisted. Supports SQLite/PostgreSQL. Python 3.11+. Highly relevant — async, database-backed, extensible command system, built-in web client. |
| **OpenPythonRPG** | https://github.com/rodmarkun/OpenPythonRPG | Python | Open Source | Modular RPG engine with AI integrations. Supports text console, Discord bots, web interfaces, and PyGame. Engine manages intermediary logic; developers focus on content. |
| **Ranvier** | https://ranviermud.com/ | JavaScript | MIT | Node.js MUD engine. Event-driven, modular area/quest system. |

**Evennia** is the most relevant to sqliteRAG — it's a mature Python framework with SQLAlchemy-like ORM, async networking, and a web client. Its command/scripting system for game mechanics is a proven pattern.

### 7.2 Interactive Fiction Engines

| Engine | URL | Language | License | Description |
|--------|-----|----------|---------|-------------|
| **Ink** | https://github.com/inkle/ink | C# (runtime) | MIT | inkle's narrative scripting language. Branching dialogue, variable tracking, conditional content. Used in 80 Days, Heaven's Vault. Python runtime: `inklewriter` or community ports. |
| **Twine** | https://twinery.org/ | JavaScript | GPL-3 | Visual editor for interactive stories. Exports to HTML. Harlowe and SugarCube story formats. |
| **Inform** | https://ganelson.github.io/inform-website/ | Inform 7 | Artistic-2 | Natural-language programming for interactive fiction. Compiles to Z-machine/Glulx. |
| **Ren'Py** | https://www.renpy.org/ | Python | MIT | Visual novel engine. Python-scriptable. Large community. |
| **Inky** | https://github.com/inkle/inky | Electron | MIT | IDE for writing Ink scripts with live preview. |

### 7.3 Game Frameworks

| Framework | URL | Language | License | Description |
|-----------|-----|----------|---------|-------------|
| **Godot** | https://godotengine.org/ | GDScript/C# | MIT | Full game engine with 2D/3D support. GDScript is Python-like. |
| **DOME** | https://domeengine.com/ | Wren | MIT | Lightweight 2D game framework. |
| **Phaser** | https://phaser.io/ | JavaScript | MIT | 2D web game framework — could render maps in browser. |

---

## 8. Character Generators

| Tool | URL | Type | Cost | Features |
|------|-----|------|------|----------|
| **D&D Beyond Character Builder** | https://www.dndbeyond.com/characters | Official | Free (SRD) / Subscription for full content | Official WotC tool. Full character creation with all published content (subscription). SRD-only characters free. |
| **Aidedd Character Builder** | https://aidedd.org/dnd-builder/ | Web | Free | Quick 5e character generation. |
| **Fast Character** | https://fastcharacter.com/ | Web | Free | One-click random 5e character generation. Great for NPCs. |
| **Hero Forge** | https://www.heroforge.com/ | 3D Mini Creator | Free to design / Pay to print or download | 3D character mini designer. Could export tokens for VTT use. |
| **Eigengrau's Generator** | https://github.com/ryceg/Eigengrau-s-Essential-Establishment-Generator | Web/GitHub | Free / Open Source | Generates entire towns with NPCs, relationships, shops, taverns. Rich interconnected content. |
| **NPC Generator (kassoon)** | https://www.kassoon.com/dnd/npc-generator/ | Web | Free | Random NPC with personality, appearance, backstory, plot hook. |
| **Tetra-cube NPC Generator** | https://tetra-cube.com/dnd/dnd-statblock.html | Web | Free | NPC stat block generator with custom stat blocks. |
| **NPC Generator** | https://www.npcgenerator.com/ | Web | Free | Randomized NPCs with attributes, unique descriptions, and plot hooks. |
| **Negatherium NPC Generator** | https://negatherium.com/npc-generator/ | Web | Free | Emphasizes cohesive, multi-faceted, believable characters. |
| **Tetra-cube Character Gen** | https://tetra-cube.com/dnd/dnd-char-gen.html | Web | Free | Full random 5e character generator with sourcebook selection. |

---

## 9. Encounter & Combat Tools

| Tool | URL | Type | Cost | Description |
|------|-----|------|------|-------------|
| **Kobold Fight Club** | https://koboldplus.club/ | Encounter Builder | Free | The standard encounter difficulty calculator. Filters by CR, environment, type. Uses official XP thresholds. |
| **D&D Beyond Encounter Builder** | https://www.dndbeyond.com/encounter-builder | Encounter Builder | Free (SRD) / Sub | Official encounter builder with full monster database. |
| **Improved Initiative** | https://www.improved-initiative.com/ | Initiative Tracker | Free / Open Source | Web-based initiative tracker with monster stat blocks. GitHub: https://github.com/cynicaloptimist/improved-initiative |
| **Owlbear Rodeo Initiative** | Built into VTT | Initiative Tracker | Free | Simple turn tracker integrated into the VTT. |
| **Sly Flourish Encounter Builder** | https://slyflourish.com/encounter_building.html | Encounter Guidelines | Free | Simplified encounter building based on "Lazy DM" principles. |
| **DnD-battler** | https://github.com/matteoferla/DnD-battler | Combat Simulator | Free / Open Source | Python 5e encounter simulator. Runs 1,000 simulations for victory probabilities. Web demo at https://dnd.matteoferla.com/ |
| **DnD5e-CombatSimulator** | https://github.com/asahala/DnD5e-CombatSimulator | Combat Simulator | Free / Open Source | Lightweight Python 3.6 combat simulator. No external dependencies. |
| **Kobold Helper** | https://www.koboldhelper.com/ | All-in-One DM Tool | Free | Combat tracker + initiative tracker + encounter generator combined. |

---

## 10. Random Content Generators

### 10.1 Name Generators

| Tool | URL | Description |
|------|-----|-------------|
| **Fantasy Name Generators** | https://www.fantasynamegenerators.com/ | 10,000+ name generators: fantasy races, medieval, taverns, cities, weapons, everything. |
| **donjon Name Generator** | https://donjon.bin.sh/fantasy/name/ | Random fantasy names by race/culture. |
| **Behind the Name** | https://www.behindthename.com/random/ | Real-world name database with random generator. |
| **Chaotic Shiny** | https://chaoticshiny.com/ | Generators for names, cultures, religions, taverns, NPCs. |
| **Seventh Sanctum** | https://www.seventhsanctum.com/ | Massive generator collection: tavern names, characters, plot ideas, and more. |
| **The Thieves Guild** | https://www.thievesguild.cc/ | Race-specific NPC and name generators for D&D. |

### 10.2 Tavern / Shop / Location Generators

| Tool | URL | Description |
|------|-----|-------------|
| **donjon Inn Generator** | https://donjon.bin.sh/fantasy/inn/ | Random tavern with name, description, menu, patrons, rumors. |
| **Eigengrau's Generator** | https://github.com/ryceg/Eigengrau-s-Essential-Establishment-Generator | Full procedural town with interconnected NPCs, shops, taverns, relationships. |
| **Kassoon Town Generator** | https://www.kassoon.com/dnd/town-generator/ | Quick random town with buildings, NPCs, hooks. |
| **Watabou City Generator** | https://watabou.github.io/city-generator/ | Procedural medieval city maps with districts. |

### 10.3 Loot & Treasure Generators

| Tool | URL | Description |
|------|-----|-------------|
| **donjon Treasure Generator** | https://donjon.bin.sh/5e/random/#type=treasure | Random treasure by CR and hoard type. Follows DMG tables. |
| **D&D Loot Generator** | https://www.dndloot.com/ | Magic item and treasure generators. |
| **Loot Tavern** | https://www.loottavern.com/ | Curated homebrew magic items with art. |

### 10.4 Plot & Quest Generators

| Tool | URL | Description |
|------|-----|-------------|
| **donjon Quest Generator** | https://donjon.bin.sh/fantasy/adventure/ | Random adventure/quest hooks. |
| **Springhole Plot Generators** | https://www.springhole.net/writing_roleplaying_related/index.html | Various plot, character, and worldbuilding generators. |
| **Adventuresmith** | https://github.com/stevesea/adventuresmith | Mobile app with hundreds of random generators from many RPG systems. Open source. |

### 10.5 Random Encounter Tables

| Tool | URL | Description |
|------|-----|-------------|
| **donjon Encounter Generator** | https://donjon.bin.sh/5e/random/ | Random encounters by environment and party level. |
| **Kobold Fight Club** | https://koboldplus.club/ | Can generate random encounters within CR budget. |
| **Goblinist 5e Encounter Generator** | https://tools.goblinist.com/5enc | Quick random encounters with XP budget. |
| **Random Encounters AI** | https://randomencountersai.com/ | AI-powered (GPT-4) encounter table generator. Creative, context-aware encounters. |
| **Chartopia** | https://chartopia.d12dev.com/ | Platform for creating/managing random table collections. Linked charts, nested equations. Massive user library. |

---

## 11. Discord Bots & Chat Integrations

### 11.1 Avrae

| Field | Detail |
|-------|--------|
| **URL** | https://avrae.io/ |
| **GitHub** | https://github.com/avrae/avrae |
| **License** | GPL-3 |
| **Language** | Python |

The premier D&D Discord bot (used in 1M+ servers). Built by the D&D Beyond team. Features:
- Full dice rolling with `d20` library (complex expressions, advantage/disadvantage)
- Character sheet integration (D&D Beyond, GSheet, Dicecloud)
- Initiative tracking with automated combat
- Spell/monster/item lookups from SRD + D&D Beyond
- Custom aliases and scripting (Draconic — Python-like DSL)
- **Relevant architecture**: Python async, uses `d20` library, SRD data lookups, tool-calling patterns

### 11.2 Other RPG Discord Bots

| Bot | URL | Description |
|-----|-----|-------------|
| **DiceParser** | https://github.com/Rolisteam/DiceParser | Multi-system dice bot with probability analysis. C++ core with Discord frontend. |
| **RPG Sage** | Discord | Pathfinder 2e focused bot with character management. |
| **Tupper / PluralKit** | Discord | RP-focused bots for character proxying (speaking as different characters). |
| **SideQuest** | Discord | Quest tracking and party management bot. |
| **GameMaster Bot** | Discord | General RPG bot with dice, initiative, character sheets. |
| **RPGBot** | https://github.com/henry232323/RPGBot | Open-source Discord RPG bot with inventory, market/economy, team setups, server-unique characters. |
| **ApocaBot** | https://github.com/apocabot/ApocaBot | Bot for Powered by the Apocalypse (PbtA) games. In-chat character sheets and stat-based rolls. |
| **RPG Sessions** | https://rpgsessions.com/ | Integrated bot: character sheets, dice, initiative, XP, destiny points. Focused on FFG narrative dice RPGs. |
| **UnbelievaBoat** | https://unbelievaboat.com/ | Economy/currency bot — pattern for in-game economy systems. |

---

## 12. Sound & Music Tools

### 12.1 Tabletop Audio Platforms

| Tool | URL | Cost | Description |
|------|-----|------|-------------|
| **Syrinscape** | https://syrinscape.com/ | Free tier / Sub $7-14/mo | Professional tabletop audio. 1000s of soundscapes: dungeons, taverns, combat, weather. Has a Remote Control API for integration. |
| **Tabletop Audio** | https://tabletopaudio.com/ | Free | 200+ free 10-minute ambient audio tracks organized by environment (tavern, forest, dungeon, etc.). No API but direct MP3 links. |
| **Kenku FM** | https://kenku.fm/ | Free | Discord-integrated audio player for tabletop. Stream ambient sounds into voice channels. |
| **Ambient Mixer** | https://www.ambient-mixer.com/ | Free | Create custom soundscapes by mixing individual ambient sounds. RPG category at rpg.ambient-mixer.com. |
| **TableTone** | https://www.tabletone.app/ | Freemium | Interactive TTRPG audio app. Studio-quality music, ambient sounds, SFX. 100K+ downloads. Android/iOS, Foundry VTT planned. |
| **myNoise** | https://mynoise.net/ | Free | Customizable noise generators with per-frequency sliders. Hundreds of soundscapes. |
| **Ambient Realms** | https://www.ambientrealms.com/ | Free | D&D-focused tabletop ambient soundscapes. |

### 12.2 Music Generation

| Tool | URL | Description |
|------|-----|-------------|
| **AIVA** | https://www.aiva.ai/ | AI music composer — can generate fantasy/orchestral tracks. Free tier available. |
| **Mubert** | https://mubert.com/ | AI-generated ambient music streams. Has an API for programmatic generation. |
| **Suno** | https://suno.com/ | AI music generation from text prompts. Could generate session-specific battle/tavern music. |
| **Soundverse AI** | https://www.soundverse.ai/ | AI music generation for gaming. Custom ambient tracks and adaptive soundtracks from text prompts. |

---

## 13. AI / LLM D&D Projects

### 13.1 AI Dungeon Master Projects

| Project | URL | Description | Architecture |
|---------|-----|-------------|--------------|
| **AI Dungeon** | https://play.aidungeon.com/ | The original AI text adventure. Uses large language models for open-ended storytelling. Commercial product, pioneer of the space. | Cloud LLM, proprietary |
| **TavernAI / SillyTavern** | https://github.com/SillyTavern/SillyTavern | Open-source chat frontend for LLMs with character cards, world lore, and RP features. Supports local models (Ollama, llama.cpp). | Node.js, multi-backend, character card system |
| **KoboldAI** | https://github.com/KoboldAI/KoboldAI-Client | AI-assisted writing/RP tool. Supports local models. Memory system, world info, author's note features. | Python, Gradio UI, local inference |
| **tegridydev/dnd-llm-game** | https://github.com/tegridydev/dnd-llm-game | Streamlit app using **Ollama** local LLMs as D&D DM. Character generation, turn-based adventures, AI party members. **Closest architectural match to sqliteRAG.** | Python, Ollama, Streamlit |
| **deusversus/aidm** | https://github.com/deusversus/aidm | Agentic RPG platform with 24+ specialized AI agents, ChromaDB-backed narrative memory, multi-phase turn lifecycle, Session Zero character creation. | Multi-agent, vector memory |
| **davidpm1021/ai-dungeon-master** | https://github.com/davidpm1021/ai-dungeon-master | Discord bot with vector memory (pgvector), Redis ephemeral state, dual model approach (Claude-3 + Mistral-7B). | Dual model, vector memory |
| **fedefreak92/dungeon-master-ai-project** | https://github.com/fedefreak92/dungeon-master-ai-project | Modular Python backend for D&D 5e with state machine, map system, NPCs, items, skill checks, inventory. | Python, state machine |

### 13.1b CALYPSO (Academic Research)

| Field | Detail |
|-------|--------|
| **Paper** | https://arxiv.org/abs/2308.07540 |
| **GitHub** | https://github.com/northern-lights-province/calypso-aiide-artifact |
| **Published** | AAAI AIIDE 2023 (UPenn) |

LLM-powered DM assistant (Discord bot) with three interfaces: monster understanding, encounter brainstorming, scene description. Tested with 71 players over 4 months. Found LLMs produce "high-fidelity text suitable for direct presentation to players" and "low-fidelity ideas DMs could develop further."

### 13.2 LLM + RPG Tool-Use Patterns

| Project | URL | Description |
|---------|-----|-------------|
| **LangChain RPG Agents** | GitHub examples | LangChain agents with D&D tool functions (dice rolling, lookups, combat resolution). Similar pattern to sqliteRAG's agent loop. |
| **Function-Calling DM** | Various | Projects using OpenAI/Anthropic function calling for structured D&D actions — mirrors sqliteRAG's tool-calling architecture. |
| **TextWorld (Microsoft)** | https://github.com/microsoft/TextWorld | Framework for training RL agents in text-based games. Academic but relevant for understanding text game state management. |
| **LIGHT (Facebook/Meta)** | https://github.com/facebookresearch/LIGHT | Research platform for large-scale fantasy text adventure. Crowdsourced world with 600+ locations, 1700+ characters. | Python, PyTorch |

### 13.3 RAG + RPG Patterns

| Concept | Description | Relevance to sqliteRAG |
|---------|-------------|----------------------|
| **World Lore RAG** | Embedding world descriptions, NPC backstories, and session notes for retrieval during play. | Directly matches sqliteRAG's current architecture. |
| **SRD RAG** | Embedding the SRD (spells, monsters, rules) for in-context rule lookups. | Could supplement sqliteRAG's existing RAG with canonical D&D rules. |
| **Session Memory** | Using vector similarity to recall relevant past events during long campaigns. | Already implemented in sqliteRAG (Phase 2.6-2.8). |
| **Character Voice** | Fine-tuning or prompting for consistent NPC personality across sessions. | Relevant to sqliteRAG's NPC system and knowledge graph. |

---

## 14. Tile & Asset Libraries

### 14.1 Free Map Tiles & Tokens

| Resource | URL | License | Description |
|----------|-----|---------|-------------|
| **2-Minute Tabletop** | https://2minutetabletop.com/ | Free + Premium packs | High-quality battle map assets, tokens, and tiles. Some free, bulk packs paid. |
| **Forgotten Adventures** | https://www.forgotten-adventures.net/ | Free + Patreon | Massive library of map assets, tokens, and battlemaps. Foundry VTT module available. |
| **Tom Cartos** | https://www.patreon.com/tomcartos | Free + Patreon | Battle maps and map-making assets. |
| **Game-icons.net** | https://game-icons.net/ | CC-BY-3.0 | 4000+ RPG-themed icons (swords, potions, shields, spells). SVG format. Ideal for UI elements. |
| **OpenGameArt** | https://opengameart.org/ | CC / GPL / Public Domain | Large collection of 2D/3D game assets including RPG tilesets, sprites, icons. |
| **Kenney.nl** | https://kenney.nl/assets | CC0 (Public Domain) | High-quality free game assets. Includes RPG tileset, UI elements, icons. |
| **Liberated Pixel Cup (LPC)** | https://opengameart.org/content/liberated-pixel-cup-lpc-base-assets-sprites-map-tiles | CC-BY-SA 3.0 / GPLv3 | Consistent-style pixel art from Mozilla/FSF/CC competition. Character sprites, map tiles, environmental assets. Ideal base tileset for a web map renderer. |
| **Itch.io CC0 Tilesets** | https://itch.io/game-assets/assets-cc0/free/tag-tileset | CC0 (Public Domain) | Curated free tilesets — no attribution required. 16x16 DungeonTileset II, Ninja Adventure, etc. |
| **CartographyAssets** | https://cartographyassets.com/ | Various | Largest asset library specifically for mapmakers and TTRPG. Assets for Wonderdraft, Dungeondraft, Inkarnate. |
| **Devin Night Tokens** | https://immortalnights.com/tokensite/ | Free + Premium | 950+ free professionally designed tokens with consistent art style. |
| **Itch.io RPG Assets** | https://itch.io/game-assets/tag-rpg | Various (many free) | Large marketplace for RPG game assets — tilesets, character sprites, UI kits. |

### 14.2 Token Makers

| Tool | URL | Description |
|------|-----|-------------|
| **Token Stamp** | https://rolladvantage.com/tokenstamp/ | Free browser-based VTT token creator. Upload image, apply border/frame. |
| **Token Tool** | https://www.rptools.net/toolbox/token-tool/ | Desktop app for creating VTT tokens with frames and effects. |
| **Hero Forge** | https://www.heroforge.com/ | 3D character mini designer — export 2D token images. |

---

## 15. Relevance to sqliteRAG

### High-Priority Integrations

| Resource | Integration Path | Effort | Impact |
|----------|-----------------|--------|--------|
| **5e-database JSON** | Import SRD JSON directly into SQLite + sqlite-vec for RAG | Low | High — canonical spell/monster/item data for AI lookups |
| **D&D 5e API** | HTTP tool calling from agent loop | Low | High — real-time SRD lookups during gameplay |
| **Open5e API** | HTTP tool calling (same pattern) | Low | High — extended monster/spell database |
| **d20 library** | Replace custom dice roller in `rpg_service.py` | Low | Medium — battle-tested dice parsing |
| **dnd-character** | Supplement character creation tools | Medium | Medium — validated character mechanics |
| **game-icons.net** | Download SVG icons for frontend renderers | Low | Medium — visual polish for tool results |

### Medium-Priority Enhancements

| Resource | Integration Path | Effort | Impact |
|----------|-----------------|--------|--------|
| **python-tcod BSP** | Algorithmic dungeon generation for `create_location` | Medium | High — auto-generated dungeon maps |
| **Eigengrau's Generator** | Port town generation logic to Python | Medium | High — rich interconnected location content |
| **Tabletop Audio** | Embed ambient sound links in location/environment responses | Low | Medium — immersion enhancement |
| **Syrinscape API** | Trigger soundscapes based on game events | Medium | Medium — automated audio |
| **Foundry VTT modules** | Export game state to Foundry format | High | Medium — VTT interop |

### Architectural Inspiration

| Project | Lesson for sqliteRAG |
|---------|---------------------|
| **Avrae** | Tool-calling patterns, `d20` dice library, character sheet integration architecture |
| **Evennia** | Python MUD engine — command system, async game loops, database-backed world state |
| **SillyTavern** | Character card system, world lore injection, multi-backend LLM support |
| **KoboldAI** | Memory system (world info, author's note) — parallels to sqliteRAG's MemGPT eviction |
| **Ink** | Narrative branching language — could define quest/dialogue trees declaratively |
| **tegridydev/dnd-llm-game** | Same Ollama-based architecture. Patterns for prompt engineering and turn management. |
| **deusversus/aidm** | Multi-agent + vector memory — most similar to sqliteRAG's RAG + knowledge graph + MemGPT eviction. |
| **CALYPSO** | Academic validation of LLM-as-DM approach. Tested with real players over 4 months. |
| **RPGBot (Discord)** | Inventory and economy system — reference for item transfer and market mechanics. |

---

## Sources

### APIs
- https://www.dnd5eapi.co/
- https://5e-bits.github.io/docs/
- https://open5e.com/
- https://api.open5e.com/
- https://github.com/5e-bits/5e-srd-api
- https://github.com/open5e/open5e-api

### Python Libraries
- https://pypi.org/project/d20/
- https://pypi.org/project/dice/
- https://pypi.org/project/xdice/
- https://pypi.org/project/dnd-character/
- https://pypi.org/project/dungeonsheets/
- https://pypi.org/project/dnd5epy/
- https://pypi.org/project/tcod/
- https://pypi.org/project/noise/
- https://pypi.org/project/opensimplex/
- https://pypi.org/project/pywfc/
- https://pypi.org/project/fantasynames/
- https://github.com/a-tsagkalidis/fictional_names_package

### Datasets
- https://github.com/5e-bits/5e-database
- https://github.com/nick-aschenbach/dnd-data
- https://github.com/BTMorton/dnd-5e-srd
- https://github.com/vorpalhex/srd_spells
- https://brianwendt.github.io/dnd5e_json_schema/
- https://game-icons.net/
- https://opengameart.org/
- https://kenney.nl/assets

### Map Tools
- https://donjon.bin.sh/
- https://watabou.github.io/
- https://watabou.github.io/city.html
- https://watabou.github.io/perilous-shores/
- https://azgaar.github.io/Fantasy-Map-Generator/
- https://github.com/Azgaar/Fantasy-Map-Generator
- https://dungeonscrawl.com/
- https://inkarnate.com/
- https://www.wonderdraft.net/
- https://www.dungeonalchemist.com/

### Procedural Generation
- https://rogueliketutorials.com/
- https://github.com/AtTheMatinee/dungeon-generation
- https://github.com/mxgmn/WaveFunctionCollapse
- https://ondras.github.io/rot.js/
- https://blog.jrheard.com/procedural-dungeon-generation-cellular-automata

### VTT Platforms
- https://roll20.net/
- https://foundryvtt.com/
- https://foundryvtt.com/api/
- https://github.com/kakaroto/fvtt-module-api
- https://www.owlbear.rodeo/
- https://docs.owlbear.rodeo/extensions/apis/

### RPG Engines
- https://www.evennia.com/
- https://github.com/evennia/evennia
- https://github.com/rodmarkun/OpenPythonRPG
- https://github.com/inkle/ink
- https://twinery.org/
- https://ganelson.github.io/inform-website/
- https://www.renpy.org/

### Character & Encounter Tools
- https://www.dndbeyond.com/
- https://koboldplus.club/
- https://github.com/fantasycalendar/kobold-plus-fight-club
- https://www.improved-initiative.com/
- https://github.com/cynicaloptimist/improved-initiative
- https://fastcharacter.com/
- https://www.fantasynamegenerators.com/
- https://github.com/ryceg/Eigengrau-s-Essential-Establishment-Generator
- https://www.npcgenerator.com/
- https://github.com/matteoferla/DnD-battler
- https://github.com/asahala/DnD5e-CombatSimulator

### Discord Bots
- https://avrae.io/
- https://github.com/avrae/avrae
- https://github.com/Rolisteam/DiceParser
- https://github.com/henry232323/RPGBot
- https://github.com/apocabot/ApocaBot
- https://rpgsessions.com/

### Sound
- https://syrinscape.com/
- https://tabletopaudio.com/
- https://kenku.fm/
- https://www.tabletone.app/
- https://rpg.ambient-mixer.com/
- https://mynoise.net/
- https://www.soundverse.ai/

### AI Projects
- https://play.aidungeon.com/
- https://github.com/SillyTavern/SillyTavern
- https://github.com/KoboldAI/KoboldAI-Client
- https://github.com/microsoft/TextWorld
- https://github.com/facebookresearch/LIGHT
- https://github.com/tegridydev/dnd-llm-game
- https://github.com/deusversus/aidm
- https://github.com/davidpm1021/ai-dungeon-master
- https://github.com/fedefreak92/dungeon-master-ai-project
- https://arxiv.org/abs/2308.07540 (CALYPSO)
- https://github.com/northern-lights-province/calypso-aiide-artifact

### Asset Libraries
- https://2minutetabletop.com/
- https://www.forgotten-adventures.net/
- https://opengameart.org/content/liberated-pixel-cup-lpc-base-assets-sprites-map-tiles
- https://cartographyassets.com/
- https://immortalnights.com/tokensite/
- https://rolladvantage.com/tokenstamp/
- https://www.rptools.net/toolbox/token-tool/
- https://itch.io/game-assets/tag-rpg
- https://itch.io/game-assets/assets-cc0/free/tag-tileset
