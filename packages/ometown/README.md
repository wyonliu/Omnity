# OmeTown — The Perpetual Town

**A world where humans and AI coexist. Your Ome lives here, works, socializes, and creates value — even when you're away.**

Not another virtual world — an **async mirror** of real life, powered by AI.

## Quick Start

```bash
cd packages/ometown
npm install
npm run dev          # → http://localhost:5173
```

## Architecture

```
PixiJS 8 (isometric renderer)  →  React 19 (UI: chat, report, panels)
         ↓                                    ↓
    Tiled JSON map              ome-server (FastAPI + WebSocket)
         ↓                                    ↓
  AI-generated tiles            Maxim engine (NPC behavior)
  (Flux LoRA pipeline)          Ome core (personality + memory)
```

## Art Pipeline — Nintendo-Style Compression

Target: **entire town < 3MB**.

| Technique | How | Result |
|-----------|-----|--------|
| **Modular building kit** | 10 walls + 4 roofs + 15 details = hundreds of buildings | Zero unique building art needed |
| **Palette swap** | 1 character sprite × 12 color palettes | 12 distinct characters from 1 sheet |
| **Indexed-color PNG** | 64-color palette via pngquant | ~1KB per tile (vs ~8KB RGBA) |
| **Sprite atlas** | All tiles packed into 1 texture | 1 draw call, <500KB total |
| **Procedural variation** | Runtime: random rotation + scale + color shift | Infinite perceived variety |
| **Seasonal palette** | Same tree + 4 color maps | 4× content at 0 bytes |

See [`assets/ART_SPEC.md`](assets/ART_SPEC.md) for full specification.

### Generate Art

```bash
# Step 1: AI-generate raw tiles (requires OPENROUTER_API_KEY)
python tools/gen_tiles.py --list              # see all 75 tile definitions
python tools/gen_tiles.py --category ground   # generate ground tiles
python tools/gen_tiles.py                     # generate everything

# Step 2: Optimize (quantize, resize, pack atlas)
python tools/optimize_assets.py               # process all raw → optimized
python tools/optimize_assets.py --atlas       # pack into sprite sheets
python tools/optimize_assets.py --report      # size report
```

## Features

### Now
- Isometric 2:1 diamond grid (128×64 tiles)
- Camera pan + zoom
- Character rendering with palette swap
- Click-to-chat with any Ome (SSE streaming)
- Daily report ("what Ome did while you were away")
- A* pathfinding on walkable tiles

### Next
- [ ] Tiled map editor integration (JSON import)
- [ ] AI tile generation + LoRA training
- [ ] WebSocket real-time Ome behavior push
- [ ] Maxim integration (NPC needs-driven behavior)
- [ ] Ome home decoration (furniture placement)
- [ ] Day/night cycle with palette transition

## Part of Omnity

OmeTown is Layer 5 of the [Omnity](../../README.md) stack:

```
SOAP (spatial) → Mindos (brain) → Ome (agent) → Maxim (society) → OmeTown (world)
```

## License

Apache-2.0 — same as the [Omnity monorepo](../../LICENSE).
