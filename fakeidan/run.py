#!/usr/bin/env python3
"""Fake Idan — review-voice critique skill.

Sibling to fakematt-feedback (UX) / fakematt-copyedit (prose) / fakematt-email (email).
This one applies Idan's review patterns to ANY artifact: code, prose, video shot list,
launch copy, product spec, etc.

Anchored on:
  - ~/.claude/skills/fakeidan/anchors/idan_review_voice.md (this skill's primary anchor)
  - feedback_idan_pr_review_bar.md (memory — code/PR patterns)
  - Optional mode-specific catalogs (techniques.md for video shot lists, etc.)

Usage:
    python3 ~/.claude/skills/fakeidan/run.py <artifact_path> [<more.md>...] [flags]

Flags:
    --mode MODE       prose | code | video | product | spec (default: prose)
    --out-dir DIR     where to write reviews (default: /tmp/fakeidan/)
    --model MODEL     Claude model (default: claude-opus-4-7)
    --quick           shorter review

The artifact path can be:
  - A markdown file (.md, .txt)
  - A Python/JS/TS file (.py, .js, .ts) — review treats it as code
  - A directory containing artifacts to review together (e.g. a PR diff dir)
"""
from __future__ import annotations

import argparse
import datetime as dt
import subprocess
import sys
from pathlib import Path

# Reuse the existing Claude CLI subprocess wrapper from feedback-corpus.
sys.path.insert(0, str(Path.home() / ".claude" / "feedback-corpus"))
try:
    from lib.claude import call_claude  # type: ignore
except ImportError:
    print("ERROR: ~/.claude/feedback-corpus/lib/claude.py not found.", file=sys.stderr)
    sys.exit(2)


DEFAULT_MODEL = "claude-opus-4-7"
DEFAULT_OUT = Path("/tmp/fakeidan")

ANCHOR_PATH = Path.home() / ".claude/skills/fakeidan/anchors/idan_review_voice.md"
MEMORY_DIR = Path.home() / ".claude/projects/-Users-mattheweisner-Library-Mobile-Documents-iCloud-md-obsidian-Documents-Zerg/memory"


def _resolve_pr_bar_memory() -> Path:
    """The Idan PR-bar anchor lives in the live vault _style/ folder; an older copy
    lived under the iCloud-encoded projects memory dir (retired 2026-06-24).
    Prefer the live vault path, fall back to the legacy encoded path."""
    live = Path.home() / "Obsidian" / "Zerg" / "MattZerg" / "_style" / "feedback_idan_pr_review_bar.md"
    if live.exists():
        return live
    legacy = (
        Path.home()
        / ".claude/projects/-Users-mattheweisner-Library-Mobile-Documents-iCloud-md-obsidian-Documents-Zerg/memory/feedback_idan_pr_review_bar.md"
    )
    return legacy


PR_BAR_MEMORY = _resolve_pr_bar_memory()

PRODUCT_VIDEO_SKILL_DIR = Path.home() / ".claude/skills/product-video-skill"


def load_anchors(mode: str, quick: bool = False) -> str:
    parts = []
    if ANCHOR_PATH.exists():
        parts.append(f"# IDAN REVIEW VOICE ANCHOR (canonical)\n\n{ANCHOR_PATH.read_text()}")
    else:
        parts.append("# IDAN REVIEW VOICE ANCHOR — MISSING. Proceed with general best practices but flag the missing anchor in the output.")

    if PR_BAR_MEMORY.exists():
        parts.append(f"# IDAN PR REVIEW BAR (memory — concrete code/architecture patterns)\n\n{PR_BAR_MEMORY.read_text()}")

    # Mode-specific anchors
    if mode == "video" and not quick:
        techniques = PRODUCT_VIDEO_SKILL_DIR / "techniques.md"
        density = PRODUCT_VIDEO_SKILL_DIR / "pm_tools_density.md"
        if techniques.exists():
            parts.append(f"# VIDEO TECHNIQUES CATALOG (frame-by-frame measurements)\n\n{techniques.read_text()[:18000]}")
        if density.exists():
            parts.append(f"# PM-TOOL INTERACTION DENSITY CATALOG\n\n{density.read_text()[:12000]}")

    if mode in ("prose", "video") and not quick:
        # Pull voice motion-pitfalls memory if reviewing video shot lists or prose
        pitfalls = MEMORY_DIR / "feedback_video_motion_pitfalls.md"
        workflow = MEMORY_DIR / "feedback_video_workflow.md"
        if pitfalls.exists():
            parts.append(f"# VIDEO MOTION PITFALLS (memory)\n\n{pitfalls.read_text()}")
        if workflow.exists():
            parts.append(f"# VIDEO SHOT-LIST WORKFLOW (memory)\n\n{workflow.read_text()}")

    return "\n\n---\n\n".join(parts)


SYSTEM_PROMPT_TEMPLATE = """You are Fake Idan, doing a review pass on the artifact below. Apply Idan's review patterns from the anchors. Your review must:

- Follow the **mandatory output shape** at the end of the IDAN REVIEW VOICE ANCHOR (architecture-credits-first; concerns ranked C1/C2/.../S1/S2/...; pre-merge asks numbered; post-merge tracker numbered; closing paragraph addressed by name).
- Apply **verify-then-parse** rigor: don't accept claims at face value; flag when something can't be verified from the artifact alone or the supplied context.
- Cite the **specific rule** each finding violates — name the section in the anchor or the memory rule (e.g., "feedback_idan_pr_review_bar.md item 1 'match-shape'").
- Be **structured and technical**, not Idan-voice cosplay.
- Be **honest** — if it's good, lead with what landed; if there are real concerns, rank them clearly.

Mode for this review: **{mode}**. Tune the lens accordingly:
- prose: tie-in placement, voice authenticity, concrete-claims-only, hero/visual coherence
- code: match-shape, verify-then-parse, schema invariants, money-handling delta
- video: shot-list verifies-against-product, density, branded bookends, no-mock-features-in-launch
- product: same shape as code (schema invariants, gate coverage)
- spec: same as code, plus honest-scoping in the body

Output the review in the exact mandatory shape. Do NOT wrap in a code fence. Do NOT include preamble. Start with the `# Fake Idan Review:` heading.
"""


def review_artifact(
    artifact_path: Path,
    *,
    mode: str = "prose",
    out_dir: Path = DEFAULT_OUT,
    model: str = DEFAULT_MODEL,
    quick: bool = False,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    if not artifact_path.exists():
        raise SystemExit(f"Not found: {artifact_path}")

    if artifact_path.is_dir():
        # Concatenate all .md / .txt / .py / .js / .ts files in dir
        chunks = []
        for f in sorted(artifact_path.rglob("*")):
            if f.suffix.lower() in {".md", ".txt", ".py", ".js", ".ts", ".tsx", ".jsx", ".vue"}:
                chunks.append(f"### {f.relative_to(artifact_path)}\n\n```\n{f.read_text()}\n```\n")
        artifact_text = "\n".join(chunks)
        artifact_label = f"{artifact_path.name} (directory)"
    else:
        artifact_text = artifact_path.read_text()
        artifact_label = artifact_path.name

    anchors = load_anchors(mode, quick=quick)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(mode=mode)

    # Build user message
    user_message = (
        f"# Anchors\n\n{anchors}\n\n---\n\n"
        f"# Artifact under review (`{artifact_label}`, mode: `{mode}`)\n\n"
        f"```\n{artifact_text}\n```\n"
    )

    print(f"[fakeidan] reviewing {artifact_path} (mode={mode}, model={model})")
    # call_claude is a thin Claude CLI wrapper that doesn't accept a separate
    # system prompt — fold the system instructions into the prompt prefix.
    full_prompt = f"{system_prompt}\n\n---\n\n{user_message}"
    review = call_claude(prompt=full_prompt, model=model)

    today = dt.date.today().isoformat()
    out_path = out_dir / f"{artifact_path.stem}.fakeidan-{mode}.{today}.md"
    out_path.write_text(review)
    print(f"[fakeidan] wrote {out_path}")
    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("artifact", nargs="+", help="Path(s) to artifact(s) to review")
    ap.add_argument("--mode", default="prose",
                    choices=["prose", "code", "video", "product", "spec"],
                    help="Review lens to apply (default: prose)")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT),
                    help=f"Output directory (default: {DEFAULT_OUT})")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help=f"Claude model (default: {DEFAULT_MODEL})")
    ap.add_argument("--quick", action="store_true",
                    help="Skip large mode-specific catalogs to save tokens")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    written = []
    for art in args.artifact:
        path = Path(art).expanduser().resolve()
        out = review_artifact(
            path, mode=args.mode, out_dir=out_dir, model=args.model, quick=args.quick,
        )
        written.append(out)

    print(f"\n=== Done. {len(written)} review(s) written to {out_dir} ===")
    for p in written:
        print(f"  {p}")


if __name__ == "__main__":
    main()
