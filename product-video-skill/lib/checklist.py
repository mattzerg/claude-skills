#!/usr/bin/env python3
"""Pre-publish checklist for product videos.

Auto-checks the verifiable items (codec, faststart, dimensions, frame rate,
duration sanity). Prints the human-judgement items with a checkbox prompt
so the approver records their answer.

Usage:
    python3 checklist.py /path/to/video.mp4 [--storyboard /path/to/storyboard.json]

Returns 0 if all auto-checks pass + human signs off; non-zero otherwise.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path


# 15 items per the best-practices research.
HUMAN_ITEMS = [
    "Value prop is visible on screen by 0:03 (no logo bumper before the hook).",
    "First frame is interesting alone — would work as the autoplay-paused thumbnail.",
    "Title/caption copy names the capability — NOT 'Watch this.' or other meta copy.",
    "Captions read clearly on a phone (≥36px equivalent at 1080p, scrimmed).",
    "Captions sync to the action within ±300ms; no caption lingers past its action.",
    "Video plays meaningfully with sound off (mute and watch once to confirm).",
    "UI fills ≥75% of frame area; no >25% empty brand-color expanses.",
    "Cursor moves are smoothed; zooms held ≥1.0s on the moment.",
    "ONE mechanic per video (didn't try to teach two things in 30s).",
    "End card has: brand mark + one-line headline + verb-led CTA + URL + 3–5s hold.",
    "No pricing in end card unless price IS the news.",
    "Aspect-ratio variants exist for the channels it'll ship on (or planned).",
    "Bottom 12% of frame is clear of important content (platform UI overlays).",
]


def ffprobe(video_path):
    """Return a dict of useful video properties."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,r_frame_rate,duration",
        "-show_entries", "format=duration,bit_rate,format_name",
        "-of", "json",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    stream = data.get("streams", [{}])[0]
    fmt = data.get("format", {})

    fr = stream.get("r_frame_rate", "30/1")
    if "/" in fr:
        n, d = fr.split("/")
        fps = float(n) / float(d) if float(d) != 0 else 30.0
    else:
        fps = float(fr)

    return {
        "codec": stream.get("codec_name", "unknown"),
        "width": stream.get("width", 0),
        "height": stream.get("height", 0),
        "fps": fps,
        "duration": float(fmt.get("duration", stream.get("duration", 0)) or 0),
        "bitrate": int(fmt.get("bit_rate", 0) or 0),
        "format": fmt.get("format_name", ""),
    }


def has_faststart(video_path):
    """Check whether the moov atom is at the start of the file (web autoplay friendly)."""
    cmd = ["ffprobe", "-v", "trace", "-i", str(video_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stderr
    # If we see 'moov' before 'mdat' in the trace, faststart is present.
    moov_idx = output.find(" type:'moov'")
    mdat_idx = output.find(" type:'mdat'")
    if moov_idx == -1 or mdat_idx == -1:
        return None  # unknown
    return moov_idx < mdat_idx


def auto_checks(video_path):
    results = []
    try:
        probe = ffprobe(video_path)
    except Exception as e:
        results.append(("ffprobe ran successfully", False, str(e)))
        return results

    # Codec
    results.append((
        "Codec is H.264 (h264)",
        probe["codec"] == "h264",
        f"got {probe['codec']}",
    ))

    # 1080p (height 1080) or close to it
    results.append((
        "Frame height ≥ 1080",
        probe["height"] >= 1080,
        f"got {probe['width']}x{probe['height']}",
    ))

    # Frame rate 30 or 60 (not 24/25)
    results.append((
        "Frame rate is 30 or 60 fps",
        round(probe["fps"]) in (30, 60),
        f"got {probe['fps']:.2f}",
    ))

    # Duration sanity — 8s to 90s
    results.append((
        "Duration between 8s and 90s",
        8 <= probe["duration"] <= 90,
        f"got {probe['duration']:.1f}s",
    ))

    # Faststart
    fs = has_faststart(video_path)
    if fs is None:
        results.append(("Faststart enabled (moov atom first)", False, "could not determine"))
    else:
        results.append(("Faststart enabled (moov atom first)", fs, "ok" if fs else "moov is after mdat"))

    return results


def human_check(items):
    print("\n=== Human-judgement items ===\n")
    print("Answer y/n for each. Hit q to abort.\n")
    fails = []
    for i, item in enumerate(items, 1):
        while True:
            ans = input(f"  [{i:>2}] {item}\n      → [y/n/q]: ").strip().lower()
            if ans in ("y", "n", "q"):
                break
        if ans == "q":
            print("\nAborted.")
            sys.exit(2)
        if ans == "n":
            fails.append(item)
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", help="Path to video file")
    ap.add_argument("--storyboard", help="Optional storyboard.json for cross-checking", default=None)
    ap.add_argument("--no-interactive", action="store_true", help="Skip the human checklist (auto-only)")
    args = ap.parse_args()

    video = Path(args.video)
    if not video.exists():
        print(f"Not found: {video}", file=sys.stderr)
        sys.exit(1)

    print(f"\n=== Auto checks for {video.name} ===\n")
    auto_results = auto_checks(video)
    auto_fails = []
    for label, ok, detail in auto_results:
        mark = "✓" if ok else "✗"
        print(f"  {mark} {label}  ({detail})")
        if not ok:
            auto_fails.append(label)

    if args.no_interactive:
        if auto_fails:
            print(f"\n{len(auto_fails)} auto check(s) failed.")
            sys.exit(1)
        print("\nAuto checks passed.")
        sys.exit(0)

    human_fails = human_check(HUMAN_ITEMS)

    print("\n=== Summary ===")
    if not auto_fails and not human_fails:
        print("✓ All checks passed. Cleared to publish.")
        sys.exit(0)
    if auto_fails:
        print(f"✗ Auto failures: {len(auto_fails)}")
        for f in auto_fails:
            print(f"    - {f}")
    if human_fails:
        print(f"✗ Human failures: {len(human_fails)}")
        for f in human_fails:
            print(f"    - {f}")
    sys.exit(1)


if __name__ == "__main__":
    main()
