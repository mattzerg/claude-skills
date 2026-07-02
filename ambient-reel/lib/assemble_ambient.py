#!/usr/bin/env python3
"""
assemble_ambient — turn a set of clips + one music track into a single
ambient reel: normalize every clip to identical params, apply ONE color
grade to all of them (the #1 coherence lever), hard-cut on a fixed grid,
bed the music (loudnorm + short fades), export H.264 / 30fps / yuv420p /
+faststart so it passes the video-review gate.

LEAN BY DESIGN: fixed cut grid + one grade preset + hard cuts. BPM beat-sync
and true seamless-loop seam handling are intentionally deferred until a real
generated reel proves the format is worth that polish (see SKILL.md).

CLI:
    assemble_ambient.py --clips a.mp4 b.mp4 ... --music m.mp3 --out out.mp4 \
        --width 1080 --height 1920 --fps 30 --clip-seconds 3.0 --grade teal_amber
    # BPM mode (clip length = bars * 4 beats * 60 / bpm):
    assemble_ambient.py --clips ... --bpm 100 --bars 2 ...
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

# One grade per preset, applied identically to every clip.
GRADES = {
    "none": "null",
    "teal_amber": (
        "colorbalance=rs=-0.05:bs=0.06:rm=0.05:bm=-0.03:rh=0.08:bh=-0.06,"
        "eq=contrast=1.06:saturation=1.08:gamma=0.98"
    ),
    "blue_hour": (
        "colorbalance=rs=-0.08:bs=0.10:bm=0.04:bh=0.06,"
        "eq=contrast=1.05:saturation=1.04:gamma=0.96:brightness=-0.02"
    ),
    "neon_noir": (
        "colorbalance=rs=0.04:bs=0.08:rm=-0.03:bm=0.05:rh=0.06:bh=0.04,"
        "eq=contrast=1.12:saturation=1.18:gamma=0.92:brightness=-0.03"
    ),
    "warm_dawn": (
        "colorbalance=rs=0.07:bs=-0.05:rm=0.04:bh=-0.04,"
        "eq=contrast=1.04:saturation=1.06:gamma=1.02"
    ),
    # LOCKED Omphalos grade (linear part of "teal-amber-neon v2"): de-greens the shadows
    # to cyan-blue, crushes blacks, S-curve + vibrance. Pair with a bloom+grain finishing
    # pass for the full look. See omphalos-visual-bible-v1.md §v1.1.
    "neon_v2": (
        "curves=master='0/0 0.06/0.02 0.5/0.5 0.94/0.97 1/1':green='0/0 0.5/0.46 1/1',"
        "colorbalance=rs=-0.03:gs=-0.06:bs=0.08:rm=0.02:bm=-0.02:rh=0.06:bh=-0.05,"
        "eq=contrast=1.12:saturation=1.20:gamma=0.97"
    ),
    # neon_v3 (LOCKED 2026-07-01) — neon_v2 + DE-PURPLE. neon_v2's de-green let magenta accents
    # bleed the haze to lavender (the dominant fail mode on the v1.2 pushed batch). v3 pulls red out
    # of mids/highs, adds green to counter magenta, nudges hue violet->blue, eases saturation. Holds
    # cyan-blue + amber vs near-black. This is the default for Omphalos pushed-bar frames.
    "neon_v3": (
        "curves=master='0/0 0.06/0.02 0.5/0.5 0.94/0.97 1/1':green='0/0 0.5/0.46 1/1',"
        "colorbalance=rs=-0.04:gs=-0.04:bs=0.07:rm=-0.03:gm=0.04:bm=-0.01:rh=-0.02:gh=0.03:bh=-0.06,"
        "eq=contrast=1.13:saturation=1.10:gamma=0.97,hue=h=-7"
    ),
}


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _grade_filter(name: str) -> str:
    if name not in GRADES:
        raise ValueError(f"unknown grade {name}; choose {list(GRADES)}")
    return GRADES[name]


def clip_seconds(args) -> float:
    if getattr(args, "bpm", None):
        beats = args.bars * 4  # assume 4/4
        return round(beats * 60.0 / args.bpm, 3)
    return float(args.clip_seconds)


def normalize_clip(src: Path, dst: Path, w: int, h: int, fps: int, dur: float,
                   grade: str, finish: bool = True) -> None:
    # Shared finishing stack (applied identically to every clip): a vignette +
    # faint temporal grain. Per the 2026-06-30 videographer review, this glues
    # independently-generated clips together more than color alone, and the
    # temporal grain survives platform recompression (kills banding on dark skies).
    finish_chain = ",vignette,noise=alls=6:allf=t+u" if finish else ""
    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},setsar=1,{_grade_filter(grade)}{finish_chain},"
        f"fps={fps},format=yuv420p"
    )
    _run([
        "ffmpeg", "-y", "-v", "error", "-i", str(src),
        "-t", f"{dur:.3f}", "-vf", vf,
        "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", str(dst),
    ])


def concat_clips(parts: list[Path], dst: Path) -> None:
    listfile = dst.parent / "_concat.txt"
    listfile.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    _run([
        "ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
        "-i", str(listfile), "-c", "copy", "-movflags", "+faststart", str(dst),
    ])


def add_music(video: Path, music: Path, dst: Path, total: float, fps: int) -> None:
    fade_out_start = max(0.0, total - 0.6)
    a_chain = (
        f"[1:a]aloudnorm=I=-16:TP=-1.5:LRA=11,"
        f"atrim=0:{total:.3f},"
        f"afade=t=in:st=0:d=0.5,"
        f"afade=t=out:st={fade_out_start:.3f}:d=0.6[a]"
    )
    _run([
        "ffmpeg", "-y", "-v", "error",
        "-i", str(video), "-i", str(music),
        "-filter_complex", a_chain,
        "-map", "0:v", "-map", "[a]",
        "-r", str(fps),
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest", "-movflags", "+faststart", str(dst),
    ])


def assemble(clips: list[Path], out: Path, music: Path | None,
             w: int, h: int, fps: int, dur: float, grade: str, finish: bool = True) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="ambient_", dir=out.parent))
    parts = []
    for i, c in enumerate(clips):
        p = work / f"norm_{i:02d}.mp4"
        normalize_clip(c, p, w, h, fps, dur, grade, finish)
        parts.append(p)
    silent = work / "silent.mp4"
    concat_clips(parts, silent)
    total = round(dur * len(clips), 3)
    if music:
        add_music(silent, music, out, total, fps)
    else:
        # No music: keep the silent master (valid silent-first reel).
        _run(["ffmpeg", "-y", "-v", "error", "-i", str(silent),
              "-c", "copy", "-movflags", "+faststart", str(out)])
    return {
        "out": str(out), "clips": len(clips), "clip_seconds": dur,
        "total_seconds": total, "grade": grade, "finish": finish,
        "music": str(music) if music else None,
        "dims": f"{w}x{h}", "fps": fps,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--clips", nargs="+", required=True)
    ap.add_argument("--music")
    ap.add_argument("--out", required=True)
    ap.add_argument("--width", type=int, default=1080)
    ap.add_argument("--height", type=int, default=1920)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--clip-seconds", type=float, default=3.0)
    ap.add_argument("--bpm", type=float)
    ap.add_argument("--bars", type=int, default=2)
    ap.add_argument("--grade", default="teal_amber", choices=list(GRADES))
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--no-finish", action="store_true", help="disable the vignette+grain finishing stack")
    args = ap.parse_args()

    dur = clip_seconds(args)
    music = None if args.no_audio or not args.music else Path(args.music).expanduser()
    report = assemble(
        [Path(c).expanduser() for c in args.clips],
        Path(args.out).expanduser(), music,
        args.width, args.height, args.fps, dur, args.grade, not args.no_finish,
    )
    import json
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
