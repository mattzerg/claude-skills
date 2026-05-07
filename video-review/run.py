#!/usr/bin/env python3
"""video-review — pre-flight critique for short product launch videos.

Runs auto checks (format, codec, motion jitter, music-out + logo silence,
hook timing, cut cadence, end-card hold) plus prints a 15-item human
checklist for items the algorithm can't decide. Writes a Markdown report.

Usage:
    python3 ~/.claude/skills/video-review/run.py video.mp4 [--storyboard sb.md] [--no-interactive]
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

# Make lib importable
sys.path.insert(0, str(Path(__file__).parent / "lib"))
from checks import run_all  # noqa: E402


HUMAN_CHECKLIST = [
    "Value prop visible by 0:03 (caption or branded title card).",
    "First frame interesting alone (works as autoplay-paused thumbnail).",
    "Title copy is concrete (NOT 'Watch this.' / vague meta).",
    "Captions readable on a phone (≥36px equivalent at 1080p, scrimmed).",
    "Captions sync to action within ±300ms; no caption lingers past its action.",
    "Plays meaningfully with sound off.",
    "UI fills ≥75% of frame area; no >25% empty brand-color expanses.",
    "Cursor moves smoothed; zooms held ≥1.0s on the moment.",
    "ONE mechanic per video — OR if multi-mechanic, ≥0.4 events/sec on demo content.",
    "End card has: brand mark + headline + verb-led CTA + URL + 3–6s hold.",
    "**Bookends carry brand identity** (NOT Linear-clone mono caps as title/end cards).",
    "No pricing in end card unless price IS the news.",
    "Bottom 12% of frame clear of important content (platform UI overlays).",
    "Music drops out before logo (silence on logo card).",
    "Aspect-ratio variants exist for planned channels.",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", help="Path to video file")
    ap.add_argument("--storyboard", help="Optional storyboard.md to cross-reference", default=None)
    ap.add_argument("--no-interactive", action="store_true",
                    help="Skip the human checklist (auto-only)")
    ap.add_argument("--out", default=None,
                    help="Override output report path (default: /tmp/video-review/<slug>-<ts>.md)")
    args = ap.parse_args()

    video = Path(args.video).expanduser().resolve()
    if not video.exists():
        print(f"Not found: {video}", file=sys.stderr)
        sys.exit(2)

    slug = video.stem
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = Path(args.out) if args.out else Path(f"/tmp/video-review/{slug}-{ts}.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n=== video-review: {video.name} ===\n")
    print("Running auto checks (this samples frames + scene-detects + silence-detects, ~5–15s):\n")

    results = run_all(video)

    auto_fails = []
    lines = [
        f"# Video Review: {slug}",
        "",
        f"**File:** `{video}`",
        f"**Generated:** {ts}",
        "",
        "## Auto checks",
        "",
        "| | Check | Passed | Value | Expected |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        mark = "✅" if r["passed"] else "❌"
        print(f"  {mark} {r['name']}")
        print(f"      → got: {r['value']}")
        if not r["passed"]:
            auto_fails.append(r)
        lines.append(
            f"| {mark} | {r['name']} | {'PASS' if r['passed'] else 'FAIL'} | "
            f"{r['value']} | {r['expected']} |"
        )

    # Detailed fix recipes for failures
    if auto_fails:
        lines += ["", "## Auto-check failures with fix recipes", ""]
        for f in auto_fails:
            lines += [
                f"### {f['name']}",
                "",
                f"- **Got:** {f['value']}",
                f"- **Expected:** {f['expected']}",
                f"- **Source:** {f['source']}",
                f"- **Fix:** {f.get('fix') or '(no specific fix recipe)'}",
                "",
            ]

    # Human checklist
    lines += ["", "## Human-judgment checklist", ""]
    human_fails = []
    if not args.no_interactive:
        print("\n=== Human checklist ===")
        print("Answer y/n for each. Hit q to abort and save partial report.\n")
        for i, item in enumerate(HUMAN_CHECKLIST, 1):
            while True:
                ans = input(f"  [{i:>2}] {item}\n      → [y/n/q]: ").strip().lower()
                if ans in ("y", "n", "q"):
                    break
            if ans == "q":
                lines.append("(checklist aborted)")
                break
            mark = "✅" if ans == "y" else "❌"
            lines.append(f"- {mark} {item}")
            if ans == "n":
                human_fails.append(item)
    else:
        for item in HUMAN_CHECKLIST:
            lines.append(f"- ☐ {item}")

    # Summary
    lines += ["", "## Summary", ""]
    total_auto = len(results)
    passed_auto = total_auto - len(auto_fails)
    lines.append(f"- Auto checks: {passed_auto} / {total_auto} passed")
    if not args.no_interactive:
        total_human = len(HUMAN_CHECKLIST)
        passed_human = total_human - len(human_fails)
        lines.append(f"- Human checks: {passed_human} / {total_human} confirmed")
    if auto_fails or human_fails:
        lines.append("")
        lines.append("**Recommendation:** Fix the failed items above before shipping.")
    else:
        lines.append("")
        lines.append("**Recommendation:** Cleared for ship.")

    out_path.write_text("\n".join(lines) + "\n")
    print(f"\nReport: {out_path}")

    print("\n=== Summary ===")
    print(f"  Auto: {passed_auto} / {total_auto} passed", end="")
    if not args.no_interactive:
        print(f"  |  Human: {len(HUMAN_CHECKLIST) - len(human_fails)} / {len(HUMAN_CHECKLIST)} confirmed")
    else:
        print()
    if auto_fails or (not args.no_interactive and human_fails):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
