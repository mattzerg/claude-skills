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
    if aspect == "square":
        return dict(
            w=1200, h=1200, eyebrow_y=120, title_y=200, title_size=50, subtitle_y=255,
            cards_y=380, card_h=280, num_size=120, takeaway_y=860,
        )
    if aspect == "wide":
        return dict(
            w=1200, h=675, eyebrow_y=80, title_y=140, title_size=40, subtitle_y=178,
            cards_y=240, card_h=220, num_size=110, takeaway_y=520,
        )
    # og default
    return dict(
        w=1200, h=630, eyebrow_y=78, title_y=138, title_size=40, subtitle_y=178,
        cards_y=218, card_h=200, num_size=108, takeaway_y=478,
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
    n_size = L["num_size"]
    cx_left = w // 2 - 200 - 80      # 320 for og (1200w)
    cx_right = w // 2 + 200 + 80     # 880 for og
    card_w = 400
    arrow_y = cy + ch // 2

    # Card vertical layout: label_y, num_y, subtext_y, italic_caption_y
    label_y = cy + 44
    num_y = cy + ch * 0.66
    sub_y = cy + ch - 44       # plain supporting line (e.g. "single-pass correctness")
    cap_italic_y = cy + ch - 22

    sx, sy = w // 2 - 60, w // 2 + 60   # arrow start/end x (centered)
    arrow_left_x = w // 2 - 60
    arrow_right_x = w // 2 + 60

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        f'<rect width="{w}" height="{h}" fill="{p.BG}"/>',
        f'<text x="{w//2}" y="{L["eyebrow_y"]}" text-anchor="middle" font-family="{p.FONT}" font-size="16" letter-spacing="3" font-weight="600" fill="{p.MUTED}">{eyebrow}</text>',
        f'<text x="{w//2}" y="{L["title_y"]}" text-anchor="middle" font-family="{p.FONT}" font-size="{L["title_size"]}" font-weight="700" fill="{p.TEXT}">{title}</text>',
    ]
    if subtitle:
        parts.append(f'<text x="{w//2}" y="{L["subtitle_y"]}" text-anchor="middle" font-family="{p.FONT}" font-size="18" fill="{p.MUTED}">{subtitle}</text>')

    # Before card (amber)
    parts += [
        f'<rect x="{cx_left - card_w//2}" y="{cy}" width="{card_w}" height="{ch}" rx="14" fill="{p.CARD}" stroke="{p.AMBER}" stroke-width="1.5"/>',
        f'<text x="{cx_left}" y="{label_y}" text-anchor="middle" font-family="{p.FONT}" font-size="14" letter-spacing="2" font-weight="600" fill="{p.MUTED}">{bl}</text>',
        f'<text x="{cx_left}" y="{num_y}" text-anchor="middle" font-family="{p.FONT}" font-size="{n_size}" font-weight="700" fill="{p.AMBER}">{bv}</text>',
    ]
    if bs:
        parts.append(f'<text x="{cx_left}" y="{sub_y}" text-anchor="middle" font-family="{p.FONT}" font-size="16" fill="{p.TEXT}">{bs}</text>')
    if bc:
        parts.append(f'<text x="{cx_left}" y="{cap_italic_y}" text-anchor="middle" font-family="{p.FONT}" font-size="13" fill="{p.MUTED}" font-style="italic">{bc}</text>')

    # Arrow + middle labels
    parts += [
        f'<line x1="{arrow_left_x}" y1="{arrow_y}" x2="{arrow_right_x - 5}" y2="{arrow_y}" stroke="{p.MUTED}" stroke-width="2.5"/>',
        f'<polygon points="{arrow_right_x},{arrow_y} {arrow_right_x-14},{arrow_y-8} {arrow_right_x-14},{arrow_y+8}" fill="{p.MUTED}"/>',
    ]
    if ml:
        parts.append(f'<text x="{w//2}" y="{arrow_y - 20}" text-anchor="middle" font-family="{p.FONT}" font-size="12" letter-spacing="1.5" font-weight="600" fill="{p.MUTED}">{ml}</text>')
    if mc:
        parts.append(f'<text x="{w//2}" y="{arrow_y + 22}" text-anchor="middle" font-family="{p.FONT}" font-size="12" font-style="italic" fill="{p.MUTED}">{mc}</text>')

    # After card (green)
    parts += [
        f'<rect x="{cx_right - card_w//2}" y="{cy}" width="{card_w}" height="{ch}" rx="14" fill="{p.CARD}" stroke="{p.GREEN}" stroke-width="2.5"/>',
        f'<text x="{cx_right}" y="{label_y}" text-anchor="middle" font-family="{p.FONT}" font-size="14" letter-spacing="2" font-weight="600" fill="{p.MUTED}">{al}</text>',
        f'<text x="{cx_right}" y="{num_y}" text-anchor="middle" font-family="{p.FONT}" font-size="{n_size}" font-weight="700" fill="{p.GREEN}">{av}</text>',
    ]
    if as_:
        parts.append(f'<text x="{cx_right}" y="{sub_y}" text-anchor="middle" font-family="{p.FONT}" font-size="16" fill="{p.TEXT}">{as_}</text>')
    if ac:
        parts.append(f'<text x="{cx_right}" y="{cap_italic_y}" text-anchor="middle" font-family="{p.FONT}" font-size="13" fill="{p.MUTED}" font-style="italic">{ac}</text>')

    # Bottom band
    if takeaway:
        parts.append(f'<text x="{w//2}" y="{L["takeaway_y"]}" text-anchor="middle" font-family="{p.FONT}" font-size="20" font-weight="600" fill="{p.TEXT}">{takeaway}</text>')
    if takeaway_sub:
        parts.append(f'<text x="{w//2}" y="{L["takeaway_y"] + 30}" text-anchor="middle" font-family="{p.FONT}" font-size="14" fill="{p.MUTED}">{takeaway_sub}</text>')
    if source:
        src_y = L["takeaway_y"] + 80
        parts.append(f'<text x="{w//2}" y="{src_y}" text-anchor="middle" font-family="{p.FONT}" font-size="13" fill="{p.MUTED}">{source}</text>')

    parts.append("</svg>")
    return "\n".join(parts)
