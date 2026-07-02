"""Tree template: root + binary branching with comparison panels.

Use case: "two strategies / one root" stories. The agents-that-remember body-2
diagram (small moves vs large moves under one working kernel) is the canonical
example. Works for any "approach A vs approach B, both held in parallel" frame.

Aspects:
    - body      1600×1000  (blog inline; full panels with examples)
    - wide      1200×675   (X 16:9; trimmed comparison panels, no examples)

Required config:
    title           str
    root_label      str   — center root label (e.g. "Working Kernel")
    left            dict  — { name, sub, alone_lines: [str], alone_fail: str, color (optional) }
    right           dict  — same shape

Optional:
    subtitle        str
    root_sub        str
    bottom_takeaway str   — bold line below the panels
    bottom_sub      str
    source          str
    aspect          str   "body" (default) | "wide"
    show_examples   bool  — default True for body, False for wide. If True and
                            left/right have 'examples' (list[dict{title,lines}]),
                            renders example child boxes between root and panels.
"""
from . import _palette as p


DESCRIPTION = "Root + two-way branching with parallel comparison panels (e.g. small vs large moves)."

DEFAULT_VIEWBOX = (1600, 1000)

EXAMPLE_CONFIG = {
    "title": "Two Move Types, Held in Parallel",
    "subtitle": "Tree-based search keeps small refinements and full restarts on the same board",
    "root_label": "Working Kernel",
    "root_sub": "a candidate from the pool",
    "left": {
        "name": "Small Moves",
        "sub": "patch — preserve structure",
        "alone_lines": ["Get stuck in local optima", "Can't escape a poor structural choice"],
        "alone_fail": "— this is where iterative refinement plateaus",
        "color": p.BLUE,
        "examples": [
            {"title": "Tweak Block Size", "lines": ["+ adjust tile shape", "+ rewrite reduction"]},
            {"title": "Unroll Loop", "lines": ["+ reorder ops", "+ vectorize"]},
        ],
    },
    "right": {
        "name": "Large Moves",
        "sub": "regenerate — different starting assumptions",
        "alone_lines": ["Waste time rediscovering known constraints", "Slow to converge"],
        "alone_fail": "— this is what random restarts give up",
        "color": p.GREEN,
        "examples": [
            {"title": "Switch to Fused Kernel", "lines": ["new tile strategy", "new memory layout"]},
            {"title": "Different Parallelism", "lines": ["restart from a pool peer", "with new assumptions"]},
        ],
    },
    "bottom_takeaway": "Both, Held in Parallel and Chosen by Structure",
    "bottom_sub": "— is what lets the system keep improving past where iteration plateaus",
    "source": "Source: AdaExplore (Du et al., 2026)",
    "aspect": "body",
}


def _layout(aspect):
    if aspect == "wide":
        return dict(
            w=1200, h=675, title_y=138, title_size=40, sub_y=172, sub_size=16,
            root_y=218, root_h=60, root_w=200,
            tbar_y=305, head_y=354,
            show_examples=False,
            panels_y=395, panels_h=130,
            bottom_take_y=578, source_y=612,
        )
    # body default
    return dict(
        w=1600, h=1000, title_y=70, title_size=34, sub_y=106, sub_size=20,
        root_y=160, root_h=90, root_w=380,
        tbar_y=290, head_y=348,
        show_examples=True,
        examples_y=460, examples_h=110,
        panels_y=620, panels_h=180,
        bottom_take_y=860, bottom_sub_y=894, source_y=952,
    )


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") if isinstance(s, str) else s


def render(config):
    aspect = config.get("aspect", "body")
    L = _layout(aspect)
    title = config["title"]
    subtitle = config.get("subtitle", "")
    root_label = config["root_label"]
    root_sub = config.get("root_sub", "")
    L_arm = config["left"]
    R_arm = config["right"]
    bottom_takeaway = config.get("bottom_takeaway", "")
    bottom_sub = config.get("bottom_sub", "")
    source = config.get("source", "")
    show_examples = config.get("show_examples", L["show_examples"])

    w, h = L["w"], L["h"]
    cx = w // 2
    # Branch x positions: 25% and 75% of width
    lx, rx = w // 4, w * 3 // 4

    L_color = L_arm.get("color", p.BLUE)
    R_color = R_arm.get("color", p.GREEN)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        f'<rect width="{w}" height="{h}" fill="{p.BG}"/>',
        f'<text x="{cx}" y="{L["title_y"]}" text-anchor="middle" font-family="{p.FONT}" font-size="{L["title_size"]}" font-weight="600" fill="{p.TEXT}">{_esc(title)}</text>',
    ]
    if subtitle:
        parts.append(f'<text x="{cx}" y="{L["sub_y"]}" text-anchor="middle" font-family="{p.FONT}" font-size="{L["sub_size"]}" fill="{p.MUTED}">{_esc(subtitle)}</text>')

    # Root box
    rw, rh = L["root_w"], L["root_h"]
    parts += [
        f'<rect x="{cx - rw//2}" y="{L["root_y"]}" width="{rw}" height="{rh}" rx="12" fill="{p.CARD}" stroke="{p.TEXT}" stroke-width="2"/>',
        f'<text x="{cx}" y="{L["root_y"] + rh*0.45}" text-anchor="middle" font-family="{p.FONT}" font-size="18" font-weight="600" fill="{p.TEXT}">{_esc(root_label)}</text>',
    ]
    if root_sub:
        parts.append(f'<text x="{cx}" y="{L["root_y"] + rh*0.78}" text-anchor="middle" font-family="{p.FONT}" font-size="14" fill="{p.MUTED}">{_esc(root_sub)}</text>')

    # T-bar split
    root_bottom = L["root_y"] + rh
    tb = L["tbar_y"]
    head = L["head_y"]
    parts += [
        f'<line x1="{cx}" y1="{root_bottom}" x2="{cx}" y2="{tb}" stroke="{p.MUTED}" stroke-width="2"/>',
        f'<line x1="{lx}" y1="{tb}" x2="{rx}" y2="{tb}" stroke="{p.MUTED}" stroke-width="2"/>',
        f'<line x1="{lx}" y1="{tb}" x2="{lx}" y2="{tb + 25}" stroke="{L_color}" stroke-width="2.5"/>',
        f'<line x1="{rx}" y1="{tb}" x2="{rx}" y2="{tb + 25}" stroke="{R_color}" stroke-width="2.5"/>',
    ]

    # Section heads — rendered as bordered cards (Rule 9: hierarchy consistency).
    # Branch headers were bare text in v2 (2026-05-13); Matt flagged it twice.
    head_w = 360
    head_h = 80
    head_card_y = head - 32  # raise the card so the name baseline sits inside
    for arm_cx, arm, color in [(lx, L_arm, L_color), (rx, R_arm, R_color)]:
        parts.append(
            f'<rect x="{arm_cx - head_w//2}" y="{head_card_y}" width="{head_w}" height="{head_h}" '
            f'rx="12" fill="{p.CARD}" stroke="{color}" stroke-width="2"/>'
        )
        parts.append(
            f'<text x="{arm_cx}" y="{head}" text-anchor="middle" font-family="{p.FONT}" '
            f'font-size="22" font-weight="700" fill="{color}">{_esc(arm["name"])}</text>'
        )
        parts.append(
            f'<text x="{arm_cx}" y="{head + 26}" text-anchor="middle" font-family="{p.FONT}" '
            f'font-size="14" fill="{p.MUTED}">{_esc(arm.get("sub", ""))}</text>'
        )

    # Optional examples row (body aspect only)
    if show_examples and "examples" in L_arm and "examples" in R_arm:
        ey = L["examples_y"]
        eh = L["examples_h"]

        def _examples(arm_cx, examples, color):
            local = []
            arm_top_y = head + 42
            local += [
                f'<line x1="{arm_cx}" y1="{arm_top_y}" x2="{arm_cx}" y2="{arm_top_y + 30}" stroke="{color}" stroke-width="2"/>',
            ]
            n_ex = len(examples)
            box_w = 280
            spacing = 310
            total = (n_ex - 1) * spacing
            start_x = arm_cx - total // 2
            tbar_y2 = arm_top_y + 30
            local.append(f'<line x1="{start_x}" y1="{tbar_y2}" x2="{start_x + total}" y2="{tbar_y2}" stroke="{color}" stroke-width="2"/>')
            for j, ex in enumerate(examples):
                bx = start_x + j * spacing
                local += [
                    f'<line x1="{bx}" y1="{tbar_y2}" x2="{bx}" y2="{ey}" stroke="{color}" stroke-width="2"/>',
                    f'<rect x="{bx - box_w//2}" y="{ey}" width="{box_w}" height="{eh}" rx="10" fill="{p.CARD}" stroke="{color}" stroke-width="1.5"/>',
                    f'<text x="{bx}" y="{ey + 33}" text-anchor="middle" font-family="{p.FONT}" font-size="15" font-weight="600" fill="{p.TEXT}">{_esc(ex["title"])}</text>',
                ]
                for li, line in enumerate(ex.get("lines", [])):
                    local.append(f'<text x="{bx}" y="{ey + 57 + li*22}" text-anchor="middle" font-family="{p.FONT}" font-size="13" fill="{p.MUTED}">{_esc(line)}</text>')
            return local

        parts += _examples(lx, L_arm["examples"], L_color)
        parts += _examples(rx, R_arm["examples"], R_color)

    # Comparison panels: "Alone" with each arm's failure mode
    py = L["panels_y"]
    ph = L["panels_h"]
    pw = int(w * 0.41)
    plx = (w // 2 - pw) // 2 + 0   # leftmost
    plx_left = w // 4 - pw // 2 + 40 if w > 1300 else 80
    # Simpler: split w into two panel slots
    margin = 60 if w > 1300 else 80
    pw = (w - margin * 3) // 2
    p_left_x = margin
    p_right_x = w - margin - pw
    p_cx_left = p_left_x + pw // 2
    p_cx_right = p_right_x + pw // 2

    parts += [
        f'<rect x="{p_left_x}" y="{py}" width="{pw}" height="{ph}" rx="14" fill="{p.CARD}" stroke="{L_color}" stroke-width="2"/>',
        f'<text x="{p_cx_left}" y="{py + 42}" text-anchor="middle" font-family="{p.FONT}" font-size="22" font-weight="700" fill="{L_color}">Alone</text>',
    ]
    for li, line in enumerate(L_arm.get("alone_lines", [])):
        parts.append(f'<text x="{p_cx_left}" y="{py + 78 + li*28}" text-anchor="middle" font-family="{p.FONT}" font-size="16" fill="{p.TEXT}">{_esc(line)}</text>')
    if L_arm.get("alone_fail"):
        parts.append(f'<text x="{p_cx_left}" y="{py + ph - 32}" text-anchor="middle" font-family="{p.FONT}" font-size="14" fill="{p.MUTED}" font-style="italic">{_esc(L_arm["alone_fail"])}</text>')

    parts += [
        f'<rect x="{p_right_x}" y="{py}" width="{pw}" height="{ph}" rx="14" fill="{p.CARD}" stroke="{R_color}" stroke-width="2"/>',
        f'<text x="{p_cx_right}" y="{py + 42}" text-anchor="middle" font-family="{p.FONT}" font-size="22" font-weight="700" fill="{R_color}">Alone</text>',
    ]
    for li, line in enumerate(R_arm.get("alone_lines", [])):
        parts.append(f'<text x="{p_cx_right}" y="{py + 78 + li*28}" text-anchor="middle" font-family="{p.FONT}" font-size="16" fill="{p.TEXT}">{_esc(line)}</text>')
    if R_arm.get("alone_fail"):
        parts.append(f'<text x="{p_cx_right}" y="{py + ph - 32}" text-anchor="middle" font-family="{p.FONT}" font-size="14" fill="{p.MUTED}" font-style="italic">{_esc(R_arm["alone_fail"])}</text>')

    # Bottom takeaway
    if bottom_takeaway:
        parts.append(f'<text x="{cx}" y="{L["bottom_take_y"]}" text-anchor="middle" font-family="{p.FONT}" font-size="22" font-weight="700" fill="{p.TEXT}">{_esc(bottom_takeaway)}</text>')
    if bottom_sub and "bottom_sub_y" in L:
        parts.append(f'<text x="{cx}" y="{L["bottom_sub_y"]}" text-anchor="middle" font-family="{p.FONT}" font-size="17" fill="{p.MUTED}">{_esc(bottom_sub)}</text>')
    if source:
        parts.append(f'<text x="{cx}" y="{L["source_y"]}" text-anchor="middle" font-family="{p.FONT}" font-size="14" fill="{p.MUTED}">{_esc(source)}</text>')

    parts.append("</svg>")
    return "\n".join(parts)
