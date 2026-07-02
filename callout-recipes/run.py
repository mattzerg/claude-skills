#!/usr/bin/env python3
"""
callout-recipes — overlay arrows / highlights / labels / state-badges / metric-badges
onto a video via Pillow + ffmpeg overlay.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL_DIR))

from lib import recipes  # noqa: E402


def _ffprobe_dims(video: Path) -> tuple[int, int]:
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
        capture_output=True, text=True, check=True,
    )
    w, h = res.stdout.strip().split("\n")
    return int(w), int(h)


def _build_filter_complex(overlays: list[dict]) -> str:
    if not overlays:
        return ""
    chains: list[str] = []
    in_label = "[0:v]"
    for i, ov in enumerate(overlays, start=1):
        out_label = f"[v{i}]"
        enable = f"between(t,{ov['t_start']},{ov['t_end']})"
        chains.append(
            f"{in_label}[{i}:v]overlay=0:0:enable='{enable}'{out_label}"
        )
        in_label = out_label
    return ";".join(chains)


def cmd_apply(args: argparse.Namespace) -> int:
    video = Path(args.input).expanduser()
    if not video.exists():
        print(f"ERROR: video not found: {video}", file=sys.stderr)
        return 2

    callouts = json.loads(Path(args.callouts).expanduser().read_text())
    if not callouts:
        print("WARN: no callouts found", file=sys.stderr)
        return 1

    video_w, video_h = _ffprobe_dims(video)
    base = video.stem
    out_dir = Path(args.out_dir).expanduser() if args.out_dir else Path.home() / "Downloads" / "callout-recipes" / base
    out_dir.mkdir(parents=True, exist_ok=True)
    out_mp4 = Path(args.out).expanduser() if args.out else out_dir / f"{base}-annotated.mp4"

    pngs_dir = out_dir / "callouts"
    pngs_dir.mkdir(parents=True, exist_ok=True)

    overlays: list[dict] = []
    for i, spec in enumerate(callouts, start=1):
        kind = spec["type"]
        if kind not in recipes.RENDERERS:
            print(f"WARN: unknown callout type '{kind}', skipping", file=sys.stderr)
            continue
        png = pngs_dir / f"co-{i:>02}-{kind}.png"
        meta = recipes.RENDERERS[kind](spec, video_w, video_h, png)
        overlays.append({
            "png": str(png),
            "t_start": spec["t_start"],
            "t_end": spec["t_end"],
            "type": kind,
            "meta": meta,
        })

    if not overlays:
        print("ERROR: no valid callouts to render", file=sys.stderr)
        return 1

    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(video)]
    for ov in overlays:
        cmd += ["-i", ov["png"]]

    filt = _build_filter_complex(overlays)
    final_label = f"[v{len(overlays)}]"
    cmd += [
        "-filter_complex", filt,
        "-map", final_label,
        "-map", "0:a?",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-c:a", "copy",
        "-movflags", "+faststart",
        str(out_mp4),
    ]
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"ERROR: ffmpeg failed: {e}", file=sys.stderr)
        return 2

    report = {
        "input": str(video),
        "output": str(out_mp4),
        "video_dims": [video_w, video_h],
        "callout_count": len(overlays),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "callouts": [{"type": ov["type"], "t_start": ov["t_start"], "t_end": ov["t_end"]} for ov in overlays],
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2))

    print(f"✓ applied {len(overlays)} callouts → {out_mp4}")
    return 0


def cmd_preview(args: argparse.Namespace) -> int:
    callouts = json.loads(Path(args.callouts).expanduser().read_text())
    out_dir = Path(args.out).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, spec in enumerate(callouts, start=1):
        kind = spec["type"]
        if kind not in recipes.RENDERERS:
            continue
        png = out_dir / f"preview-{i:>02}-{kind}.png"
        recipes.RENDERERS[kind](spec, args.w, args.h, png)
    print(f"✓ {len(callouts)} previews → {out_dir}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    subs = p.add_subparsers(dest="cmd", required=True)
    pa = subs.add_parser("apply")
    pa.add_argument("--input", required=True)
    pa.add_argument("--callouts", required=True)
    pa.add_argument("--out")
    pa.add_argument("--out-dir")
    pp = subs.add_parser("preview")
    pp.add_argument("--callouts", required=True)
    pp.add_argument("--w", type=int, default=1920)
    pp.add_argument("--h", type=int, default=1080)
    pp.add_argument("--out", required=True)
    args = p.parse_args()
    if args.cmd == "apply":
        return cmd_apply(args)
    if args.cmd == "preview":
        return cmd_preview(args)
    p.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
