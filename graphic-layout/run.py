#!/usr/bin/env python3
"""Minimal graphic-layout runner.

Provides:
- `review`: write a structured review scaffold for a rendered asset
- `template`: print the canonical checklist for a named intent

Each `review` invocation writes a record to `sent-log.jsonl` (asset path +
sha256 + review path + target kind + ts). `learn.py` later checks whether
the asset has been re-rendered (different sha256) since the review and
captures that as a "review-prompted-edit" signal in `corrections.md`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

try:
    from PIL import Image
except Exception:
    Image = None


SKILL_DIR = Path(__file__).parent
SENT_LOG = SKILL_DIR / "sent-log.jsonl"


def sha256_file(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def append_sent_log(record: dict) -> None:
    SENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(SENT_LOG, "a") as f:
        f.write(json.dumps(record) + "\n")


TEMPLATES = {
    "hero": {
        "canvas": "1200x630",
        "summary": "Centered or intentional rule-of-thirds headline with one supporting visual.",
        "checks": [
            "Single dominant headline",
            "No informationally-empty eyebrow",
            "Support visual anchored, not drifting to a side without reason",
        ],
    },
    "split-comparison": {
        "canvas": "1200x630",
        "summary": "50/50 comparison with equal visual weight on both sides.",
        "checks": [
            "Left and right feel equally weighted",
            "Comparison labels are obvious",
            "No decorative dead zone replacing content on one side",
        ],
    },
    "stat-strip": {
        "canvas": "1200x630",
        "summary": "Centered title above three equal-width stat regions.",
        "checks": [
            "Stat blocks align vertically",
            "No one stat visually dominates unless intentional",
            "Whitespace between blocks is consistent",
        ],
    },
    "annotated-screenshot": {
        "canvas": "1600x720",
        "summary": "Product pane with side rail or separated callouts.",
        "checks": [
            "Callouts do not sit on top of the exact UI element they describe",
            "Primary screenshot remains readable",
            "Numbering / labels are consistent",
        ],
    },
    "title-card": {
        "canvas": "1200x630",
        "summary": "Brand + one-line headline + CTA + one support element.",
        "checks": [
            "One dominant focal point",
            "Bookend feels branded, not generic",
            "Bottom CTA has breathing room",
        ],
    },
}


def image_info(path: Path) -> tuple[int, int]:
    if Image is None:
        raise RuntimeError("Pillow is required for review mode")
    with Image.open(path) as img:
        return img.size


def review_asset(path: Path, target_kind: str, out_dir: Path) -> Path:
    width, height = image_info(path)
    edge_zone = max(40, round(min(width, height) * 0.05))
    top_band = round(height * 0.15)
    bottom_band = round(height * 0.15)
    template = TEMPLATES.get(target_kind, TEMPLATES["hero"])
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{path.stem}-{ts}.review.md"
    lines = [
        f"# Graphic Layout Review: {path.stem}",
        "",
        f"**File:** `{path}`",
        f"**Target kind:** `{target_kind}`",
        f"**Canvas:** `{width}x{height}`",
        f"**Template expectation:** {template['summary']}",
        "",
        "## Deterministic geometry notes",
        "",
        f"- Edge danger zone: `{edge_zone}px` from each edge",
        f"- Top band to inspect: top `{top_band}px`",
        f"- Bottom band to inspect: bottom `{bottom_band}px`",
        "",
        "## Review checklist",
        "",
    ]
    lines.extend(f"- ☐ {item}" for item in template["checks"])
    lines += [
        "",
        "## Findings",
        "",
        "Use this section for concrete HIGH / MEDIUM / LOW findings after visual inspection.",
        "",
        "### F1 — (fill in)",
        "**Rule:**",
        "**Confidence:**",
        "**Issue:**",
        "**Suggested fix:**",
        "",
        "## Notes",
        "",
        "- This runner provides a structured review surface and geometry hints.",
        "- It does not attempt OCR or semantic layout detection.",
    ]
    out_path.write_text("\n".join(lines) + "\n")
    append_sent_log({
        "ts": datetime.now().isoformat(timespec="seconds"),
        "source_path": str(path),
        "source_sha256": sha256_file(path),
        "source_size": [width, height],
        "target_kind": target_kind,
        "review_path": str(out_path),
    })
    return out_path


def emit_template(intent: str, canvas: str) -> str:
    data = TEMPLATES[intent]
    chosen_canvas = canvas or data["canvas"]
    return "\n".join(
        [
            f"# Graphic Template: {intent}",
            "",
            f"**Canvas:** `{chosen_canvas}`",
            f"**Summary:** {data['summary']}",
            "",
            "## Checks",
            "",
            *[f"- {item}" for item in data["checks"]],
        ]
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)

    review = sub.add_parser("review")
    review.add_argument("asset")
    review.add_argument("--target-kind", default="hero", choices=sorted(TEMPLATES.keys()))
    review.add_argument("--out-dir", default="/tmp/graphic-layout")

    template = sub.add_parser("template")
    template.add_argument("intent", choices=sorted(TEMPLATES.keys()))
    template.add_argument("--canvas", default="")

    args = ap.parse_args()

    if args.mode == "review":
        out = review_asset(Path(args.asset).expanduser().resolve(), args.target_kind, Path(args.out_dir))
        print(out)
        return 0

    print(emit_template(args.intent, args.canvas))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
