#!/usr/bin/env python3
"""
OmeTown Tile Generator — AI-powered isometric art pipeline.

Generates isometric building/ground/nature tiles via Flux or OpenRouter.
Follows ART_SPEC.md: modular kit parts, not whole buildings.

Usage:
    python tools/gen_tiles.py                          # Generate all tiles
    python tools/gen_tiles.py --category ground         # Ground tiles only
    python tools/gen_tiles.py --category buildings       # Building modules only
    python tools/gen_tiles.py --single wall_wood_1x1     # One specific tile
    python tools/gen_tiles.py --list                     # Show all tile definitions

Requires: OPENROUTER_API_KEY in environment (or .env file)
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
RAW_DIR = ASSETS_DIR / "tiles" / "raw"

# Load env
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent.parent / ".env", override=True)
except ImportError:
    pass

# ─── Style prompt (consistent across all tiles) ───
STYLE = (
    "Isometric game tile, cozy village illustration style, "
    "warm watercolor palette with soft shadows, "
    "clean edges suitable for tile-based game, "
    "transparent background, centered in frame, "
    "Studio Ghibli meets Stardew Valley warmth. "
    "No text, no labels, no UI elements."
)

# ─── Tile Definitions ───
TILES = {
    "ground": {
        "grass_01": "Grass ground tile, lush green, slight texture variation",
        "grass_02": "Grass ground tile, lighter green with tiny wildflowers",
        "grass_03": "Grass ground tile, dark green with subtle shadow",
        "grass_04": "Grass ground tile, golden-green, sun-lit meadow feel",
        "path_straight": "Stone cobblestone path, straight section, warm gray stones",
        "path_corner": "Stone cobblestone path, 90-degree corner turn",
        "path_cross": "Stone cobblestone path, four-way intersection",
        "path_end": "Stone cobblestone path, dead end with grass growing between stones",
        "water_01": "Small pond water tile, calm blue-green surface, soft ripples",
        "water_02": "Stream water tile, gentle flowing water with small stones visible",
        "dirt_01": "Dirt ground tile, warm brown earth, slightly uneven",
        "dirt_02": "Dirt ground tile, light sandy brown with small pebbles",
        "plaza_stone_01": "Plaza paving tile, large warm sandstone slabs, clean",
        "plaza_stone_02": "Plaza paving tile, mixed cobblestone pattern, aged look",
        "flower_bed_01": "Garden flower bed tile, colorful mixed flowers in rows",
        "flower_bed_02": "Garden flower bed tile, lavender and roses, tidy borders",
        "bridge": "Small wooden bridge tile over water gap, planks and simple railing",
        "stairs": "Stone staircase tile, 3-4 steps going up, mossy edges",
    },
    "buildings": {
        # Walls
        "wall_wood_1x1": "Wooden wall module, light oak planks, 1 tile wide, cozy cottage style",
        "wall_wood_2x1": "Wooden wall module, light oak planks, 2 tiles wide, cottage style",
        "wall_stone_1x1": "Stone wall module, gray cobblestone masonry, 1 tile wide",
        "wall_stone_2x1": "Stone wall module, gray cobblestone masonry, 2 tiles wide",
        "wall_stucco_1x1": "Stucco wall module, warm cream/beige, Mediterranean style, 1 tile",
        "wall_stucco_2x1": "Stucco wall module, warm cream/beige, Mediterranean style, 2 tiles",
        # Roofs
        "roof_tile_flat": "Clay tile roof module, terracotta red-brown, flat isometric top-down view",
        "roof_thatch": "Thatched roof module, golden straw bundles, cottage style",
        "roof_slate": "Slate roof module, dark blue-gray, clean modern look",
        "roof_garden": "Green roof module, small plants and moss growing on top, living roof",
        # Doors
        "door_wood": "Wooden door, warm brown, simple iron handle, arched top",
        "door_shop": "Shop entrance door, wide double doors, glass panels, welcoming",
        "door_arch": "Stone arched doorway, medieval style, dark wooden door behind",
        # Windows
        "window_small": "Small cottage window, 4-pane, white frame, warm light glow inside",
        "window_large": "Large window, 6-pane, white frame, curtains visible, warm interior light",
        "window_round": "Round porthole window, decorative stone frame",
        # Details
        "sign_hanging": "Hanging wooden shop sign, blank/generic, iron bracket mount",
        "sign_wall": "Wall-mounted wooden sign, simple rectangle, aged look",
        "awning_stripe": "Striped fabric awning, red and white, slightly curved",
        "awning_solid": "Solid color fabric awning, deep green, shop front style",
        "planter_box": "Wooden planter box with flowers, sits on ground or window sill",
        "lamp_post": "Vintage street lamp post, warm glowing light, iron and glass",
        "chimney": "Brick chimney, small, with wisps of smoke",
        "balcony_iron": "Small iron railing balcony, decorative, with flower pot",
        "balcony_wood": "Wooden balcony, simple railing, cottage style",
    },
    "nature": {
        "tree_deciduous_01": "Deciduous tree, round canopy, lush green, medium size",
        "tree_deciduous_02": "Deciduous tree, oval canopy, light green, slightly smaller",
        "tree_deciduous_03": "Deciduous tree, spreading branches, deep green, large",
        "tree_pine_01": "Pine tree, conical shape, dark green, tall",
        "tree_pine_02": "Pine tree, shorter and wider, blue-green needles",
        "bush_01": "Round bush, dense green foliage, small",
        "bush_02": "Flowering bush, green with pink flowers, medium",
        "bush_03": "Hedge bush, rectangular trimmed, formal garden style",
        "rock_01": "Decorative rock, gray, round and smooth",
        "rock_02": "Decorative rocks, cluster of 3 small stones, mossy",
        "rock_03": "Large decorative boulder, gray with lichen patches",
    },
    "props": {
        "bench_wood": "Wooden park bench, simple design, slightly worn",
        "fountain_small": "Small stone fountain, bubbling water, birdbath style",
        "barrel": "Wooden barrel, dark oak with iron bands",
        "crate": "Wooden crate, light wood, slightly open lid",
        "cart": "Small wooden handcart, rustic, with wheel",
        "well": "Stone well with wooden bucket, rope and pulley",
        "mailbox": "Cute wooden mailbox on post, slightly tilted",
        "streetlight": "Modern street light, warm glow, simple pole",
    },
}


def generate_tile(name: str, description: str, api_key: str) -> bytes | None:
    """Generate a single isometric tile via OpenRouter (Gemini Flash)."""
    import requests

    prompt = f"{STYLE}\n\nSpecific tile: {description}. Isometric 30-degree angle view."

    # Using the same model as CaptainCast gen_image.py
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    body = {
        "model": "google/gemini-3.1-flash-image-preview",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 4096,
    }

    proxies = {}
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    if proxy:
        proxies = {"https": proxy, "http": proxy}

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=body,
            proxies=proxies,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()

        # Extract image from response
        for choice in data.get("choices", []):
            content = choice.get("message", {}).get("content", "")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "image_url":
                        url = part["image_url"]["url"]
                        if url.startswith("data:image"):
                            b64 = url.split(",", 1)[1]
                            return base64.b64decode(b64)
            elif isinstance(content, str) and "base64" in content:
                # Try to extract base64 image
                import re
                match = re.search(r'data:image/[^;]+;base64,([A-Za-z0-9+/=]+)', content)
                if match:
                    return base64.b64decode(match.group(1))

        print(f"  ⚠️  No image in response for {name}")
        return None

    except Exception as e:
        print(f"  ❌ Error generating {name}: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Generate isometric tiles via AI")
    parser.add_argument("--category", choices=list(TILES.keys()), help="Generate specific category")
    parser.add_argument("--single", type=str, help="Generate single tile by name")
    parser.add_argument("--list", action="store_true", help="List all tile definitions")
    parser.add_argument("--dry-run", action="store_true", help="Show prompts without generating")
    args = parser.parse_args()

    if args.list:
        for cat, tiles in TILES.items():
            print(f"\n[{cat}] ({len(tiles)} tiles)")
            for name, desc in tiles.items():
                print(f"  {name}: {desc[:60]}...")
        total = sum(len(t) for t in TILES.values())
        print(f"\nTotal: {total} tiles")
        return

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key and not args.dry_run:
        print("Set OPENROUTER_API_KEY in environment or .env")
        sys.exit(1)

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # Determine which tiles to generate
    if args.single:
        targets = {}
        for cat, tiles in TILES.items():
            if args.single in tiles:
                targets[args.single] = tiles[args.single]
                break
        if not targets:
            print(f"Unknown tile: {args.single}")
            return
    elif args.category:
        targets = TILES[args.category]
    else:
        targets = {}
        for tiles in TILES.values():
            targets.update(tiles)

    # Skip already generated
    existing = {f.stem for f in RAW_DIR.glob("*.png")}
    to_generate = {k: v for k, v in targets.items() if k not in existing}

    print(f"Tiles: {len(targets)} total, {len(existing & set(targets))} exist, {len(to_generate)} to generate")

    if args.dry_run:
        for name, desc in to_generate.items():
            print(f"\n[{name}]")
            print(f"  {STYLE}")
            print(f"  Specific: {desc}")
        return

    if not to_generate:
        print("All tiles already generated! Run optimize_assets.py next.")
        return

    for i, (name, desc) in enumerate(to_generate.items()):
        print(f"[{i + 1}/{len(to_generate)}] Generating {name}...")
        img_bytes = generate_tile(name, desc, api_key)

        if img_bytes:
            out_path = RAW_DIR / f"{name}.png"
            out_path.write_bytes(img_bytes)
            print(f"  ✅ Saved ({len(img_bytes) / 1024:.1f}KB)")
        else:
            print(f"  ❌ Failed")

        # Rate limit: 500ms between requests
        if i < len(to_generate) - 1:
            time.sleep(0.5)

    print(f"\nDone! Raw tiles in {RAW_DIR}")
    print("Next: python tools/optimize_assets.py")


if __name__ == "__main__":
    main()
