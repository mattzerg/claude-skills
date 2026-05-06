"""Funnel template: N → M → K distillation/compression visual.

Use case: any "raw → unique → filtered" or "many → few → essential" story.
The agents-that-remember body-1 diagram is the canonical example
(1,178 raw failures → 174 unique patterns → 78 reusable rules).

Aspects:
    - body      1600×900   (blog inline)
    - square    1200×1200  (LinkedIn 1:1)

Required config:
    title           str
    stages          list[dict]   1–4 stages, top to bottom widening box on top, narrowing
                                 each stage: { value, label, sub, color (optional) }

Optional:
    subtitle        str
    arrow_labels    list[str]    italic labels between stages (n-1 of them)
    result_line     str          bottom emphasized line (with optional <tspan> highlights)
    source          str
    aspect          str          "body" (default) | "square"
"""
from . import _palette as p


DESCRIPTION = "Multi-stage compression/distillation funnel (e.g. raw → unique → filtered)."

DEFAULT_VIEWBOX = (1600, 900)

EXAMPLE_CONFIG = {
    "title": "Distilling 200 Triton Tasks Into 78 Reusable Rules",
    "subtitle": "Each step compresses what the agent learned across the run",
    "stages": [
        {"value": "1,178", "label": "Raw Failure Traces", "sub": "collected across 200 synthetic Triton tasks", "color": p.AMBER},
        {"value": "174", "label": "Unique Failure Patterns", "sub": "distinct ways things went wrong", "color": p.BLUE},
        {"value": "78", "label": "High-Frequency Rules", "sub": "a validity rulebook the agent carries forward", "color": p.GREEN},
    ],
    "arrow_labels": ["deduplicate similar errors", "filter by frequency"],
    "result_line": "Effect on single-pass correctness: 22% → 54%",
    "source": "Source: AdaExplore (Du et al., 2026)",
    "aspect": "body",
}


def _layout(aspect):
    if aspect == "square":
        return dict(w=1200, h=1200, top_pad=120, title_size=46, sub_size=18,
                    stages_top=320, stage_h=130, stage_gap=50,
                    result_y=1080, source_y=1135)
    # body default
    return dict(w=1600, h=900, top_pad=80, title_size=34, sub_size=20,
                stages_top=170, stage_h=150, stage_gap=20,
                result_y=830, source_y=865)


def render(config):
    aspect = config.get("aspect", "body")
    L = _layout(aspect)
    title = config["title"]
    subtitle = config.get("subtitle", "")
    stages = config["stages"]
    arrow_labels = config.get("arrow_labels", [])
    result_line = config.get("result_line", "")
    source = config.get("source", "")

    n = len(stages)
    if n < 1 or n > 4:
        raise ValueError("funnel requires 1–4 stages")

    w, h = L["w"], L["h"]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        f'<rect width="{w}" height="{h}" fill="{p.BG}"/>',
        f'<text x="{w//2}" y="{L["top_pad"]}" text-anchor="middle" font-family="{p.FONT}" font-size="{L["title_size"]}" font-weight="600" fill="{p.TEXT}">{title}</text>',
    ]
    if subtitle:
        parts.append(f'<text x="{w//2}" y="{L["top_pad"] + 36}" text-anchor="middle" font-family="{p.FONT}" font-size="{L["sub_size"]}" fill="{p.MUTED}">{subtitle}</text>')

    # Stage boxes — widest on top, narrowing each step
    base_w = int(w * 0.75)
    width_step = int(base_w * 0.18 / max(1, n - 1)) if n > 1 else 0
    y = L["stages_top"]
    sh = L["stage_h"]
    gap = L["stage_gap"]

    for i, stage in enumerate(stages):
        sw = base_w - i * width_step * 2  # narrow symmetrically
        sx = (w - sw) // 2
        color = stage.get("color", [p.AMBER, p.BLUE, p.GREEN, p.MUTED][i % 4])
        stroke_w = 3 if i == n - 1 else 2

        # Number font scales smaller per stage
        num_size = 68 - i * 5
        parts += [
            f'<rect x="{sx}" y="{y}" width="{sw}" height="{sh}" rx="14" fill="{p.CARD}" stroke="{color}" stroke-width="{stroke_w}"/>',
            f'<text x="{w//2}" y="{y + sh*0.42}" text-anchor="middle" font-family="{p.FONT}" font-size="{num_size}" font-weight="700" fill="{color}">{stage["value"]}</text>',
            f'<text x="{w//2}" y="{y + sh*0.68}" text-anchor="middle" font-family="{p.FONT}" font-size="22" font-weight="600" fill="{p.TEXT}">{stage["label"]}</text>',
        ]
        if stage.get("sub"):
            parts.append(f'<text x="{w//2}" y="{y + sh*0.88}" text-anchor="middle" font-family="{p.FONT}" font-size="17" fill="{p.MUTED}">{stage["sub"]}</text>')

        # Arrow + label to next stage
        if i < n - 1:
            ay1 = y + sh + 5
            ay2 = ay1 + gap + 25
            parts += [
                f'<line x1="{w//2}" y1="{ay1}" x2="{w//2}" y2="{ay2 - 5}" stroke="{p.MUTED}" stroke-width="2"/>',
                f'<polygon points="{w//2},{ay2} {w//2 - 7},{ay2 - 12} {w//2 + 7},{ay2 - 12}" fill="{p.MUTED}"/>',
            ]
            if i < len(arrow_labels):
                parts.append(f'<text x="{w//2 + 20}" y="{(ay1 + ay2) // 2 + 4}" font-family="{p.FONT}" font-size="17" fill="{p.MUTED}" font-style="italic">{arrow_labels[i]}</text>')

        y = y + sh + gap + 35

    # Result line at bottom
    if result_line:
        parts.append(f'<text x="{w//2}" y="{L["result_y"]}" text-anchor="middle" font-family="{p.FONT}" font-size="20" fill="{p.TEXT}">{result_line}</text>')
    if source:
        parts.append(f'<text x="{w//2}" y="{L["source_y"]}" text-anchor="middle" font-family="{p.FONT}" font-size="15" fill="{p.MUTED}">{source}</text>')

    parts.append("</svg>")
    return "\n".join(parts)
