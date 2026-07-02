"""Pillow renderers for the 5 canonical callout types."""

from __future__ import annotations

import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Tycoon brand tokens
NAVY = (10, 15, 46, 220)
NAVY_DARK = (5, 8, 26, 235)
BRASS = (200, 168, 75, 255)
BRASS_DIM = (200, 168, 75, 90)
CREAM = (232, 236, 245, 255)
RED = (220, 38, 38, 255)
GREEN = (22, 163, 74, 255)

# Font path: caption-burn ships IBM Plex; share that.
CAPTION_BURN_FONT = Path.home() / ".claude/skills/caption-burn/fonts/IBMPlexMono-Medium.ttf"
CAPTION_BURN_FONT_BOLD = Path.home() / ".claude/skills/caption-burn/fonts/IBMPlexMono-Bold.ttf"

FALLBACKS = [
    "/System/Library/Fonts/Menlo.ttc",
    "/Library/Fonts/Courier New.ttf",
]


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    primary = CAPTION_BURN_FONT_BOLD if bold else CAPTION_BURN_FONT
    if primary.exists():
        try:
            return ImageFont.truetype(str(primary), size)
        except Exception:
            pass
    for fp in FALLBACKS:
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            pass
    return ImageFont.load_default()


def render_arrow_to(spec: dict, w: int, h: int, out: Path) -> dict:
    """
    Brass arrow from a labeled origin point to (x, y).
    spec: {x, y, label, direction: 'from-left'|'from-right'|'from-top'|'from-bottom'}
    """
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    fs = max(20, int(h * 0.025))
    font = _font(fs, bold=False)
    tx, ty = int(spec["x"]), int(spec["y"])
    direction = spec.get("direction", "from-left")
    label = spec.get("label", "").upper()

    # Origin point — 25% of frame width back from target
    dist = int(w * 0.18)
    if direction == "from-left":
        ox, oy = tx - dist, ty
        arrow_angle = 0
    elif direction == "from-right":
        ox, oy = tx + dist, ty
        arrow_angle = 180
    elif direction == "from-top":
        ox, oy = tx, ty - dist
        arrow_angle = 90
    else:  # from-bottom
        ox, oy = tx, ty + dist
        arrow_angle = 270

    # Draw arrow line (3-px brass)
    draw.line([(ox, oy), (tx, ty)], fill=BRASS, width=3)

    # Arrowhead
    head_len = 18
    head_w = 12
    rad = math.radians(arrow_angle + 180)
    p1 = (tx, ty)
    p2 = (tx + head_len * math.cos(rad + math.radians(20)),
          ty + head_len * math.sin(rad + math.radians(20)))
    p3 = (tx + head_len * math.cos(rad - math.radians(20)),
          ty + head_len * math.sin(rad - math.radians(20)))
    draw.polygon([p1, p2, p3], fill=BRASS)

    # Label chip at origin
    if label:
        glyph = "◆ "
        full = glyph + label
        tb = draw.textbbox((0, 0), full, font=font)
        pad_x = int(fs * 0.5)
        pad_y = int(fs * 0.3)
        box_w = (tb[2] - tb[0]) + pad_x * 2
        box_h = (tb[3] - tb[1]) + pad_y * 2
        chip_x = ox - box_w // 2
        chip_y = oy - box_h - 8  # above the origin
        # Scrim
        draw.rectangle([chip_x, chip_y, chip_x + box_w, chip_y + box_h], fill=NAVY_DARK)
        draw.rectangle([chip_x, chip_y, chip_x + box_w, chip_y + 2], fill=BRASS)
        # Glyph in brass, label in cream
        draw.text((chip_x + pad_x, chip_y + pad_y - tb[1]), glyph, fill=BRASS, font=font)
        glyph_w = draw.textbbox((0, 0), glyph, font=font)[2]
        draw.text((chip_x + pad_x + glyph_w, chip_y + pad_y - tb[1]), label, fill=CREAM, font=font)

    canvas.save(out)
    return {"png": str(out), "type": "arrow_to"}


def render_highlight_box(spec: dict, w: int, h: int, out: Path) -> dict:
    """
    Brass-outlined translucent navy box around a rectangle.
    spec: {x, y, w, h}
    """
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    bx, by = int(spec["x"]), int(spec["y"])
    bw, bh = int(spec["w"]), int(spec["h"])
    # Brass outline (4px)
    for offset in range(4):
        draw.rectangle(
            [bx - offset, by - offset, bx + bw + offset, by + bh + offset],
            outline=BRASS,
            width=1,
        )
    # Brass-dim inner fill (10% opacity)
    fill_canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    fill_draw = ImageDraw.Draw(fill_canvas)
    fill_draw.rectangle([bx, by, bx + bw, by + bh], fill=(200, 168, 75, 26))
    canvas = Image.alpha_composite(fill_canvas, canvas)
    canvas.save(out)
    return {"png": str(out), "type": "highlight_box"}


def render_label_chip(spec: dict, w: int, h: int, out: Path) -> dict:
    """
    Small mono-caps chip with brass ◆ glyph, anchored above/below/right/left of (anchor_x, anchor_y).
    spec: {anchor_x, anchor_y, text, position}
    """
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    fs = max(18, int(h * 0.022))
    font = _font(fs)
    text = spec.get("text", "").upper()
    glyph = "◆ "
    full = glyph + text
    tb = draw.textbbox((0, 0), full, font=font)
    pad_x = int(fs * 0.5)
    pad_y = int(fs * 0.3)
    box_w = (tb[2] - tb[0]) + pad_x * 2
    box_h = (tb[3] - tb[1]) + pad_y * 2

    ax, ay = int(spec["anchor_x"]), int(spec["anchor_y"])
    pos = spec.get("position", "above")
    if pos == "above":
        cx, cy = ax - box_w // 2, ay - box_h - 12
    elif pos == "below":
        cx, cy = ax - box_w // 2, ay + 12
    elif pos == "right":
        cx, cy = ax + 12, ay - box_h // 2
    else:  # left
        cx, cy = ax - box_w - 12, ay - box_h // 2

    draw.rectangle([cx, cy, cx + box_w, cy + box_h], fill=NAVY_DARK)
    draw.rectangle([cx, cy, cx + box_w, cy + 2], fill=BRASS)
    draw.text((cx + pad_x, cy + pad_y - tb[1]), glyph, fill=BRASS, font=font)
    glyph_w = draw.textbbox((0, 0), glyph, font=font)[2]
    draw.text((cx + pad_x + glyph_w, cy + pad_y - tb[1]), text, fill=CREAM, font=font)
    canvas.save(out)
    return {"png": str(out), "type": "label_chip"}


def render_state_badge(spec: dict, w: int, h: int, out: Path) -> dict:
    """
    Persistent state badge at a corner (top-left default).
    spec: {text, position: 'top-left'|'top-right'|'bottom-left'|'bottom-right'}
    """
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    fs = max(20, int(h * 0.028))
    font = _font(fs, bold=True)
    text = spec.get("text", "").upper()
    glyph = "◆ "
    full = glyph + text
    tb = draw.textbbox((0, 0), full, font=font)
    pad_x = int(fs * 0.6)
    pad_y = int(fs * 0.4)
    box_w = (tb[2] - tb[0]) + pad_x * 2
    box_h = (tb[3] - tb[1]) + pad_y * 2

    margin = int(min(w, h) * 0.03)
    pos = spec.get("position", "top-left")
    if pos == "top-left":
        cx, cy = margin, margin
    elif pos == "top-right":
        cx, cy = w - box_w - margin, margin
    elif pos == "bottom-left":
        cx, cy = margin, h - box_h - margin
    else:
        cx, cy = w - box_w - margin, h - box_h - margin

    draw.rectangle([cx, cy, cx + box_w, cy + box_h], fill=NAVY_DARK)
    draw.rectangle([cx, cy, cx + box_w, cy + 2], fill=BRASS)
    draw.text((cx + pad_x, cy + pad_y - tb[1]), glyph, fill=BRASS, font=font)
    glyph_w = draw.textbbox((0, 0), glyph, font=font)[2]
    draw.text((cx + pad_x + glyph_w, cy + pad_y - tb[1]), text, fill=CREAM, font=font)
    canvas.save(out)
    return {"png": str(out), "type": "state_badge"}


def render_metric_badge(spec: dict, w: int, h: int, out: Path) -> dict:
    """
    Label + value + optional delta indicator (▲ green / ▼ red).
    spec: {label, value, delta_color: 'red'|'green'|None, position}
    """
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    label_fs = max(14, int(h * 0.018))
    value_fs = max(28, int(h * 0.04))
    label_font = _font(label_fs)
    value_font = _font(value_fs, bold=True)
    label = spec.get("label", "").upper()
    value = spec.get("value", "")
    dc = spec.get("delta_color")

    glyph = "◆ "
    label_full = glyph + label

    # Measure both lines
    ltb = draw.textbbox((0, 0), label_full, font=label_font)
    vtb = draw.textbbox((0, 0), value, font=value_font)
    pad_x = int(value_fs * 0.4)
    pad_y = int(value_fs * 0.3)
    box_w = max(ltb[2] - ltb[0], vtb[2] - vtb[0]) + pad_x * 2
    box_h = (ltb[3] - ltb[1]) + (vtb[3] - vtb[1]) + pad_y * 2 + 8

    margin = int(min(w, h) * 0.03)
    pos = spec.get("position", "top-right")
    if pos == "top-left":
        cx, cy = margin, margin
    elif pos == "top-right":
        cx, cy = w - box_w - margin, margin
    elif pos == "bottom-left":
        cx, cy = margin, h - box_h - margin
    else:
        cx, cy = w - box_w - margin, h - box_h - margin

    draw.rectangle([cx, cy, cx + box_w, cy + box_h], fill=NAVY_DARK)
    draw.rectangle([cx, cy, cx + box_w, cy + 2], fill=BRASS)

    # Label
    draw.text((cx + pad_x, cy + pad_y - ltb[1]), glyph, fill=BRASS, font=label_font)
    glyph_w = draw.textbbox((0, 0), glyph, font=label_font)[2]
    draw.text((cx + pad_x + glyph_w, cy + pad_y - ltb[1]), label, fill=CREAM, font=label_font)

    # Value (with optional delta caret)
    val_color = RED if dc == "red" else (GREEN if dc == "green" else CREAM)
    val_y = cy + pad_y + (ltb[3] - ltb[1]) + 8
    draw.text((cx + pad_x, val_y - vtb[1]), value, fill=val_color, font=value_font)

    canvas.save(out)
    return {"png": str(out), "type": "metric_badge"}


RENDERERS = {
    "arrow_to": render_arrow_to,
    "highlight_box": render_highlight_box,
    "label_chip": render_label_chip,
    "state_badge": render_state_badge,
    "metric_badge": render_metric_badge,
}
