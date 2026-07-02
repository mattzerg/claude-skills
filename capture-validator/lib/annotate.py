"""
Draw violation boxes onto the source frame so Matt can SEE what's wrong.
"""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFont


COLORS = {
    "FAIL": (220, 38, 38, 255),    # red
    "WARN": (217, 119, 6, 255),    # amber
    "PASS": (22, 163, 74, 255),    # green
}


def _font(size: int = 24) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/Library/Fonts/Arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def annotate(img: Image.Image, results: list[dict]) -> Image.Image:
    """Return a NEW image with violation boxes + labels drawn on."""
    out = img.convert("RGBA").copy()
    overlay = Image.new("RGBA", out.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font_lg = _font(28)
    font_sm = _font(16)

    # Header strip
    header_h = 56
    draw.rectangle((0, 0, out.size[0], header_h), fill=(0, 0, 0, 200))
    passed = sum(1 for r in results if r["passed"])
    failed = sum(1 for r in results if r["severity"] == "FAIL" and not r["passed"])
    title = f"CAPTURE-VALIDATOR · {passed}/{len(results)} passed · {failed} FAIL"
    draw.text((16, 14), title, fill=(255, 255, 255), font=font_lg)

    # Per-violation boxes
    y_offset = header_h + 12
    for r in results:
        if r["passed"]:
            continue
        bboxes = r.get("all_bboxes") or ([r["bbox"]] if r.get("bbox") else [])
        color = COLORS.get(r["severity"], COLORS["FAIL"])
        for bbox in bboxes:
            x, y, w, h = bbox
            # 6-pixel-wide rectangle for visibility on hi-res frames
            for offset in range(6):
                draw.rectangle(
                    (x + offset, y + offset, x + w - offset, y + h - offset),
                    outline=color,
                    width=1,
                )
            # Label above the bbox
            label = f"⚠ {r['name'].upper()}"
            draw.rectangle(
                (x, max(0, y - 32), x + min(len(label) * 13 + 16, out.size[0] - x), y),
                fill=color,
            )
            draw.text((x + 8, max(0, y - 30)), label, fill=(255, 255, 255), font=font_sm)

        # Bottom-left running list
        line = f"⚠ {r['name']}: {r['details'][:120]}"
        draw.rectangle(
            (0, y_offset - 2, min(900, out.size[0]), y_offset + 22),
            fill=(0, 0, 0, 200),
        )
        draw.text((12, y_offset), line, fill=color[:3], font=font_sm)
        y_offset += 26

    return Image.alpha_composite(out, overlay).convert("RGB")
