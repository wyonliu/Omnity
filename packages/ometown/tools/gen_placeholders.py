#!/usr/bin/env python3
"""
Generate high-quality programmatic isometric placeholder tiles using Pillow.
No API key needed. Produces 128x64 ground tiles and 128x128 building/nature tiles.

Follows palette.json colors and ART_SPEC.md specifications.
Output: assets/tiles/optimized/
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
OUT_DIR = ASSETS_DIR / "tiles" / "optimized"
PALETTE_FILE = ASSETS_DIR / "palette.json"

# Load palette
palette = json.loads(PALETTE_FILE.read_text())

def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

def rgb_to_rgba(rgb: tuple[int, int, int], a: int = 255) -> tuple[int, int, int, int]:
    return (*rgb, a)

def shade(rgb: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    """Lighten (>1) or darken (<1) a color."""
    return tuple(max(0, min(255, int(c * factor))) for c in rgb)

def blend(c1: tuple, c2: tuple, t: float) -> tuple[int, int, int]:
    """Blend two RGB colors by factor t (0=c1, 1=c2)."""
    return tuple(int(a + (b - a) * t) for a, b in zip(c1[:3], c2[:3]))

# ─── Diamond mask for ground tiles ───
TILE_W, TILE_H = 128, 64

def diamond_polygon(w: int, h: int, offset: tuple[int, int] = (0, 0)) -> list[tuple[int, int]]:
    ox, oy = offset
    return [
        (ox + w // 2, oy),          # top
        (ox + w, oy + h // 2),      # right
        (ox + w // 2, oy + h),      # bottom
        (ox, oy + h // 2),          # left
    ]

def draw_diamond_base(img: Image.Image, draw: ImageDraw.ImageDraw,
                       base_color: tuple[int, int, int],
                       w: int = TILE_W, h: int = TILE_H,
                       offset: tuple[int, int] = (0, 0)):
    """Draw a filled isometric diamond with subtle shading."""
    poly = diamond_polygon(w, h, offset)
    draw.polygon(poly, fill=rgb_to_rgba(base_color))
    # Lighter top-left edge
    lighter = shade(base_color, 1.15)
    draw.line([poly[0], poly[3]], fill=rgb_to_rgba(lighter), width=2)
    draw.line([poly[0], poly[1]], fill=rgb_to_rgba(lighter), width=1)
    # Darker bottom-right edge
    darker = shade(base_color, 0.8)
    draw.line([poly[1], poly[2]], fill=rgb_to_rgba(darker), width=2)
    draw.line([poly[2], poly[3]], fill=rgb_to_rgba(darker), width=1)


def add_texture_dots(draw: ImageDraw.ImageDraw, w: int, h: int,
                     base_color: tuple[int, int, int], count: int = 40,
                     offset: tuple[int, int] = (0, 0), seed: int = 42):
    """Add subtle texture dots inside diamond area."""
    rng = random.Random(seed)
    ox, oy = offset
    for _ in range(count):
        # Random point, check if inside diamond
        px = rng.randint(ox + 4, ox + w - 4)
        py = rng.randint(oy + 4, oy + h - 4)
        # Diamond test: |px - cx| / (w/2) + |py - cy| / (h/2) <= 1
        cx, cy = ox + w // 2, oy + h // 2
        if abs(px - cx) / (w / 2) + abs(py - cy) / (h / 2) > 0.9:
            continue
        factor = rng.uniform(0.85, 1.15)
        dot_color = shade(base_color, factor)
        r = rng.randint(1, 2)
        draw.ellipse([px - r, py - r, px + r, py + r], fill=rgb_to_rgba(dot_color, 180))


# ─── Ground Tile Generators ───

def gen_grass(variant: int = 1) -> Image.Image:
    img = Image.new("RGBA", (TILE_W, TILE_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    colors = [
        hex_to_rgb(palette["ground"]["grass_light"]),
        hex_to_rgb(palette["ground"]["grass_mid"]),
        hex_to_rgb(palette["ground"]["grass_dark"]),
        blend(hex_to_rgb(palette["ground"]["grass_light"]),
              hex_to_rgb(palette["nature"]["leaf_autumn"]), 0.3),
    ]
    base = colors[(variant - 1) % len(colors)]
    draw_diamond_base(img, draw, base)
    add_texture_dots(draw, TILE_W, TILE_H, base, count=50, seed=variant * 7)

    # Small grass blades
    rng = random.Random(variant * 13)
    blade_color = shade(base, 1.2)
    for _ in range(8):
        px = rng.randint(20, TILE_W - 20)
        py = rng.randint(10, TILE_H - 10)
        cx, cy = TILE_W // 2, TILE_H // 2
        if abs(px - cx) / (TILE_W / 2) + abs(py - cy) / (TILE_H / 2) > 0.8:
            continue
        draw.line([(px, py), (px + rng.randint(-2, 2), py - rng.randint(3, 6))],
                  fill=rgb_to_rgba(blade_color, 200), width=1)
    return img


def gen_dirt(variant: int = 1) -> Image.Image:
    img = Image.new("RGBA", (TILE_W, TILE_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    colors = [
        hex_to_rgb(palette["ground"]["dirt_light"]),
        hex_to_rgb(palette["ground"]["dirt_dark"]),
    ]
    base = colors[(variant - 1) % len(colors)]
    draw_diamond_base(img, draw, base)
    add_texture_dots(draw, TILE_W, TILE_H, base, count=60, seed=variant * 11)
    # Pebbles
    rng = random.Random(variant * 17)
    for _ in range(5):
        px = rng.randint(25, TILE_W - 25)
        py = rng.randint(12, TILE_H - 12)
        cx, cy = TILE_W // 2, TILE_H // 2
        if abs(px - cx) / (TILE_W / 2) + abs(py - cy) / (TILE_H / 2) > 0.75:
            continue
        pebble = shade(base, rng.uniform(0.7, 0.9))
        r = rng.randint(2, 4)
        draw.ellipse([px - r, py - r, px + r + 1, py + r], fill=rgb_to_rgba(pebble))
    return img


def gen_path() -> Image.Image:
    img = Image.new("RGBA", (TILE_W, TILE_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    base = hex_to_rgb(palette["ground"]["stone"])
    draw_diamond_base(img, draw, base)

    # Cobblestone pattern
    rng = random.Random(99)
    for _ in range(25):
        px = rng.randint(15, TILE_W - 15)
        py = rng.randint(8, TILE_H - 8)
        cx, cy = TILE_W // 2, TILE_H // 2
        if abs(px - cx) / (TILE_W / 2) + abs(py - cy) / (TILE_H / 2) > 0.8:
            continue
        stone_color = shade(base, rng.uniform(0.85, 1.1))
        rw, rh = rng.randint(4, 8), rng.randint(3, 5)
        draw.rounded_rectangle([px - rw, py - rh, px + rw, py + rh],
                                radius=2, fill=rgb_to_rgba(stone_color),
                                outline=rgb_to_rgba(shade(base, 0.7), 120))
    return img


def gen_water(variant: int = 1) -> Image.Image:
    img = Image.new("RGBA", (TILE_W, TILE_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    base = hex_to_rgb(palette["water"]["mid"])
    draw_diamond_base(img, draw, base)

    # Ripple highlights
    rng = random.Random(variant * 23)
    light = hex_to_rgb(palette["water"]["light"])
    for i in range(6):
        px = rng.randint(25, TILE_W - 25)
        py = rng.randint(10, TILE_H - 10)
        cx, cy = TILE_W // 2, TILE_H // 2
        if abs(px - cx) / (TILE_W / 2) + abs(py - cy) / (TILE_H / 2) > 0.75:
            continue
        w = rng.randint(8, 16)
        draw.arc([px - w, py - 2, px + w, py + 2], 0, 180,
                 fill=rgb_to_rgba(light, 140), width=1)
    # Subtle dark reflections
    dark = hex_to_rgb(palette["water"]["dark"])
    add_texture_dots(draw, TILE_W, TILE_H, dark, count=15, seed=variant * 31)
    return img


# ─── Building Generators (128x128) ───
BLDG_W, BLDG_H = 128, 128

def gen_building_house() -> Image.Image:
    img = Image.new("RGBA", (BLDG_W, BLDG_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Ground diamond at bottom
    base_y = BLDG_H - TILE_H
    ground = hex_to_rgb(palette["ground"]["grass_mid"])
    draw_diamond_base(img, draw, ground, TILE_W, TILE_H, (0, base_y))

    # Wall (isometric box)
    wall_color = hex_to_rgb(palette["buildings"]["wood_light"])
    wall_dark = shade(wall_color, 0.8)
    wall_h = 40

    # Front face (left-facing)
    front = [
        (0, base_y + TILE_H // 2),                    # bottom-left
        (TILE_W // 2, base_y + TILE_H),               # bottom-right
        (TILE_W // 2, base_y + TILE_H - wall_h),      # top-right
        (0, base_y + TILE_H // 2 - wall_h),           # top-left
    ]
    draw.polygon(front, fill=rgb_to_rgba(wall_dark))

    # Right face
    right = [
        (TILE_W // 2, base_y + TILE_H),               # bottom-left
        (TILE_W, base_y + TILE_H // 2),               # bottom-right
        (TILE_W, base_y + TILE_H // 2 - wall_h),      # top-right
        (TILE_W // 2, base_y + TILE_H - wall_h),      # top-left
    ]
    draw.polygon(right, fill=rgb_to_rgba(wall_color))

    # Roof (raised diamond)
    roof_color = hex_to_rgb(palette["buildings"]["roof_clay"])
    roof_y = base_y - wall_h + 8
    roof_poly = diamond_polygon(TILE_W + 8, TILE_H + 4, (-4, roof_y))
    draw.polygon(roof_poly, fill=rgb_to_rgba(roof_color))
    # Roof highlight
    draw.line([roof_poly[0], roof_poly[1]], fill=rgb_to_rgba(shade(roof_color, 1.2)), width=2)

    # Door on front face
    door_color = hex_to_rgb(palette["buildings"]["wood_dark"])
    dx = 20
    dy = base_y + TILE_H // 2 - 4
    draw.rectangle([dx, dy - 14, dx + 8, dy + 4], fill=rgb_to_rgba(door_color))

    # Window on right face
    win_x = TILE_W // 2 + 20
    win_y = base_y + TILE_H // 2 - wall_h + 14
    draw.rectangle([win_x, win_y, win_x + 10, win_y + 8],
                   fill=rgb_to_rgba((240, 220, 160), 200),
                   outline=rgb_to_rgba(shade(wall_color, 0.7)))

    # Chimney
    chimney_color = hex_to_rgb(palette["buildings"]["brick"])
    cx = TILE_W // 2 + 30
    cy = roof_y - 4
    draw.rectangle([cx, cy - 12, cx + 6, cy + 4], fill=rgb_to_rgba(chimney_color))

    return img


def gen_building_shop() -> Image.Image:
    img = Image.new("RGBA", (BLDG_W, BLDG_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    base_y = BLDG_H - TILE_H
    ground = hex_to_rgb(palette["ground"]["stone"])
    draw_diamond_base(img, draw, ground, TILE_W, TILE_H, (0, base_y))

    # Walls
    wall_color = hex_to_rgb(palette["buildings"]["stucco"])
    wall_dark = shade(wall_color, 0.82)
    wall_h = 44

    # Front face
    front = [
        (0, base_y + TILE_H // 2),
        (TILE_W // 2, base_y + TILE_H),
        (TILE_W // 2, base_y + TILE_H - wall_h),
        (0, base_y + TILE_H // 2 - wall_h),
    ]
    draw.polygon(front, fill=rgb_to_rgba(wall_dark))

    # Right face
    right = [
        (TILE_W // 2, base_y + TILE_H),
        (TILE_W, base_y + TILE_H // 2),
        (TILE_W, base_y + TILE_H // 2 - wall_h),
        (TILE_W // 2, base_y + TILE_H - wall_h),
    ]
    draw.polygon(right, fill=rgb_to_rgba(wall_color))

    # Roof
    roof_color = hex_to_rgb(palette["buildings"]["roof_thatch"])
    roof_y = base_y - wall_h + 6
    roof_poly = diamond_polygon(TILE_W + 10, TILE_H + 6, (-5, roof_y))
    draw.polygon(roof_poly, fill=rgb_to_rgba(roof_color))
    draw.line([roof_poly[0], roof_poly[1]], fill=rgb_to_rgba(shade(roof_color, 1.2)), width=2)

    # Awning on front face (red-white striped)
    awning_top = base_y + TILE_H // 2 - wall_h + 10
    awning_bot = awning_top + 12
    for i in range(4):
        x1 = 4 + i * 14
        x2 = x1 + 7
        stripe_color = (200, 60, 60) if i % 2 == 0 else (240, 230, 220)
        # Approximate isometric skew for awning
        draw.polygon([
            (x1, awning_top + i * 2),
            (x2, awning_top + i * 2 + 1),
            (x2, awning_bot + i * 2 + 1),
            (x1, awning_bot + i * 2),
        ], fill=rgb_to_rgba(stripe_color))

    # Large window / shop front on right face
    win_x = TILE_W // 2 + 12
    win_y = base_y + TILE_H // 2 - wall_h + 12
    draw.rectangle([win_x, win_y, win_x + 24, win_y + 16],
                   fill=rgb_to_rgba((240, 230, 180), 200),
                   outline=rgb_to_rgba(shade(wall_color, 0.6)))

    # Door
    door_color = hex_to_rgb(palette["buildings"]["wood_dark"])
    dx = 24
    dy = base_y + TILE_H // 2
    draw.rectangle([dx, dy - 16, dx + 10, dy + 4], fill=rgb_to_rgba(door_color))

    # Hanging sign
    gold = hex_to_rgb(palette["brand"]["gold"])
    sign_x = TILE_W // 2 + 40
    sign_y = base_y + TILE_H // 2 - wall_h + 6
    draw.line([(sign_x + 4, sign_y), (sign_x + 4, sign_y + 6)],
             fill=rgb_to_rgba((60, 60, 60)), width=1)
    draw.rounded_rectangle([sign_x, sign_y + 6, sign_x + 10, sign_y + 14],
                           radius=1, fill=rgb_to_rgba(gold))

    return img


def gen_building_cafe() -> Image.Image:
    img = Image.new("RGBA", (BLDG_W, BLDG_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    base_y = BLDG_H - TILE_H
    ground = hex_to_rgb(palette["ground"]["stone"])
    draw_diamond_base(img, draw, ground, TILE_W, TILE_H, (0, base_y))

    # Warm brick walls
    wall_color = hex_to_rgb(palette["buildings"]["brick"])
    wall_dark = shade(wall_color, 0.82)
    wall_h = 42

    front = [
        (0, base_y + TILE_H // 2),
        (TILE_W // 2, base_y + TILE_H),
        (TILE_W // 2, base_y + TILE_H - wall_h),
        (0, base_y + TILE_H // 2 - wall_h),
    ]
    draw.polygon(front, fill=rgb_to_rgba(wall_dark))

    right = [
        (TILE_W // 2, base_y + TILE_H),
        (TILE_W, base_y + TILE_H // 2),
        (TILE_W, base_y + TILE_H // 2 - wall_h),
        (TILE_W // 2, base_y + TILE_H - wall_h),
    ]
    draw.polygon(right, fill=rgb_to_rgba(wall_color))

    # Green awning
    awning_color = (70, 120, 70)
    awning_top = base_y + TILE_H // 2 - wall_h + 8
    awning_points = [
        (2, awning_top),
        (TILE_W // 2 - 2, awning_top + TILE_H // 4),
        (TILE_W // 2 - 2, awning_top + TILE_H // 4 + 10),
        (2, awning_top + 10),
    ]
    draw.polygon(awning_points, fill=rgb_to_rgba(awning_color))

    # Roof
    roof_color = hex_to_rgb(palette["buildings"]["roof_slate"])
    roof_y = base_y - wall_h + 4
    roof_poly = diamond_polygon(TILE_W + 6, TILE_H + 4, (-3, roof_y))
    draw.polygon(roof_poly, fill=rgb_to_rgba(roof_color))

    # Windows (warm glow)
    for i in range(2):
        win_x = TILE_W // 2 + 10 + i * 18
        win_y = base_y + TILE_H // 2 - wall_h + 14
        draw.rectangle([win_x, win_y, win_x + 10, win_y + 10],
                       fill=rgb_to_rgba((255, 230, 160), 220),
                       outline=rgb_to_rgba(shade(wall_color, 0.6)))

    # Door
    door_color = hex_to_rgb(palette["buildings"]["wood_light"])
    dx = 20
    dy = base_y + TILE_H // 2 - 2
    draw.rectangle([dx, dy - 15, dx + 10, dy + 4], fill=rgb_to_rgba(door_color))
    # Door handle
    draw.ellipse([dx + 7, dy - 6, dx + 9, dy - 4], fill=rgb_to_rgba((200, 180, 100)))

    return img


# ─── Nature Generators (128x128) ───

def gen_tree(variant: int = 1) -> Image.Image:
    img = Image.new("RGBA", (BLDG_W, BLDG_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Small ground shadow
    base_y = BLDG_H - TILE_H
    shadow_color = (20, 30, 20, 60)
    shadow_poly = diamond_polygon(48, 24, (40, base_y + 20))
    draw.polygon(shadow_poly, fill=shadow_color)

    # Trunk
    trunk_color = hex_to_rgb(palette["nature"]["trunk"])
    trunk_x = BLDG_W // 2
    trunk_bot = BLDG_H - 24
    trunk_top = trunk_bot - 30 - variant * 4
    draw.rectangle([trunk_x - 4, trunk_top, trunk_x + 4, trunk_bot],
                   fill=rgb_to_rgba(trunk_color))
    # Trunk highlight
    draw.rectangle([trunk_x - 4, trunk_top, trunk_x - 1, trunk_bot],
                   fill=rgb_to_rgba(shade(trunk_color, 1.2)))

    # Canopy
    leaf_colors = [
        hex_to_rgb(palette["nature"]["leaf_summer"]),
        hex_to_rgb(palette["nature"]["leaf_spring"]),
        blend(hex_to_rgb(palette["nature"]["leaf_summer"]),
              hex_to_rgb(palette["nature"]["leaf_spring"]), 0.5),
    ]
    leaf = leaf_colors[(variant - 1) % len(leaf_colors)]

    # Main canopy (overlapping circles for organic feel)
    canopy_cx = trunk_x
    canopy_cy = trunk_top - 5
    rng = random.Random(variant * 37)

    # Large base circles
    for _ in range(5):
        ox = rng.randint(-14, 14)
        oy = rng.randint(-12, 8)
        r = rng.randint(14, 22)
        c = shade(leaf, rng.uniform(0.85, 1.15))
        draw.ellipse([canopy_cx + ox - r, canopy_cy + oy - r,
                      canopy_cx + ox + r, canopy_cy + oy + r],
                     fill=rgb_to_rgba(c))

    # Highlight spots
    for _ in range(3):
        ox = rng.randint(-10, 10)
        oy = rng.randint(-10, 2)
        r = rng.randint(6, 10)
        c = shade(leaf, 1.3)
        draw.ellipse([canopy_cx + ox - r, canopy_cy + oy - r,
                      canopy_cx + ox + r, canopy_cy + oy + r],
                     fill=rgb_to_rgba(c, 140))

    return img


def gen_bush(variant: int = 1) -> Image.Image:
    img = Image.new("RGBA", (TILE_W, TILE_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Shadow
    shadow_poly = diamond_polygon(40, 20, (44, 36))
    draw.polygon(shadow_poly, fill=(20, 30, 20, 50))

    leaf_colors = [
        hex_to_rgb(palette["nature"]["leaf_summer"]),
        hex_to_rgb(palette["nature"]["leaf_spring"]),
    ]
    leaf = leaf_colors[(variant - 1) % len(leaf_colors)]

    cx, cy = TILE_W // 2, TILE_H // 2 - 4
    rng = random.Random(variant * 41)

    # Overlapping circles
    for _ in range(4):
        ox = rng.randint(-8, 8)
        oy = rng.randint(-6, 4)
        r = rng.randint(8, 14)
        c = shade(leaf, rng.uniform(0.85, 1.1))
        draw.ellipse([cx + ox - r, cy + oy - r, cx + ox + r, cy + oy + r],
                     fill=rgb_to_rgba(c))

    # Flowers on bush_02
    if variant == 2:
        flower = hex_to_rgb(palette["nature"]["flower_pink"])
        for _ in range(5):
            fx = cx + rng.randint(-10, 10)
            fy = cy + rng.randint(-8, 4)
            draw.ellipse([fx - 2, fy - 2, fx + 2, fy + 2],
                         fill=rgb_to_rgba(flower))

    return img


def gen_flower() -> Image.Image:
    img = Image.new("RGBA", (TILE_W, TILE_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Light grass base
    base = hex_to_rgb(palette["ground"]["grass_light"])
    draw_diamond_base(img, draw, base)

    # Scattered flowers
    flower_colors = [
        hex_to_rgb(palette["nature"]["flower_pink"]),
        hex_to_rgb(palette["nature"]["flower_blue"]),
        hex_to_rgb(palette["nature"]["flower_yellow"]),
    ]
    rng = random.Random(55)
    cx, cy = TILE_W // 2, TILE_H // 2
    for _ in range(12):
        fx = rng.randint(20, TILE_W - 20)
        fy = rng.randint(8, TILE_H - 8)
        if abs(fx - cx) / (TILE_W / 2) + abs(fy - cy) / (TILE_H / 2) > 0.75:
            continue
        fc = rng.choice(flower_colors)
        r = rng.randint(2, 3)
        # Petals
        for angle in range(0, 360, 72):
            px = fx + int(r * 1.2 * math.cos(math.radians(angle)))
            py = fy + int(r * 1.2 * math.sin(math.radians(angle)))
            draw.ellipse([px - 1, py - 1, px + 2, py + 2], fill=rgb_to_rgba(fc))
        # Center
        draw.ellipse([fx - 1, fy - 1, fx + 1, fy + 1],
                     fill=rgb_to_rgba((255, 220, 80)))
        # Stem
        stem_color = shade(base, 0.8)
        draw.line([(fx, fy + 2), (fx, fy + 5)], fill=rgb_to_rgba(stem_color), width=1)

    return img


# ─── Main ───

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    tiles: list[tuple[str, Image.Image]] = []

    # Ground tiles
    for i in range(1, 5):
        tiles.append((f"grass_0{i}", gen_grass(i)))
    tiles.append(("dirt_01", gen_dirt(1)))
    tiles.append(("dirt_02", gen_dirt(2)))
    tiles.append(("path_straight", gen_path()))
    tiles.append(("water_01", gen_water(1)))
    tiles.append(("water_02", gen_water(2)))
    tiles.append(("flower_bed_01", gen_flower()))

    # Buildings
    tiles.append(("building_house", gen_building_house()))
    tiles.append(("building_shop", gen_building_shop()))
    tiles.append(("building_cafe", gen_building_cafe()))

    # Nature
    for i in range(1, 4):
        tiles.append((f"tree_deciduous_0{i}", gen_tree(i)))
    tiles.append(("bush_01", gen_bush(1)))
    tiles.append(("bush_02", gen_bush(2)))

    total_bytes = 0
    for name, img in tiles:
        path = OUT_DIR / f"{name}.png"
        img.save(path, "PNG", optimize=True)
        size = path.stat().st_size
        total_bytes += size
        print(f"  {name}.png  ({img.width}x{img.height})  {size / 1024:.1f}KB")

    print(f"\nGenerated {len(tiles)} tiles in {OUT_DIR}")
    print(f"Total size: {total_bytes / 1024:.1f}KB")


if __name__ == "__main__":
    main()
