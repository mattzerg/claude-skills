#!/usr/bin/env python3
"""Render a storyboard JSON as a Markdown brief for human approval.

Usage:
    python3 storyboard.py /tmp/my-storyboard.json --out /tmp/my-brief.md
    python3 storyboard.py /tmp/my-storyboard.json --out -            # stdout

The brief is what goes to the approver before recording. It surfaces:
- the brief (core message, audience, channels, length, tone)
- the beat-by-beat plan with timing budgets
- the on-screen copy for every beat (so lazy placeholder copy can't sneak through)
- the end card layout
- a pre-flight checklist (15 items)
"""
import argparse
import json
import sys
from pathlib import Path


CHECKLIST = [
    "Value prop is visible on screen by 0:03 (no logo bumper before the hook).",
    "First frame is interesting alone — would work as the autoplay-paused thumbnail.",
    "Title/caption copy names the capability — NOT 'Watch this.' or other meta copy.",
    "Captions read clearly on a phone (≥36px equivalent at 1080p, scrimmed).",
    "Captions sync to the action within ±300ms.",
    "Video plays meaningfully with sound off.",
    "UI fills ≥75% of frame area; no >25% empty brand-color expanses.",
    "Cursor moves are smoothed; zooms held ≥1.0s on the moment.",
    "ONE mechanic per video.",
    "End card has: brand mark + one-line headline + verb-led CTA + URL + 3–5s hold.",
    "No pricing in end card unless price IS the news.",
    "Aspect-ratio variants exist for planned channels.",
    "Bottom 12% of frame is clear of important content.",
]


def fmt_seconds(s):
    return f"{s:.1f}s"


def render_md(sb):
    out = []
    title = sb.get("title", sb["slug"].replace("-", " ").title())
    out.append(f"# {title} — Storyboard Brief\n")
    out.append(f"_Slug: `{sb['slug']}`_\n")

    out.append("\n## Brief\n")
    out.append(f"- **Core message:** {sb['core_message']}")
    out.append(f"- **Audience:** {sb['audience']}")
    out.append(f"- **Channels:** {', '.join(sb['channels'])}")
    out.append(f"- **Length:** {sb['length_s']:.0f}s")
    out.append(f"- **Tone:** {sb['tone']}")
    if sb.get("aspects"):
        out.append(f"- **Aspect variants:** {', '.join(sb['aspects'])}")

    audio = sb.get("audio", {})
    out.append(f"- **Audio mode:** {audio.get('mode', 'silent')}")
    if audio.get("music_prompt"):
        out.append(f"- **Music prompt:** _{audio['music_prompt']}_")
    if audio.get("music_file"):
        out.append(f"- **Music file:** `{audio['music_file']}`")
    if audio.get("vo_lines"):
        out.append("- **VO lines:**")
        for line in audio["vo_lines"]:
            out.append(f"    - \"{line}\"")

    out.append("\n## Beats\n")
    out.append("| # | Time | Duration | Beat | Caption | Visual / Action |")
    out.append("|---|---|---|---|---|---|")
    for i, beat in enumerate(sb["beats"], 1):
        start = fmt_seconds(beat["start_s"])
        dur = fmt_seconds(beat["duration_s"])
        label = beat.get("label", "")
        caption = beat.get("caption") or "_(no caption)_"
        visual = beat.get("visual", "")
        action = beat.get("action", "")
        v_a = visual + (" — " + action if action else "")
        # Escape pipes in markdown table
        for col in (caption, v_a, label):
            pass
        caption_md = caption.replace("|", "\\|")
        v_a_md = v_a.replace("|", "\\|")
        out.append(f"| {i} | {start} | {dur} | {label} | {caption_md} | {v_a_md} |")

    out.append("\n## End card\n")
    ec = sb["end_card"]
    out.append(f"- **Brand mark:** `{ec.get('brand_mark', '—')}`")
    out.append(f"- **Headline:** \"{ec['headline']}\"")
    out.append(f"- **CTA:** \"{ec['cta']}\"")
    out.append(f"- **URL:** `{ec['url']}`")
    out.append(f"- **Hold:** {ec.get('hold_s', 3.5):.1f}s")

    # Audio cue notes from beats
    audio_beats = [(b.get('label', f'Beat {i+1}'), b.get('audio_note'))
                   for i, b in enumerate(sb["beats"]) if b.get("audio_note")]
    if audio_beats:
        out.append("\n## Audio direction\n")
        for lbl, note in audio_beats:
            out.append(f"- **{lbl}:** {note}")

    out.append("\n## Pre-flight checklist\n")
    out.append("Before recording, confirm each:\n")
    for item in CHECKLIST:
        out.append(f"- [ ] {item}")

    out.append("\n## Approval\n")
    out.append("**Approver:** _________________   **Date:** _________________\n")
    out.append("**Notes:**\n")

    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("storyboard_json", help="Path to storyboard JSON")
    ap.add_argument("--out", default="-", help="Output path (or '-' for stdout)")
    args = ap.parse_args()

    sb = json.loads(Path(args.storyboard_json).read_text())
    md = render_md(sb)

    if args.out == "-":
        sys.stdout.write(md)
    else:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md)
        print(f"Wrote {out} ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
