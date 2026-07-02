"""Stat-card template: before-arrow-after big-number layout.

Use case: hero for technical posts where a single delta is the headline
(e.g., "22% → 54% single-pass correctness"). Three aspect modes:
    - og        1200×630   (blog hero / OG card)
    - square    1200×1200  (LinkedIn 1:1)
    - wide      1200×675   (X 16:9)

Required config:
    title           str   — main title (post title or hook)
    before_value    str   — big number on the left (e.g. "22%")
    after_value     str   — big number on the right (e.g. "54%")

Optional:
    eyebrow         str   default "RESEARCH · ZERG AI"
    subtitle        str   default ""
    before_label    str   default "BEFORE"
    after_label     str   default "AFTER"
    before_caption  str   small italic under before number
    after_caption   str   small italic under after number
    middle_label    str   small caps above the arrow (e.g. "DISTILL FAILURES")
    middle_caption  str   italic under the arrow (e.g. "1,178 → 174 → 78 rules")
    takeaway        str   bottom bold line
    takeaway_sub    str   bottom muted second line
    source          str   bottom credit line
    aspect          str   "og" (default) | "square" | "wide"
"""
from . import _palette as p


def _esc(s: str) -> str:
    """Escape XML special chars in SVG text content. Without this, '<' / '>' / '&' break Chrome's parser."""
    if s is None:
        return ""
    return (str(s).replace("&", "&amp;")
                  .replace("<", "&lt;")
                  .replace(">", "&gt;"))


DESCRIPTION = "Before/after big-number stat card with optional middle caption. Hero for posts where a single delta is the headline."

DEFAULT_VIEWBOX = (1200, 630)

EXAMPLE_CONFIG = {
    "title": "What AI Agents Get Wrong About Failure",
    "subtitle": "Failure as data, not noise: distilled rules carry across tasks",
    "before_value": "22%",
    "before_subtext": "single-pass correctness",
    "before_caption": "retry loop, no memory",
    "after_value": "54%",
    "after_subtext": "single-pass correctness",
    "after_caption": "cross-task failure memory",
    "middle_label": "DISTILL FAILURES",
    "middle_caption": "1,178 → 174 → 78 rules",
    "takeaway": "More than 2× the correctness, before any search or optimization.",
    "takeaway_sub": "Just from not repeating known mistakes.",
    "source": "Source: AdaExplore (Du et al., 2026)  ·  zergai.com/blog",
    "aspect": "og",
}


def _layout(aspect):
    # Rebalanced 2026-05-13 per `feedback_graphic_basics.md` rules 10/11:
    # - Display num_size reduced from 108–120 → 56–64 (rule 11 typography balance)
    # - Body text raised from 14–16 → 17–18 (rule 11 legibility)
    # - card_w narrowed from 400 → 340 so middle band has 240px gutter (rule 10)
    if aspect == "square":
        # Top/bottom stack at 1:1 — before-block top half, after-block bottom half.
        # num_size 56 same as og/wide so the 56/14 = 4.0× ratio stays at MED ceiling.
        return dict(
            w=1200, h=1200, eyebrow_y=110, title_y=190, title_size=46, subtitle_y=240,
            cards_y=300, card_h=320, num_size=56, takeaway_y=1060,
            layout_mode="stack", card_w=860,
        )
    if aspect == "wide":
        return dict(
            w=1200, h=675, eyebrow_y=80, title_y=140, title_size=38, subtitle_y=176,
            cards_y=240, card_h=240, num_size=56, takeaway_y=540,
            layout_mode="side", card_w=340,
        )
    # og default
    return dict(
        w=1200, h=630, eyebrow_y=78, title_y=138, title_size=38, subtitle_y=176,
        cards_y=222, card_h=220, num_size=56, takeaway_y=500,
        layout_mode="side", card_w=340,
    )


def render(config):
    aspect = config.get("aspect", "og")
    L = _layout(aspect)
    eyebrow = config.get("eyebrow", "RESEARCH · ZERG AI")
    title = config["title"]
    subtitle = config.get("subtitle", "")
    bv = config["before_value"]
    av = config["after_value"]
    bl = config.get("before_label", "BEFORE")
    al = config.get("after_label", "AFTER")
    bc = config.get("before_caption", "")
    ac = config.get("after_caption", "")
    bs = config.get("before_subtext", "")
    as_ = config.get("after_subtext", "")
    ml = config.get("middle_label", "")
    mc = config.get("middle_caption", "")
    takeaway = config.get("takeaway", "")
    takeaway_sub = config.get("takeaway_sub", "")
    source = config.get("source", "")

    w, h = L["w"], L["h"]
    cy = L["cards_y"]
    ch = L["card_h"]
    base_n_size = L["num_size"]
    card_w = L["card_w"]
    layout_mode = L["layout_mode"]

    def _fit_num_size(value: str) -> int:
        """Auto-shrink display number if it's a long word (>4 chars) to fit the card."""
        n = len(value)
        # Empirical: at base_n_size 64, "22%" (3) fits; "Tuesday" (7) doesn't.
        # Available width ≈ card_w - 32px padding = 308 (wide/og) or 828 (square stack)
        avail = card_w - 32
        # Estimated text width per char ≈ 0.55 × font-size
        max_size = int(avail / (n * 0.55))
        return min(base_n_size, max_size)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        f'<rect width="{w}" height="{h}" fill="{p.BG}"/>',
        f'<text x="{w//2}" y="{L["eyebrow_y"]}" text-anchor="middle" font-family="{p.FONT}" font-size="16" letter-spacing="3" font-weight="600" fill="{p.MUTED}">{_esc(eyebrow)}</text>',
        f'<text x="{w//2}" y="{L["title_y"]}" text-anchor="middle" font-family="{p.FONT}" font-size="{L["title_size"]}" font-weight="700" fill="{p.TEXT}">{_esc(title)}</text>',
    ]
    if subtitle:
        parts.append(f'<text x="{w//2}" y="{L["subtitle_y"]}" text-anchor="middle" font-family="{p.FONT}" font-size="18" fill="{p.MUTED}">{_esc(subtitle)}</text>')

    # Card geometry
    if layout_mode == "stack":
        # Square: top-bottom stack — before card on top half, after card on bottom half
        before_x = (w - card_w) // 2
        before_y = cy
        after_x = before_x
        after_y = cy + ch + 60  # middle band gap = 60px
    else:
        # og/wide: side-by-side with 240px middle gutter (was 160px in v2 — Rule 10)
        middle_gap = 240
        before_x = (w - middle_gap) // 2 - card_w
        before_y = cy
        after_x = (w + middle_gap) // 2
        after_y = cy

    # Per-card text positions (relative to card top).
    # Rule 12: dominant text (display number) glyph center MUST equal box geometric center.
    # For text-anchor=middle with y=baseline, glyph_center ≈ y - 0.35*fs.
    # So num_dy (baseline) = ch/2 + 0.35*fs. The label sits above, subtext+caption below.
    num_dy = int(ch / 2 + 0.35 * base_n_size)  # display number — visually centered
    label_dy = max(34, num_dy - int(0.85 * base_n_size) - 18)  # 18px gap above top of glyph
    sub_dy = num_dy + 32       # 32px below baseline (≈ 18px below bottom of glyph)
    cap_dy = sub_dy + 26       # 26px below subtext

    # Before card (amber)
    bv_size = _fit_num_size(bv) if bv else base_n_size
    bcx = before_x + card_w // 2
    parts += [
        f'<rect x="{before_x}" y="{before_y}" width="{card_w}" height="{ch}" rx="14" fill="{p.CARD}" stroke="{p.AMBER}" stroke-width="2"/>',
        f'<text x="{bcx}" y="{before_y + label_dy}" text-anchor="middle" font-family="{p.FONT}" font-size="14" letter-spacing="2" font-weight="600" fill="{p.MUTED}">{_esc(bl)}</text>',
        f'<text x="{bcx}" y="{before_y + num_dy}" text-anchor="middle" font-family="{p.FONT}" font-size="{bv_size}" font-weight="700" fill="{p.AMBER}">{_esc(bv)}</text>',
    ]
    if bs:
        parts.append(f'<text x="{bcx}" y="{before_y + sub_dy}" text-anchor="middle" font-family="{p.FONT}" font-size="18" fill="{p.TEXT}">{_esc(bs)}</text>')
    if bc:
        parts.append(f'<text x="{bcx}" y="{before_y + cap_dy}" text-anchor="middle" font-family="{p.FONT}" font-size="14" fill="{p.MUTED}" font-style="italic">{_esc(bc)}</text>')

    # Middle band — arrow + labels (between the cards, horizontal or vertical depending on mode)
    if layout_mode == "stack":
        # Vertical arrow between top and bottom cards
        arrow_cx = w // 2
        arrow_top_y = before_y + ch + 12
        arrow_bot_y = after_y - 12
        parts += [
            f'<line x1="{arrow_cx}" y1="{arrow_top_y}" x2="{arrow_cx}" y2="{arrow_bot_y - 8}" stroke="{p.MUTED}" stroke-width="2.5"/>',
            f'<polygon points="{arrow_cx},{arrow_bot_y} {arrow_cx-8},{arrow_bot_y-14} {arrow_cx+8},{arrow_bot_y-14}" fill="{p.MUTED}"/>',
        ]
        if ml:
            parts.append(f'<text x="{arrow_cx + 60}" y="{(arrow_top_y + arrow_bot_y)//2 - 6}" text-anchor="start" font-family="{p.FONT}" font-size="14" letter-spacing="1.5" font-weight="600" fill="{p.MUTED}">{_esc(ml)}</text>')
        if mc:
            parts.append(f'<text x="{arrow_cx + 60}" y="{(arrow_top_y + arrow_bot_y)//2 + 14}" text-anchor="start" font-family="{p.FONT}" font-size="14" font-style="italic" fill="{p.MUTED}">{_esc(mc)}</text>')
    else:
        # Horizontal arrow in the middle gutter
        arrow_y = cy + ch // 2
        gutter_cx = w // 2
        arrow_left_x = gutter_cx - 80
        arrow_right_x = gutter_cx + 80
        parts += [
            f'<line x1="{arrow_left_x}" y1="{arrow_y}" x2="{arrow_right_x - 8}" y2="{arrow_y}" stroke="{p.MUTED}" stroke-width="2.5"/>',
            f'<polygon points="{arrow_right_x},{arrow_y} {arrow_right_x-14},{arrow_y-8} {arrow_right_x-14},{arrow_y+8}" fill="{p.MUTED}"/>',
        ]
        # Auto-truncate middle labels to fit gutter width (Rule 10: no text bleed)
        if ml:
            ml_clip = ml if len(ml) <= 22 else ml[:19] + "..."
            parts.append(f'<text x="{gutter_cx}" y="{arrow_y - 28}" text-anchor="middle" font-family="{p.FONT}" font-size="14" letter-spacing="1.5" font-weight="600" fill="{p.MUTED}">{_esc(ml_clip)}</text>')
        if mc:
            mc_clip = mc if len(mc) <= 26 else mc[:23] + "..."
            parts.append(f'<text x="{gutter_cx}" y="{arrow_y + 30}" text-anchor="middle" font-family="{p.FONT}" font-size="14" font-style="italic" fill="{p.MUTED}">{_esc(mc_clip)}</text>')

    # After card (green)
    av_size = _fit_num_size(av) if av else base_n_size
    acx = after_x + card_w // 2
    parts += [
        f'<rect x="{after_x}" y="{after_y}" width="{card_w}" height="{ch}" rx="14" fill="{p.CARD}" stroke="{p.GREEN}" stroke-width="2.5"/>',
        f'<text x="{acx}" y="{after_y + label_dy}" text-anchor="middle" font-family="{p.FONT}" font-size="14" letter-spacing="2" font-weight="600" fill="{p.MUTED}">{_esc(al)}</text>',
        f'<text x="{acx}" y="{after_y + num_dy}" text-anchor="middle" font-family="{p.FONT}" font-size="{av_size}" font-weight="700" fill="{p.GREEN}">{_esc(av)}</text>',
    ]
    if as_:
        parts.append(f'<text x="{acx}" y="{after_y + sub_dy}" text-anchor="middle" font-family="{p.FONT}" font-size="18" fill="{p.TEXT}">{_esc(as_)}</text>')
    if ac:
        parts.append(f'<text x="{acx}" y="{after_y + cap_dy}" text-anchor="middle" font-family="{p.FONT}" font-size="14" fill="{p.MUTED}" font-style="italic">{_esc(ac)}</text>')

    # Bottom band
    if takeaway:
        parts.append(f'<text x="{w//2}" y="{L["takeaway_y"]}" text-anchor="middle" font-family="{p.FONT}" font-size="20" font-weight="600" fill="{p.TEXT}">{_esc(takeaway)}</text>')
    if takeaway_sub:
        parts.append(f'<text x="{w//2}" y="{L["takeaway_y"] + 30}" text-anchor="middle" font-family="{p.FONT}" font-size="14" fill="{p.MUTED}">{_esc(takeaway_sub)}</text>')
    if source:
        src_y = L["takeaway_y"] + 70
        parts.append(f'<text x="{w//2}" y="{src_y}" text-anchor="middle" font-family="{p.FONT}" font-size="14" fill="{p.MUTED}">{_esc(source)}</text>')

    parts.append("</svg>")
    return "\n".join(parts)
