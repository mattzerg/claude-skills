"""Render captions as transparent PNG overlays."""

from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


NAVY = (10, 15, 46, 192)        # #0a0f2e at 75% opacity
NAVY_DARK = (5, 8, 26, 230)
BRASS = (200, 168, 75, 255)
CREAM = (232, 236, 245, 255)    # ink color from Tycoon tokens

# Font paths — relative to this file's parent (skill dir)
SKILL_DIR = Path(__file__).resolve().parent.parent
FONT_MEDIUM = SKILL_DIR / "fonts" / "IBMPlexMono-Medium.ttf"
FONT_BOLD = SKILL_DIR / "fonts" / "IBMPlexMono-Bold.ttf"

# System font fallbacks
FONT_FALLBACKS = [
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/Courier.ttc",
    "/Library/Fonts/Courier New.ttf",
]


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    primary = FONT_BOLD if bold else FONT_MEDIUM
    if primary.exists():
        try:
            return ImageFont.truetype(str(primary), size)
        except Exception:
            pass
    for path in FONT_FALLBACKS:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _split_glyph_and_text(text: str) -> tuple[str, str]:
    """If text starts with '◆ ', split into (glyph, rest)."""
    if text.startswith("◆"):
        rest = text[1:].lstrip()
        return ("◆", rest)
    return ("", text)


def render_caption(
    text: str,
    video_w: int,
    video_h: int,
    out_path: Path,
    position: str = "bottom",
    size: str = "default",
    letterbox_h: int = 0,
) -> dict:
    """
    Render one caption as a transparent PNG sized to the video.

    Returns metadata: {png: path, x: int, y: int, w: int, h: int}.
    `letterbox_h`: if >0, position "letterbox-bottom" or "letterbox-top" places
    text inside the black strip OUTSIDE the original video area.
    """
    # Size targets relative to video height (excluding letterbox)
    canvas_video_h = video_h - letterbox_h if letterbox_h else video_h
    if size == "small":
        font_size = max(20, int(canvas_video_h * 0.025))
    elif size == "large":
        font_size = max(36, int(canvas_video_h * 0.045))
    else:
        # When using letterbox, scale to fill the strip nicely
        if letterbox_h:
            font_size = max(24, int(letterbox_h * 0.36))
        else:
            font_size = max(28, int(canvas_video_h * 0.033))

    pad_x = int(font_size * 0.6)
    pad_y = int(font_size * 0.4)
    spacing = int(font_size * 0.25)

    font = _load_font(font_size, bold=False)
    glyph, rest = _split_glyph_and_text(text)

    # Measure text size
    canvas = Image.new("RGBA", (video_w, video_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)

    # Display caption text in all-caps (matching the storyboard CAP style)
    display = rest.upper() if rest else ""
    glyph_display = glyph.upper() if glyph else ""

    glyph_w = 0
    if glyph_display:
        bbox = draw.textbbox((0, 0), glyph_display, font=font)
        glyph_w = bbox[2] - bbox[0] + int(font_size * 0.5)

    text_bbox = draw.textbbox((0, 0), display, font=font)
    text_w = text_bbox[2] - text_bbox[0]
    text_h = text_bbox[3] - text_bbox[1]

    box_w = glyph_w + text_w + pad_x * 2
    box_h = text_h + pad_y * 2

    # Position on the frame
    if position == "letterbox-bottom":
        # Caption sits CENTERED inside the letterbox strip at the bottom
        box_x = (video_w - box_w) // 2
        # letterbox strip occupies the bottom `letterbox_h` pixels
        strip_top = video_h - letterbox_h
        box_y = strip_top + (letterbox_h - box_h) // 2
    elif position == "letterbox-top":
        box_x = (video_w - box_w) // 2
        box_y = (letterbox_h - box_h) // 2
    elif position == "top":
        box_x = (video_w - box_w) // 2
        box_y = int(video_h * 0.06)
    elif position == "center":
        box_x = (video_w - box_w) // 2
        box_y = (video_h - box_h) // 2
    else:  # bottom
        box_x = (video_w - box_w) // 2
        box_y = int(video_h * 0.84)

    # Draw the navy scrim with rounded look (subtle, full opacity in middle)
    scrim_box = (box_x, box_y, box_x + box_w, box_y + box_h)
    draw.rectangle(scrim_box, fill=NAVY)
    # Brass top border (1px hairline)
    draw.rectangle((box_x, box_y, box_x + box_w, box_y + 2), fill=BRASS)

    # Draw glyph (brass) + text (cream)
    text_y = box_y + pad_y - text_bbox[1]
    if glyph_display:
        draw.text((box_x + pad_x, text_y), glyph_display, fill=BRASS, font=font)
    draw.text((box_x + pad_x + glyph_w, text_y), display, fill=CREAM, font=font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)

    return {
        "png": str(out_path),
        "x": 0,
        "y": 0,
        "w": video_w,
        "h": video_h,
        "scrim_box": scrim_box,
        "font_size": font_size,
        "display": display,
    }
