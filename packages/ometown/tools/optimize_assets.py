#!/usr/bin/env python3
"""
OmeTown Asset Optimizer — Nintendo-style compression pipeline.

Takes raw AI-generated PNGs and produces game-ready indexed-color tiles.
Target: each tile < 5KB, total atlas < 500KB.

Usage:
    python tools/optimize_assets.py                     # Process all raw/ → optimized
    python tools/optimize_assets.py --input raw/cafe.png  # Single file
    python tools/optimize_assets.py --atlas              # Pack into sprite atlas
    python tools/optimize_assets.py --report             # Size report
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
RAW_DIR = ASSETS_DIR / "tiles" / "raw"
TILE_SIZE = (128, 64)       # Isometric diamond: width × height
BUILDING_SIZE = (128, 128)  # Taller for buildings
MAX_COLORS = 64
MAX_TILE_KB = 5
MAX_ATLAS_KB = 500

# Require Pillow
try:
    from PIL import Image
except ImportError:
    print("pip install Pillow")
    sys.exit(1)


def remove_background(img: Image.Image, threshold: int = 240) -> Image.Image:
    """Remove near-white background, make transparent."""
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    pixels = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if r > threshold and g > threshold and b > threshold:
                pixels[x, y] = (0, 0, 0, 0)
    return img


def quantize_indexed(img: Image.Image, colors: int = MAX_COLORS) -> Image.Image:
    """Convert to indexed color (palette mode) for maximum compression."""
    # Preserve alpha: separate alpha, quantize RGB, reapply
    if img.mode == "RGBA":
        alpha = img.split()[3]
        # Quantize the RGB
        rgb = img.convert("RGB")
        quantized = rgb.quantize(colors=colors, method=Image.Quantize.MEDIANCUT)
        # Convert back to RGBA and apply original alpha
        result = quantized.convert("RGBA")
        result.putalpha(alpha)
        return result
    else:
        return img.quantize(colors=colors, method=Image.Quantize.MEDIANCUT).convert("RGBA")


def optimize_single(src: Path, dst: Path, size: tuple[int, int] | None = None) -> dict:
    """Optimize a single PNG: resize → remove bg → quantize → save."""
    img = Image.open(src).convert("RGBA")
    original_size = src.stat().st_size

    # Auto-detect tile type by filename
    if size is None:
        name = src.stem.lower()
        if any(k in name for k in ("wall", "roof", "door", "window", "building")):
            size = BUILDING_SIZE
        else:
            size = TILE_SIZE

    # Resize if needed (maintain aspect, fit within target)
    if img.size != size:
        img.thumbnail(size, Image.Resampling.LANCZOS)
        # Pad to exact size with transparent pixels
        padded = Image.new("RGBA", size, (0, 0, 0, 0))
        offset = ((size[0] - img.width) // 2, (size[1] - img.height) // 2)
        padded.paste(img, offset)
        img = padded

    # Remove white background
    img = remove_background(img)

    # Quantize to indexed color
    img = quantize_indexed(img, MAX_COLORS)

    # Save
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst, "PNG", optimize=True)

    # Try pngquant if available (even better compression)
    try:
        subprocess.run(
            ["pngquant", "--quality=60-80", f"--colors={MAX_COLORS}",
             "--force", "--output", str(dst), str(dst)],
            capture_output=True, timeout=10
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # pngquant not installed, Pillow quantize is fine

    final_size = dst.stat().st_size
    ratio = final_size / original_size if original_size > 0 else 0

    return {
        "file": dst.name,
        "original_kb": round(original_size / 1024, 1),
        "final_kb": round(final_size / 1024, 1),
        "compression": f"{(1 - ratio) * 100:.0f}%",
        "ok": final_size / 1024 < MAX_TILE_KB,
    }


def pack_atlas(tile_dir: Path, output: Path, atlas_name: str = "atlas") -> dict:
    """Pack all tiles into a single sprite atlas + JSON descriptor."""
    tiles = sorted(tile_dir.glob("*.png"))
    if not tiles:
        print(f"No tiles found in {tile_dir}")
        return {}

    # Load all tiles
    images = [(t.stem, Image.open(t).convert("RGBA")) for t in tiles]

    # Calculate atlas dimensions (square-ish)
    count = len(images)
    cols = math.ceil(math.sqrt(count))
    rows = math.ceil(count / cols)

    # Use largest tile size
    max_w = max(img.width for _, img in images)
    max_h = max(img.height for _, img in images)
    atlas_w = cols * max_w
    atlas_h = rows * max_h

    atlas = Image.new("RGBA", (atlas_w, atlas_h), (0, 0, 0, 0))
    frames = {}

    for i, (name, img) in enumerate(images):
        col = i % cols
        row = i // cols
        x = col * max_w
        y = row * max_h
        atlas.paste(img, (x, y))
        frames[name] = {
            "frame": {"x": x, "y": y, "w": img.width, "h": img.height},
            "sourceSize": {"w": img.width, "h": img.height},
        }

    # Save atlas PNG
    atlas_png = output / f"{atlas_name}.png"
    atlas.save(atlas_png, "PNG", optimize=True)

    # Save JSON descriptor (PixiJS spritesheet format)
    atlas_json = output / f"{atlas_name}.json"
    descriptor = {
        "frames": frames,
        "meta": {
            "image": f"{atlas_name}.png",
            "size": {"w": atlas_w, "h": atlas_h},
            "scale": 1,
        },
    }
    atlas_json.write_text(json.dumps(descriptor, indent=2))

    size_kb = atlas_png.stat().st_size / 1024
    print(f"Atlas: {atlas_png.name} ({atlas_w}×{atlas_h}, {count} tiles, {size_kb:.1f}KB)")

    return {
        "atlas": atlas_png.name,
        "tiles": count,
        "size_kb": round(size_kb, 1),
        "ok": size_kb < MAX_ATLAS_KB,
    }


def report(optimized_dir: Path) -> None:
    """Print size report for all optimized assets."""
    total = 0
    files = sorted(optimized_dir.rglob("*.png"))
    print(f"\n{'File':<40} {'Size':>8}")
    print("-" * 50)
    for f in files:
        size = f.stat().st_size
        total += size
        kb = size / 1024
        flag = " ⚠️" if kb > MAX_TILE_KB and "atlas" not in f.name else ""
        print(f"{f.name:<40} {kb:>7.1f}KB{flag}")
    print("-" * 50)
    print(f"{'TOTAL':<40} {total / 1024:>7.1f}KB")
    print(f"{'Budget':<40} {MAX_ATLAS_KB:>7}KB")
    print(f"{'Status':<40} {'✅ Under budget' if total / 1024 < MAX_ATLAS_KB else '❌ Over budget!'}")


def main():
    parser = argparse.ArgumentParser(description="OmeTown asset optimizer")
    parser.add_argument("--input", type=Path, help="Single file to optimize")
    parser.add_argument("--atlas", action="store_true", help="Pack tiles into atlas")
    parser.add_argument("--report", action="store_true", help="Size report")
    parser.add_argument("--output", type=Path, default=ASSETS_DIR / "tiles", help="Output directory")
    args = parser.parse_args()

    if args.report:
        report(args.output)
        return

    if args.atlas:
        # Pack ground, buildings, nature into separate atlases
        for category in ("ground", "buildings", "nature"):
            cat_dir = args.output / category
            if cat_dir.exists() and list(cat_dir.glob("*.png")):
                pack_atlas(cat_dir, args.output, f"{category}_atlas")
        return

    if args.input:
        result = optimize_single(args.input, args.output / args.input.name)
        print(json.dumps(result, indent=2))
        return

    # Batch: process all raw/ files
    if not RAW_DIR.exists():
        print(f"No raw assets directory at {RAW_DIR}")
        print("Generate tiles first: python tools/gen_tiles.py")
        return

    results = []
    for src in sorted(RAW_DIR.glob("*.png")):
        # Route to correct output subdirectory
        name = src.stem.lower()
        if any(k in name for k in ("grass", "path", "water", "dirt", "plaza", "bridge", "stairs", "flower_bed")):
            dst_dir = args.output / "ground"
        elif any(k in name for k in ("tree", "bush", "rock", "flower")):
            dst_dir = args.output / "nature"
        else:
            dst_dir = args.output / "buildings"

        result = optimize_single(src, dst_dir / src.name)
        results.append(result)
        status = "✅" if result["ok"] else "⚠️"
        print(f"  {status} {result['file']}: {result['original_kb']}KB → {result['final_kb']}KB ({result['compression']})")

    # Summary
    total_kb = sum(r["final_kb"] for r in results)
    print(f"\nOptimized {len(results)} tiles, total: {total_kb:.1f}KB")

    # Auto-pack atlas
    for category in ("ground", "buildings", "nature"):
        cat_dir = args.output / category
        if cat_dir.exists() and list(cat_dir.glob("*.png")):
            pack_atlas(cat_dir, args.output, f"{category}_atlas")


if __name__ == "__main__":
    main()
