#!/usr/bin/env python3
"""
caption-burn — burn captions into an MP4 via Pillow + ffmpeg overlay.

Usage:
    run.py burn --input video.mp4 --caps captions.json --out captioned.mp4
    run.py burn --input video.mp4 --shotlist script.md --out captioned.mp4
    run.py burn --input video.mp4 --shotlist script.md   # auto out dir
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

from lib import render, parser  # noqa: E402


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
    """
    Build an ffmpeg filter_complex chain. Each overlay is composited with
    timing: overlay=0:0:enable='between(t,start,end)'.
    """
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


def cmd_burn(args: argparse.Namespace) -> int:
    video = Path(args.input).expanduser()
    if not video.exists():
        print(f"ERROR: video not found: {video}", file=sys.stderr)
        return 2

    # Resolve captions
    if args.caps:
        captions = json.loads(Path(args.caps).expanduser().read_text())
    elif args.shotlist:
        captions = parser.parse_shotlist(Path(args.shotlist).expanduser())
    else:
        print("ERROR: provide --caps or --shotlist", file=sys.stderr)
        return 2

    if not captions:
        print("WARN: no captions found", file=sys.stderr)
        return 1

    # Resolve output
    base = video.stem
    out_dir = Path(args.out_dir).expanduser() if args.out_dir else Path.home() / "Downloads" / "caption-burn" / base
    out_dir.mkdir(parents=True, exist_ok=True)
    out_mp4 = Path(args.out).expanduser() if args.out else out_dir / f"{base}-captioned.mp4"

    # Letterbox mode: add a black strip OUTSIDE the original frame, place
    # captions there. Default size is 12% of original height (overridable).
    video_w, video_h = _ffprobe_dims(video)
    letterbox = args.letterbox  # "bottom" | "top" | None
    letterbox_h = int(video_h * args.letterbox_pct / 100) if letterbox else 0
    if letterbox in ("bottom", "top"):
        canvas_h = video_h + letterbox_h
    else:
        canvas_h = video_h
    canvas_w = video_w

    # Render each caption PNG sized for the FULL canvas (incl. letterbox)
    caps_dir = out_dir / "captions"
    overlays: list[dict] = []
    for i, cap in enumerate(captions, start=1):
        png = caps_dir / f"cap-{cap.get('cut_id', i):>02}.png"
        # If letterbox is on, caption position is FORCED into the letterbox band
        if letterbox == "bottom":
            pos = "letterbox-bottom"
        elif letterbox == "top":
            pos = "letterbox-top"
        else:
            pos = cap.get("position", "bottom")
        meta = render.render_caption(
            text=cap["text"],
            video_w=canvas_w,
            video_h=canvas_h,
            out_path=png,
            position=pos,
            size=cap.get("size", "default"),
            letterbox_h=letterbox_h,
        )
        overlays.append({
            "png": str(png),
            "t_start": cap["t_start"],
            "t_end": cap["t_end"],
            "text": cap["text"],
            **meta,
        })

    # Build ffmpeg command — if letterboxing, pad the video first
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(video)]
    for ov in overlays:
        cmd += ["-i", ov["png"]]

    # filter_complex: optional pad → then overlay chain
    if letterbox == "bottom":
        pad = f"[0:v]pad={canvas_w}:{canvas_h}:0:0:color=black[base];"
        in_label = "[base]"
    elif letterbox == "top":
        pad = f"[0:v]pad={canvas_w}:{canvas_h}:0:{letterbox_h}:color=black[base];"
        in_label = "[base]"
    else:
        pad = ""
        in_label = "[0:v]"

    chains = []
    for i, ov in enumerate(overlays, start=1):
        out_label = f"[v{i}]"
        enable = f"between(t,{ov['t_start']},{ov['t_end']})"
        chains.append(f"{in_label}[{i}:v]overlay=0:0:enable='{enable}'{out_label}")
        in_label = out_label

    filt = pad + ";".join(chains) if chains else pad.rstrip(";")
    final_label = f"[v{len(overlays)}]" if overlays else "[base]"
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
        "caption_count": len(captions),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "captions": [
            {
                "t_start": ov["t_start"],
                "t_end": ov["t_end"],
                "text": ov["text"],
                "font_size": ov.get("font_size"),
            }
            for ov in overlays
        ],
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2))

    print(f"✓ burned {len(captions)} captions → {out_mp4}")
    print(f"  report → {out_dir}/report.json")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    subs = p.add_subparsers(dest="cmd", required=True)
    pb = subs.add_parser("burn", help="burn captions onto a video")
    pb.add_argument("--input", required=True)
    pb.add_argument("--caps")
    pb.add_argument("--shotlist")
    pb.add_argument("--out")
    pb.add_argument("--out-dir")
    pb.add_argument("--letterbox", choices=["bottom", "top"], help="Add a black strip outside the frame and place captions there (never on UI)")
    pb.add_argument("--letterbox-pct", type=float, default=12.0, help="Letterbox strip height as percent of source height (default 12)")
    args = p.parse_args()
    if args.cmd == "burn":
        return cmd_burn(args)
    p.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
