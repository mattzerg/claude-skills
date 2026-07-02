"""Parse a shot-list markdown → captions list."""

from __future__ import annotations

import re
from pathlib import Path


def parse_shotlist(md_path: Path) -> list[dict]:
    """
    Extract CAP entries from a video shot-list markdown.

    Returns list of caption dicts: [{cut_id, t_start, t_end, text, position}].
    Timing is cumulative across cuts in document order.
    """
    md = md_path.read_text()
    cuts: list[dict] = []
    in_table = False
    header_cols: list[str] = []

    for raw_line in md.splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            in_table = False
            header_cols = []
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(set(c) <= {"-", ":", " "} for c in cells if c):
            in_table = True
            continue
        if not in_table or not header_cols:
            if any("vo" in c.lower() or "caption" in c.lower() for c in cells):
                header_cols = [c.lower() for c in cells]
            continue
        if len(cells) < len(header_cols):
            continue
        row = dict(zip(header_cols, cells))
        cut_id = row.get("#") or row.get("id") or cells[0]
        dur_col = row.get("dur", "") or row.get("duration", "")
        vo_cell = next(
            (v for k, v in row.items() if "vo" in k or "caption" in k),
            None,
        )
        if vo_cell is None:
            continue
        cap_match = re.search(r"CAP:\s*`([^`]+)`", vo_cell)
        cap_text = cap_match.group(1) if cap_match else ""
        dur_match = re.match(r"([\d.]+)\s*s", dur_col)
        dur = float(dur_match.group(1)) if dur_match else 0.0
        cuts.append({"cut_id": cut_id, "dur": dur, "cap_text": cap_text})

    # Compute cumulative timing
    captions: list[dict] = []
    t = 0.0
    for c in cuts:
        if c["cap_text"]:
            captions.append({
                "cut_id": c["cut_id"],
                "t_start": t,
                "t_end": t + c["dur"],
                "text": c["cap_text"],
                "position": "bottom",
                "size": "default",
            })
        t += c["dur"]

    return captions
