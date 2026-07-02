#!/usr/bin/env python3
"""validate_hero.py — image-quality lint for Zerg blog hero/OG cards.

Exit codes:
    0  — image meets spec
    1  — usage error
    2  — image fails spec (at least one rule)

Rules (per MattZerg/_style/blog_template_rules.md §1):

HARD FAIL (gate blocks publish):
    - JPEG bytes inside .png container (Pollinations fallback signature)
    - Width < 1200 px (sub-spec)
    - Height < 600 px
    - Aspect ratio < 1.78 or > 1.95 (rejects 4:3 1.5 and square 1.0; accepts deployed 1.79 and OG 1.91)
    - File size > 2 MB

WARN (gate passes but flags for re-render or compression):
    - File size > 1 MB (OG crawlers may skip on slow links)
    - File size > 300 KB (over ideal target)
    - Aspect outside ideal [1.85, 1.95] OG band (e.g. 1.79 deployed pattern)

Used by the zpub `imagery_quality` gate. Standalone CLI for ad-hoc checks.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image

HARD_MIN_WIDTH = 1200
HARD_MIN_HEIGHT = 600
# Calibrated 2026-05-13 against Matt-approved heroes (gpt-image-1 native 1536x1024
# aspect 1.5 = 3:2). Recalibrated 2026-05-19 upward to 2.4 after the Idan-sourced
# gigacontext-threshold hero (aspect 2.334, ~21:9 ultrawide) was hard-failed by
# the prior 1.95 ceiling — see feedback_validator_calibrates_to_matt.md and
# feedback_matt_approval_preserves_state.md. Validator recalibrates to approval,
# never the other way. Ideal band stays at 1.85-1.95 so warnings still fire for
# non-OG-optimal aspects without hard-failing approved ultrawides.
HARD_ASPECT_MIN = 1.45
HARD_ASPECT_MAX = 2.40
IDEAL_ASPECT_MIN = 1.85
IDEAL_ASPECT_MAX = 1.95
SIZE_IDEAL_BYTES = 300 * 1024
SIZE_WARN_BYTES = 1024 * 1024
SIZE_HARD_BYTES = 3 * 1024 * 1024


def _detect_jpeg_in_png(path: Path) -> bool:
    """Pollinations writes JPEG bytes inside a .png container.

    Sniff the first 12 bytes: real PNG starts with 89 50 4E 47 0D 0A 1A 0A;
    JPEG starts with FF D8 FF.
    """
    with path.open("rb") as fh:
        head = fh.read(12)
    if path.suffix.lower() == ".png" and head.startswith(b"\xff\xd8\xff"):
        return True
    return False


def validate(path: Path) -> dict:
    findings = []
    info = {"path": str(path)}

    if not path.exists():
        return {"path": str(path), "ok": False, "findings": [f"file does not exist: {path}"]}

    size_bytes = path.stat().st_size
    info["size_bytes"] = size_bytes
    info["size_kb"] = round(size_bytes / 1024, 1)

    if _detect_jpeg_in_png(path):
        findings.append(
            f"JPEG bytes inside .png container — Pollinations fallback signature. "
            f"Regenerate via chatgpt-image-skill / nano-banana-pro / fal-image-skill."
        )

    try:
        with Image.open(path) as img:
            info["format"] = img.format
            info["mode"] = img.mode
            width, height = img.size
            info["width"] = width
            info["height"] = height
            info["aspect"] = round(width / height, 3) if height else 0
    except Exception as exc:
        findings.append(f"could not open as image: {exc}")
        return {**info, "ok": False, "findings": findings}

    if info["format"] not in {"PNG", "JPEG"}:
        findings.append(f"format={info['format']} — expected PNG or JPEG")

    if width < HARD_MIN_WIDTH:
        findings.append(f"width {width} < {HARD_MIN_WIDTH} (sub-spec; likely Pollinations fallback)")

    if height < HARD_MIN_HEIGHT:
        findings.append(f"height {height} < {HARD_MIN_HEIGHT}")

    aspect = info["aspect"]
    if aspect < HARD_ASPECT_MIN or aspect > HARD_ASPECT_MAX:
        findings.append(
            f"aspect ratio {aspect} outside hard band [{HARD_ASPECT_MIN}, {HARD_ASPECT_MAX}] "
            f"(target 1.91:1 OG card spec; deployed 1.79 also accepted)"
        )
    elif aspect < IDEAL_ASPECT_MIN or aspect > IDEAL_ASPECT_MAX:
        info.setdefault("warnings", []).append(
            f"aspect ratio {aspect} outside ideal [{IDEAL_ASPECT_MIN}, {IDEAL_ASPECT_MAX}] "
            f"(acceptable but not OG-card optimal)"
        )

    if size_bytes > SIZE_HARD_BYTES:
        findings.append(
            f"file size {info['size_kb']} KB > {SIZE_HARD_BYTES // 1024} KB hard ceiling"
        )
    elif size_bytes > SIZE_WARN_BYTES:
        info.setdefault("warnings", []).append(
            f"file size {info['size_kb']} KB > 1 MB — OG crawlers may skip on slow links"
        )
    elif size_bytes > SIZE_IDEAL_BYTES:
        info.setdefault("warnings", []).append(
            f"file size {info['size_kb']} KB > 300 KB ideal (consider re-compressing)"
        )

    info["ok"] = len(findings) == 0
    info["findings"] = findings
    return info


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate a Zerg blog hero image.")
    ap.add_argument("path", help="path to hero image (PNG or JPEG)")
    ap.add_argument("--json", action="store_true", help="emit JSON result instead of text")
    args = ap.parse_args()

    result = validate(Path(args.path).expanduser())

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        ok = "PASS" if result.get("ok") else "FAIL"
        print(f"[{ok}] {result['path']}")
        if "width" in result:
            print(
                f"       {result.get('width')}x{result.get('height')} "
                f"aspect={result.get('aspect')} format={result.get('format')} "
                f"size={result.get('size_kb')}KB"
            )
        for finding in result.get("findings", []):
            print(f"  - {finding}")
        for warning in result.get("warnings", []):
            print(f"  ! {warning}")

    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    sys.exit(main())
