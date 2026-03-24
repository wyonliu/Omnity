"""Soul Card Renderer — generate a beautiful shareable card image.

Design: Black/gold Omnity aesthetic, iPhone-optimized (750x1334px).
Renders using Pillow — no external dependencies beyond PIL.

Layout:
┌──────────────────────────┐
│         [Ome logo]       │
│                          │
│    ✦ {user_name} ✦       │
│                          │
│  ┌─ personality tags ──┐ │
│  │ #好奇心 #直率 #温暖  │ │
│  └─────────────────────┘ │
│                          │
│   "{representative quote}"│
│                          │
│  ── 灵魂洞察 ──          │
│  {soul insight text}     │
│                          │
│  相似度 ███████░░ 73%    │
│  对话 128 次 · 在一起 45天│
│                          │
│  ── 情绪光谱 ──          │
│  开心 ████  好奇 ███     │
│                          │
│  [Ome · 你的AI分身]      │
│  [搜索"Ome AI分身"体验]  │
└──────────────────────────┘
"""

from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any, Optional

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from ome.engine.soul_card import SoulCardData

log = logging.getLogger("ome.soul_card_renderer")

# -- Colors (Omnity brand: black/gold) --
BG_COLOR = (10, 10, 22)           # Deep dark blue-black
GOLD = (200, 169, 110)            # #c8a96e
GOLD_DIM = (160, 135, 88)         # Muted gold
TEXT_PRIMARY = (240, 237, 230)     # Warm white
TEXT_SECONDARY = (160, 155, 145)   # Muted
ACCENT_GLOW = (200, 169, 110, 40) # Gold glow (with alpha)
BAR_BG = (40, 38, 50)             # Progress bar background
BAR_FILL = (200, 169, 110)        # Progress bar fill
DIVIDER = (60, 55, 70)            # Subtle divider line

# -- Dimensions --
WIDTH = 750
HEIGHT = 1334
MARGIN = 60
CONTENT_W = WIDTH - 2 * MARGIN


def render_soul_card(
    card: SoulCardData,
    output_path: Optional[str | Path] = None,
) -> bytes:
    """Render a Soul Card to PNG bytes (and optionally save to file).

    Returns PNG image as bytes for API responses.
    """
    if not HAS_PIL:
        raise RuntimeError("Pillow is required for Soul Card rendering: pip install Pillow")

    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Load fonts (use system fonts, fall back to default)
    font_title = _load_font(36, bold=True)
    font_heading = _load_font(24, bold=True)
    font_body = _load_font(20)
    font_small = _load_font(16)
    font_tag = _load_font(18, bold=True)
    font_quote = _load_font(22)
    font_big_num = _load_font(48, bold=True)

    y = 60

    # -- Top: Ome branding --
    _draw_centered(draw, "✦  Ome  ✦", y, font_heading, GOLD_DIM)
    y += 50

    # -- User name --
    _draw_centered(draw, card.user_name, y, font_title, TEXT_PRIMARY)
    y += 55

    # -- Phase badge --
    phase_text = f"— {card.phase} —"
    _draw_centered(draw, phase_text, y, font_small, GOLD_DIM)
    y += 45

    # -- Personality tags --
    if card.personality_tags:
        tag_line = "  ".join(f"#{tag}" for tag in card.personality_tags)
        _draw_centered(draw, tag_line, y, font_tag, GOLD)
    y += 50

    # -- Divider --
    _draw_divider(draw, y)
    y += 30

    # -- Representative quote --
    if card.quote:
        quote_text = f"「{card.quote}」"
        # Word wrap
        lines = _wrap_text(quote_text, font_quote, CONTENT_W - 40)
        for line in lines[:3]:  # Max 3 lines
            _draw_centered(draw, line, y, font_quote, TEXT_PRIMARY)
            y += 32
        y += 15
    else:
        y += 10

    # -- Divider --
    _draw_divider(draw, y)
    y += 30

    # -- Soul insight section --
    _draw_centered(draw, "灵 魂 洞 察", y, font_heading, GOLD)
    y += 40

    if card.soul_insight:
        insight_lines = _wrap_text(card.soul_insight, font_body, CONTENT_W - 20)
        for line in insight_lines[:4]:  # Max 4 lines
            _draw_centered(draw, line, y, font_body, TEXT_SECONDARY)
            y += 30
    y += 25

    # -- Similarity score (big number + progress bar) --
    _draw_centered(draw, "相 似 度", y, font_small, TEXT_SECONDARY)
    y += 30

    # Big percentage number
    _draw_centered(draw, f"{card.similarity}%", y, font_big_num, GOLD)
    y += 65

    # Progress bar
    bar_x = MARGIN + 40
    bar_w = CONTENT_W - 80
    bar_h = 8
    # Background
    draw.rounded_rectangle(
        [bar_x, y, bar_x + bar_w, y + bar_h],
        radius=4, fill=BAR_BG,
    )
    # Fill
    fill_w = int(bar_w * card.similarity / 100)
    if fill_w > 0:
        draw.rounded_rectangle(
            [bar_x, y, bar_x + fill_w, y + bar_h],
            radius=4, fill=BAR_FILL,
        )
    y += 30

    # -- Stats line --
    stats_text = f"对话 {card.conversation_count} 次 · 在一起 {card.days_together} 天"
    _draw_centered(draw, stats_text, y, font_small, TEXT_SECONDARY)
    y += 45

    # -- Emotion signature --
    if card.emotion_signature:
        _draw_divider(draw, y)
        y += 25
        _draw_centered(draw, "情 绪 光 谱", y, font_small, TEXT_SECONDARY)
        y += 30
        emotion_text = "  ·  ".join(card.emotion_signature)
        _draw_centered(draw, emotion_text, y, font_body, GOLD_DIM)
        y += 40

    # -- Bottom: CTA + branding --
    # Position from bottom
    bottom_y = HEIGHT - 100
    _draw_centered(draw, "Ome · 你的AI分身", bottom_y, font_small, TEXT_SECONDARY)
    bottom_y += 25
    _draw_centered(draw, "搜索「Ome AI分身」开始你的", bottom_y, font_small, GOLD_DIM)

    # -- Decorative corner marks --
    _draw_corner_marks(draw)

    # Export
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    png_bytes = buf.getvalue()

    if output_path:
        Path(output_path).write_bytes(png_bytes)
        log.info("Soul Card saved to %s (%d bytes)", output_path, len(png_bytes))

    return png_bytes


# -- Helper functions --

def _load_font(size: int, bold: bool = False) -> Any:
    """Load a font, trying system CJK fonts then falling back to default."""
    if not HAS_PIL:
        return None

    # Common CJK font paths on macOS / Linux
    font_paths = [
        # macOS
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        # Linux
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    ]

    if bold:
        bold_paths = [
            "/System/Library/Fonts/PingFang.ttc",
            "/System/Library/Fonts/STHeiti Medium.ttc",
        ]
        font_paths = bold_paths + font_paths

    for fp in font_paths:
        try:
            return ImageFont.truetype(fp, size)
        except (OSError, IOError):
            continue

    # Fallback to default
    try:
        return ImageFont.truetype("Arial", size)
    except (OSError, IOError):
        return ImageFont.load_default()


def _draw_centered(draw: Any, text: str, y: int, font: Any, color: tuple) -> None:
    """Draw text centered horizontally."""
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    x = (WIDTH - text_w) // 2
    draw.text((x, y), text, fill=color, font=font)


def _draw_divider(draw: Any, y: int) -> None:
    """Draw a subtle centered divider line."""
    x1 = WIDTH // 2 - 100
    x2 = WIDTH // 2 + 100
    draw.line([(x1, y), (x2, y)], fill=DIVIDER, width=1)


def _draw_corner_marks(draw: Any) -> None:
    """Draw subtle decorative corner marks."""
    mark_len = 30
    offset = 30
    color = GOLD_DIM

    # Top-left
    draw.line([(offset, offset), (offset + mark_len, offset)], fill=color, width=1)
    draw.line([(offset, offset), (offset, offset + mark_len)], fill=color, width=1)
    # Top-right
    draw.line([(WIDTH - offset, offset), (WIDTH - offset - mark_len, offset)], fill=color, width=1)
    draw.line([(WIDTH - offset, offset), (WIDTH - offset, offset + mark_len)], fill=color, width=1)
    # Bottom-left
    draw.line([(offset, HEIGHT - offset), (offset + mark_len, HEIGHT - offset)], fill=color, width=1)
    draw.line([(offset, HEIGHT - offset), (offset, HEIGHT - offset - mark_len)], fill=color, width=1)
    # Bottom-right
    draw.line([(WIDTH - offset, HEIGHT - offset), (WIDTH - offset - mark_len, HEIGHT - offset)], fill=color, width=1)
    draw.line([(WIDTH - offset, HEIGHT - offset), (WIDTH - offset, HEIGHT - offset - mark_len)], fill=color, width=1)


def _wrap_text(text: str, font: Any, max_width: int) -> list[str]:
    """Wrap text to fit within max_width pixels."""
    if not HAS_PIL:
        return [text]

    # For CJK: wrap character by character
    lines = []
    current = ""
    tmp_img = Image.new("RGB", (1, 1))
    tmp_draw = ImageDraw.Draw(tmp_img)

    for char in text:
        test = current + char
        bbox = tmp_draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = char
        else:
            current = test

    if current:
        lines.append(current)

    return lines
