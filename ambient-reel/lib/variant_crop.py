#!/usr/bin/env python3
"""
variant_crop — reframe a master ambient reel into other aspect ratios at $0
(no FAL). Cover-crop when the target is narrower/taller than the source;
blurred-background pad when the target is wider (so no content is lost, just
aesthetic side fill). Output stays H.264 / yuv420p / faststart so it passes
the video-review gate.

CLI:
    variant_crop.py --input master_9x16.mp4 --target 1:1  --out sq.mp4
    variant_crop.py --input master_9x16.mp4 --target 16:9 --out wide.mp4
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ASPECTS = {
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "16:9": (1920, 1080),
    "4:5": (1080, 1350),
}


def _probe_wh(video: Path) -> tuple[int, int]:
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height",
         "-of", "csv=s=x:p=0", str(video)],
        capture_output=True, text=True, check=True,
    )
    w, h = res.stdout.strip().split("x")
    return int(w), int(h)


def _fps(video: Path) -> int:
    res = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", str(video)],
        capture_output=True, text=True, check=True,
    )
    fr = res.stdout.strip()
    if "/" in fr:
        n, d = fr.split("/")
        return round(float(n) / float(d)) if float(d) else 30
    return round(float(fr or 30))


def build_filter(src_w: int, src_h: int, tw: int, th: int) -> str:
    """Return a video filter that reframes src→target.

    target AR >= source AR (wider) → blurred-pad.
    target AR <  source AR (narrower/taller) → cover-crop (scale to cover, crop).
    """
    src_ar = src_w / src_h
    tgt_ar = tw / th
    if tgt_ar > src_ar + 1e-6:
        # Wider target: blurred background + centered foreground.
        return (
            f"split=2[bg][fg];"
            f"[bg]scale={tw}:{th}:force_original_aspect_ratio=increase,"
            f"crop={tw}:{th},gblur=sigma=28,eq=brightness=-0.06[bgb];"
            f"[fg]scale={tw}:{th}:force_original_aspect_ratio=decrease[fgs];"
            f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2,setsar=1"
        )
    # Narrower/taller (or equal) target: cover-crop.
    return (
        f"scale={tw}:{th}:force_original_aspect_ratio=increase,"
        f"crop={tw}:{th},setsar=1"
    )


def make_variant(src: Path, out: Path, target: str) -> Path:
    if target not in ASPECTS:
        raise ValueError(f"unknown target aspect {target}; choose {list(ASPECTS)}")
    tw, th = ASPECTS[target]
    sw, sh = _probe_wh(src)
    fps = _fps(src)
    vf = build_filter(sw, sh, tw, th)
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-v", "error", "-i", str(src),
        "-filter_complex", f"[0:v]{vf}[v]",
        "-map", "[v]", "-map", "0:a?",
        "-r", str(fps),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(out),
    ]
    subprocess.run(cmd, check=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", required=True)
    ap.add_argument("--target", required=True, choices=list(ASPECTS))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = make_variant(Path(args.input).expanduser(), Path(args.out).expanduser(), args.target)
    print(f"✓ variant {args.target} → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
