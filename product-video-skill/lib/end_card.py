#!/usr/bin/env python3
"""End-card generator for product videos.

Produces a still PNG that the assembly pipeline holds for 3–5s at the end
of the video. Uses the same dark-mode brand palette as `blog-imagery` SVG
templates so videos and blog imagery share visual identity.

Usage:
    python3 end_card.py \
        --headline "Zergboard is live." \
        --cta "Try it" \
        --url "zergboard.com" \
        --brand zergboard \
        --aspect 16:9 \
        --out /tmp/end-card.png

Aspects:
    16:9    1920x1080   (master / YouTube / X / site hero)
    1:1     1080x1080   (LinkedIn feed)
    9:16    1080x1920   (Reels/Shorts/TikTok)
"""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


# Brand palette (matches blog-imagery)
BG = (7, 17, 30)             # #07111E
CARD = (14, 27, 45)           # #0E1B2D
ACCENT = (244, 162, 97)       # #F4A261 (zergboard amber)
ACCENT_BLUE = (68, 184, 255)  # #44B8FF (zerg blue)
TEXT = (235, 241, 248)        # #EBF1F8
MUTED = (148, 166, 186)       # #94A6BA

ASPECTS = {
    "16:9": (1920, 1080),
    "1:1": (1080, 1080),
    "9:16": (1080, 1920),
}


def font(size, bold=False):
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/SFNS.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def mono(size):
    candidates = [
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/SFNSMono.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return font(size)


def render(*, headline, cta, url, brand, aspect, out_path, accent=None):
    if aspect not in ASPECTS:
        raise ValueError(f"Aspect must be one of {list(ASPECTS)}; got {aspect}")
    if accent is None:
        accent = ACCENT  # default amber

    w, h = ASPECTS[aspect]
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)

    # Subtle grid (matches the legacy zergboard demo cards)
    for x in range(0, w, 64):
        d.line([(x, 0), (x, h)], fill=(12, 22, 38), width=1)
    for y in range(0, h, 64):
        d.line([(0, y), (w, y)], fill=(12, 22, 38), width=1)

    # Brand mark — square + inset rounded square
    pad_x, pad_y = int(w * 0.05), int(h * 0.07)
    bs = max(60, int(h * 0.07))
    d.rounded_rectangle([pad_x, pad_y, pad_x + bs, pad_y + bs], radius=bs // 6, fill=TEXT)
    inset = bs // 6
    d.rounded_rectangle(
        [pad_x + inset, pad_y + inset, pad_x + bs - inset, pad_y + bs - inset],
        radius=(bs // 6) // 2, fill=accent
    )
    if brand:
        d.text(
            (pad_x + bs + 22, pad_y + bs // 3),
            brand.upper(),
            font=mono(max(20, int(bs * 0.42))),
            fill=accent,
        )

    # Headline (centered vertically, weighted toward upper-mid)
    headline_size = int(h * 0.075) if aspect == "16:9" else int(h * 0.06)
    headline_font = font(headline_size, bold=True)
    bbox = d.textbbox((0, 0), headline, font=headline_font)
    headline_w = bbox[2] - bbox[0]
    headline_h = bbox[3] - bbox[1]
    headline_y = int(h * 0.40) - headline_h // 2
    d.text(
        ((w - headline_w) // 2, headline_y),
        headline,
        font=headline_font,
        fill=TEXT,
    )

    # Accent underline below headline
    underline_w = int(w * 0.08)
    underline_y = headline_y + headline_h + int(h * 0.025)
    d.rectangle(
        [(w - underline_w) // 2, underline_y, (w + underline_w) // 2, underline_y + 6],
        fill=accent,
    )

    # CTA — slight offset below the underline
    cta_size = int(h * 0.040)
    cta_font = font(cta_size, bold=True)
    bbox = d.textbbox((0, 0), cta, font=cta_font)
    cta_w = bbox[2] - bbox[0]
    cta_y = underline_y + int(h * 0.06)

    # CTA pill background
    pill_pad_x, pill_pad_y = 26, 14
    pill_x0 = (w - cta_w) // 2 - pill_pad_x
    pill_x1 = (w + cta_w) // 2 + pill_pad_x
    pill_y0 = cta_y - pill_pad_y
    pill_y1 = cta_y + bbox[3] - bbox[1] + pill_pad_y
    d.rounded_rectangle(
        [pill_x0, pill_y0, pill_x1, pill_y1],
        radius=12,
        fill=accent,
    )
    d.text(
        ((w - cta_w) // 2, cta_y),
        cta,
        font=cta_font,
        fill=BG,
    )

    # Arrow after CTA — small chevron
    arrow_x = pill_x1 + 24
    arrow_y_center = (pill_y0 + pill_y1) // 2
    arrow_size = 12
    d.polygon(
        [
            (arrow_x, arrow_y_center - arrow_size),
            (arrow_x + arrow_size * 1.4, arrow_y_center),
            (arrow_x, arrow_y_center + arrow_size),
        ],
        fill=accent,
    )

    # URL — small, muted, below CTA
    url_size = int(h * 0.025)
    url_font = mono(url_size)
    bbox = d.textbbox((0, 0), url, font=url_font)
    url_w = bbox[2] - bbox[0]
    d.text(
        ((w - url_w) // 2, pill_y1 + int(h * 0.04)),
        url,
        font=url_font,
        fill=MUTED,
    )

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    return out_path


def main():
    ap = argparse.ArgumentParser(description="Generate an end-card PNG for a product video.")
    ap.add_argument("--headline", required=True, help="One line, what shipped")
    ap.add_argument("--cta", required=True, help="Verb-led 2–4 word CTA")
    ap.add_argument("--url", required=True)
    ap.add_argument("--brand", default="", help="Brand slug (e.g. zergboard)")
    ap.add_argument("--aspect", default="16:9", choices=list(ASPECTS))
    ap.add_argument("--accent", default="amber", choices=["amber", "blue"], help="Brand accent color")
    ap.add_argument("--out", required=True, help="Output PNG path")
    args = ap.parse_args()

    accent = ACCENT_BLUE if args.accent == "blue" else ACCENT
    out = render(
        headline=args.headline,
        cta=args.cta,
        url=args.url,
        brand=args.brand,
        aspect=args.aspect,
        out_path=args.out,
        accent=accent,
    )
    print(f"Wrote {out} ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
