#!/usr/bin/env python3
"""
capture-validator — hard-fail gate on screen-capture quality.

Usage:
    run.py validate <video.mp4>          # validate a finished mp4
    run.py validate-image <frame.png>    # validate a single PNG
    run.py preflight                     # capture a test screenshot + validate

Bypass: CAPTURE_VALIDATOR_BYPASS=1 env var (logged).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow `python3 run.py ...` from any cwd
SKILL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL_DIR))

from lib import checks, annotate  # noqa: E402
from PIL import Image  # noqa: E402


REPORT_BASE = Path.home() / "Downloads" / "capture-validator"
LOG_PATH = Path.home() / ".claude" / "capture-validator" / "log.jsonl"


def _basename(p: Path) -> str:
    return p.stem


def _emit_report(basename: str, summary: dict, frame: Image.Image, source: str) -> Path:
    out_dir = REPORT_BASE / basename
    out_dir.mkdir(parents=True, exist_ok=True)

    # Write report.json
    report = {
        "source": source,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "passed": summary["passed"],
            "fail_count": summary["fail_count"],
            "warn_count": summary["warn_count"],
        },
        "checks": [
            {k: v for k, v in c.items() if k != "bbox" or v is not None}
            for c in summary["checks"]
        ],
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2))

    # Write violations.png
    annotated = annotate.annotate(frame, summary["checks"])
    annotated.save(out_dir / "violations.png")

    # Save raw frame too
    frame.save(out_dir / "frame.png")

    return out_dir


def _log_bypass(source: str, summary: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "bypass": True,
        "would_have_failed": [
            c["name"] for c in summary["checks"]
            if c["severity"] == "FAIL" and not c["passed"]
        ],
    }
    with LOG_PATH.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def cmd_validate(video_path: Path, source: str = checks.SOURCE_DEFAULT) -> int:
    if not video_path.exists():
        print(f"ERROR: file not found: {video_path}", file=sys.stderr)
        return 2

    try:
        meta = checks.ffprobe_meta(video_path)
    except Exception as e:
        print(f"ERROR: ffprobe failed: {e}", file=sys.stderr)
        return 2

    # Extract frame at t=1.0s (avoid first-frame anomalies)
    tmp_frame = REPORT_BASE / _basename(video_path) / "_tmp_frame.png"
    try:
        checks.extract_frame(video_path, tmp_frame, t=1.0)
    except subprocess.CalledProcessError as e:
        print(f"ERROR: ffmpeg failed extracting frame: {e}", file=sys.stderr)
        return 2

    img = Image.open(tmp_frame).convert("RGB")
    results = checks.run_all(img, meta, source=source)
    summary = checks.summarize(results)

    out_dir = _emit_report(_basename(video_path), summary, img, str(video_path))

    # Clean up temp
    try:
        tmp_frame.unlink()
    except FileNotFoundError:
        pass

    # Print summary to stdout
    _print_summary(summary, out_dir)

    if not summary["passed"]:
        if os.environ.get("CAPTURE_VALIDATOR_BYPASS") == "1":
            _log_bypass(str(video_path), summary)
            print("\n⚠ BYPASS engaged — failures logged but exit=0.", file=sys.stderr)
            return 0
        return 1
    return 0


def cmd_validate_image(image_path: Path, source: str = checks.SOURCE_DEFAULT) -> int:
    if not image_path.exists():
        print(f"ERROR: file not found: {image_path}", file=sys.stderr)
        return 2
    img = Image.open(image_path).convert("RGB")
    # Synthesize meta from image
    meta = {"width": img.size[0], "height": img.size[1], "fps": "0/0", "duration": 0}
    results = checks.run_all(img, meta, source=source)
    summary = checks.summarize(results)
    out_dir = _emit_report(_basename(image_path), summary, img, str(image_path))
    _print_summary(summary, out_dir)
    if not summary["passed"]:
        if os.environ.get("CAPTURE_VALIDATOR_BYPASS") == "1":
            _log_bypass(str(image_path), summary)
            print("\n⚠ BYPASS engaged.", file=sys.stderr)
            return 0
        return 1
    return 0


def cmd_preflight(source: str = checks.SOURCE_DEFAULT) -> int:
    """Capture a test screenshot via macOS `screencapture` and validate it."""
    out_dir = REPORT_BASE / "_preflight"
    out_dir.mkdir(parents=True, exist_ok=True)
    test_png = out_dir / f"preflight-{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.png"
    cmd = ["screencapture", "-x", "-T", "0", str(test_png)]
    try:
        subprocess.run(cmd, check=True)
    except Exception as e:
        print(f"ERROR: screencapture failed: {e}", file=sys.stderr)
        return 2
    return cmd_validate_image(test_png, source=source)


def _print_summary(summary: dict, out_dir: Path) -> None:
    print()
    print("=" * 60)
    print("CAPTURE-VALIDATOR")
    print("=" * 60)
    for c in summary["checks"]:
        if c["passed"]:
            icon = "✓"
            sev = "PASS"
        elif c["severity"] == "FAIL":
            icon = "✗"
            sev = "FAIL"
        else:
            icon = "⚠"
            sev = "WARN"
        print(f"  {icon} [{sev:4}] {c['name']:32}  {c['details']}")
    print()
    print(f"  {summary['fail_count']} FAIL · {summary['warn_count']} WARN")
    print(f"  → {out_dir}/report.json")
    print(f"  → {out_dir}/violations.png")
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="cmd", required=True)
    source_kwargs = {
        "choices": sorted(checks.VALID_SOURCES),
        "default": checks.SOURCE_DEFAULT,
        "help": "capture source — 'default' for raw screen capture, 'screen-studio' for composited Screen Studio output",
    }
    p_val = subs.add_parser("validate", help="validate a finished mp4")
    p_val.add_argument("video", type=Path)
    p_val.add_argument("--source", **source_kwargs)
    p_img = subs.add_parser("validate-image", help="validate a PNG")
    p_img.add_argument("image", type=Path)
    p_img.add_argument("--source", **source_kwargs)
    p_pre = subs.add_parser("preflight", help="screencapture + validate")
    p_pre.add_argument("--source", **source_kwargs)
    args = parser.parse_args()

    if args.cmd == "validate":
        return cmd_validate(args.video, source=args.source)
    if args.cmd == "validate-image":
        return cmd_validate_image(args.image, source=args.source)
    if args.cmd == "preflight":
        return cmd_preflight(source=args.source)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
