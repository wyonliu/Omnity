# OmeTown Art Specification — Nintendo-Style Compression

## Budget

**Total target: < 3MB** for the entire town.

| Category | Count | Per-asset | Total |
|----------|-------|-----------|-------|
| Ground tiles | 24 | ~1KB (indexed PNG) | 24KB |
| Building modules | 40 | ~3KB (indexed PNG) | 120KB |
| Building assembled | 0 | procedural from modules | 0 |
| Furniture/props | 30 | ~2KB | 60KB |
| Character atlas | 1 | ~200KB (all sprites) | 200KB |
| Trees/nature | 8 | ~2KB | 16KB |
| UI elements | 20 | ~1KB | 20KB |
| **Subtotal** | | | **~440KB** |
| Audio (ambient) | 1 | ~500KB (OGG) | 500KB |
| **Grand total** | | | **< 1MB** |

## Tile System

### Grid
- Isometric 30° projection
- Tile size: **128×64 px** (diamond shape)
- Each tile is a transparent PNG with indexed color (8-bit, max 64 colors)

### Ground Tiles (24 types)
```
grass_01..04          — 4 variations (prevent obvious tiling)
path_straight         — stone path
path_corner           — 4 rotations via CSS/code
path_cross
path_end
water_01..02          — pond/stream
dirt_01..02
flower_bed_01..02
plaza_stone_01..02
bridge
stairs
```

### Compression Technique
1. Design at 128×64 in full color
2. Quantize to 64-color indexed palette via `pngquant --quality=60-80`
3. Result: ~800 bytes per ground tile (vs ~8KB for 32-bit RGBA)

## Building Module Kit (Nintendo Approach)

Instead of generating whole buildings, generate **modules** that snap together:

### Wall Modules (5 styles × 2 sizes)
```
wall_wood_1x1, wall_wood_2x1
wall_stone_1x1, wall_stone_2x1
wall_brick_1x1, wall_brick_2x1
wall_stucco_1x1, wall_stucco_2x1
wall_glass_1x1, wall_glass_2x1
```

### Roof Modules (4 styles)
```
roof_tile_flat        — Japanese/Chinese clay tile
roof_thatch           — rural/cottage
roof_slate            — modern
roof_garden           — green roof with plants
```

### Detail Modules (decorative overlays)
```
door_wood, door_shop, door_arch
window_small, window_large, window_round
sign_hanging, sign_wall
awning_stripe, awning_solid
planter_box, lamp_post, chimney
balcony_iron, balcony_wood
```

### Assembly Rules
```
building = wall_base + wall_upper + roof + door + windows[] + details[]

Example:
  Café = wall_stucco_2x1 + wall_stucco_1x1 + roof_tile_flat
       + door_shop + window_large×2 + awning_stripe + sign_hanging
       + planter_box×2
```

**Why this works**: 10 wall modules + 4 roofs + 15 details = 29 modules → **hundreds of unique buildings** through combinatorics. Same as how Nintendo makes hundreds of Zelda houses from ~20 pieces.

## Character Sprites

### Base Character
One **master sprite sheet**: 128×256 px atlas containing:
```
Directions: 4 (down, up, left, right) — mirror left for right to save 25%
States: idle (2 frames), walk (4 frames), sit (1 frame)
Total: 4 directions × 7 frames = 28 sprites
Sprite size: 32×48 px each
```

### Palette Swap for Variety
The base sprite uses **4-tone indexed color**:
```
Tone 1: skin
Tone 2: hair
Tone 3: outfit primary
Tone 4: outfit secondary
```

Swap at runtime via PixiJS ColorMatrixFilter or pre-generated palette variants:
```
12 palette presets → 12 visually distinct characters from 1 sprite sheet
```

### Occupation Overlays
Tiny accessory sprites (16×16) composited at runtime:
```
hat_farmer, hat_chef, apron, hammer, book, stethoscope,
backpack, glasses, scarf, flower_crown
```

**Total character budget**: 1 base sheet (28 sprites × 32×48 = ~50KB) + 12 palettes (code, 0 bytes) + 10 accessories (~10KB) = **~60KB for unlimited characters**.

## Nature Assets

```
tree_deciduous_01..03   — 3 variations, palette-swapped for seasons
tree_pine_01..02        — evergreen
bush_01..03             — low foliage
flower_01..04           — seasonal color
rock_01..03             — decorative
```

**Seasonal variation**: Same tree PNG, different palette:
- Spring: light green + pink blossoms
- Summer: deep green
- Autumn: orange/gold
- Winter: bare branches + snow overlay

4 seasons × 1 base tree = **4× perceived variety at 0 extra bytes**.

## Color Palette

Global palette (OmeTown brand, inspired by Omnity + Ghibli warmth):

```
Background:    #1a1a2e (deep navy, night)  /  #f5e6d3 (warm cream, day)
Ground:        #8b7355, #a0936e, #6d8b4e, #4a7c59
Buildings:     #d4a574, #c89b7b, #b8860b, #8b6914
Roofs:         #8b4513, #cd853f, #556b2f, #708090
Accent gold:   #c8a96e (Omnity brand)
Water:         #4a90d9, #5ba3e6
UI text:       #2d2d2d (day) / #e0e0e0 (night)
```

## AI Generation Pipeline

### Step 1: Style Anchors (one-time, human-curated)
Generate 50 isometric buildings in Midjourney/Flux with prompt:
```
Isometric building tile, cozy village style, warm watercolor illustration,
soft shadows, transparent background, game asset, 128x128px,
Studio Ghibli meets Stardew Valley, no text
```
Hand-pick the **16 best** that share consistent style.

### Step 2: Train Flux Kontext LoRA
Platform: Scenario.com or local ComfyUI
- Input: 16 curated reference tiles
- Training: ~30 minutes on A100
- Output: LoRA checkpoint (~100MB)

### Step 3: Batch Generation
```python
# Generate all building modules
for module in MODULES:
    prompt = f"Isometric {module}, [trigger_word], transparent bg, 128x128"
    image = flux_generate(prompt, lora=LORA_PATH)
    save(f"assets/tiles/raw/{module}.png")
```

### Step 4: Post-Process (tools/optimize_assets.py)
```
For each raw PNG:
  1. Resize to exact tile dimensions (128×64 or 128×128)
  2. Remove background (alpha threshold)
  3. Quantize: pngquant --quality=60-80 --colors=64
  4. Optstrip: optipng -o7
  5. Validate: check file size < 5KB
  6. Pack into sprite atlas: TexturePacker → 1 atlas PNG + JSON
```

### Step 5: Tiled Map
- Open Tiled Map Editor
- Import atlas as tileset
- Paint the street layout
- Export as JSON → PixiJS loads directly

## File Structure
```
assets/
├── ART_SPEC.md          ← this file
├── palette.json         ← global color palette definition
├── tiles/
│   ├── raw/             ← AI-generated originals (not in git, > 3MB)
│   ├── ground/          ← optimized ground tiles (indexed PNG)
│   ├── buildings/       ← optimized building modules
│   ├── nature/          ← trees, bushes, flowers
│   └── atlas.png + atlas.json  ← packed sprite atlas
├── characters/
│   ├── base_sprite.png  ← master character sheet
│   ├── palettes.json    ← 12 color swap definitions
│   └── accessories/     ← overlay sprites
└── ui/
    ├── icons/           ← chat bubbles, buttons
    └── panels/          ← dialog frames
```

## Quality Gate

Before any asset enters `assets/`:
- [ ] File size < 5KB (tiles) or < 50KB (atlas)
- [ ] Indexed color (8-bit palette, ≤ 64 colors)
- [ ] Transparent background (no white box)
- [ ] Consistent isometric angle (30°)
- [ ] Passes visual consistency check against style anchors
- [ ] No AI artifacts (extra fingers, broken geometry)
