#!/usr/bin/env python3
"""Launch-announcement skill — review or scaffold launch posts against the 15-post corpus.

Usage:
    python3 ~/.claude/skills/launch-announcement/run.py review   <draft.md> [<more.md>...] [flags]
    python3 ~/.claude/skills/launch-announcement/run.py scaffold "<product brief>" [flags]

Review flags:
    --out-dir DIR     where to write reviews (default: /tmp/launch-announcement/)
    --model MODEL     Claude model id (default: claude-opus-4-7)
    --no-pdf          skip PDF conversion + Preview open
    --quick           drop the full corpus from anchors (style guide only)

Scaffold flags:
    --out-dir DIR     where to write scaffolds (default: /tmp/launch-announcement/)
    --model MODEL     Claude model id (default: claude-opus-4-7)
    --length WORDS    target word count (default: 1500)
    --audience X      infra-engineer (default) | designer | fintech-buyer | general-tech
    --cta X           try (default) | waitlist | docs | sales | none
    --companion       also emit a companion technical-post outline
    --no-pdf          skip PDF + Preview open
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".claude" / "feedback-corpus"))
from lib.claude import call_claude  # type: ignore

DEFAULT_MODEL = "claude-opus-4-7"
DEFAULT_OUT = Path("/tmp/launch-announcement")
SKILL_ROOT = Path.home() / ".claude" / "skills" / "launch-announcement"
PROMPTS_DIR = SKILL_ROOT / "prompts"
CORPUS_FILE = SKILL_ROOT / "corpus" / "launch-announcement-corpus.md"

def _resolve_vault_root(sub: str = "Zerg/MattZerg") -> Path:
    """Live vault is ~/Obsidian/<sub>; the iCloud path was retired 2026-06-24.
    Prefer the live path, fall back to the legacy iCloud path only if it still exists."""
    primary = Path.home() / "Obsidian" / sub
    if primary.exists():
        return primary
    legacy = (
        Path.home()
        / "Library" / "Mobile Documents" / "iCloud~md~obsidian" / "Documents" / sub
    )
    return legacy if legacy.exists() else primary


VAULT_ROOT = _resolve_vault_root("Zerg/MattZerg")
GENRE_GUIDE = VAULT_ROOT / "_style" / "launch_announcement_style.md"
if not GENRE_GUIDE.exists():
    GENRE_GUIDE = VAULT_ROOT / "launch_announcement_style.md"  # legacy fallback
WRITING_STYLE = VAULT_ROOT / "_style" / "writing_style.md"
if not WRITING_STYLE.exists():
    WRITING_STYLE = VAULT_ROOT / "writing_style.md"  # legacy fallback
VOICE_UNIVERSALS = VAULT_ROOT / "_style" / "voice_universals.md"
LEARNED_PATTERNS = VAULT_ROOT / "_style" / "learned_patterns.md"
LAUNCH_CORRECTIONS = Path(__file__).parent / "corrections.md"
PDF_SCRIPT = Path("/tmp/md_to_pdf.py")


def load_anchors(quick: bool = False) -> str:
    parts = []
    if VOICE_UNIVERSALS.exists():
        parts.append(f"# VOICE UNIVERSALS (cross-surface — applies always)\n\n{VOICE_UNIVERSALS.read_text()}")
    if LEARNED_PATTERNS.exists() and LEARNED_PATTERNS.stat().st_size > 200:
        parts.append(f"# LEARNED PATTERNS (auto-promoted from Matt's edits)\n\n{LEARNED_PATTERNS.read_text()}")
    if LAUNCH_CORRECTIONS.exists() and LAUNCH_CORRECTIONS.stat().st_size > 0:
        parts.append(f"# LAUNCH-ANNOUNCEMENT CORRECTIONS (recent diffs)\n\n{LAUNCH_CORRECTIONS.read_text()}")
    if GENRE_GUIDE.exists():
        parts.append(f"# LAUNCH ANNOUNCEMENT GENRE GUIDE (canonical)\n\n{GENRE_GUIDE.read_text()}")
    else:
        parts.append("# LAUNCH ANNOUNCEMENT GENRE GUIDE — MISSING (proceed with general best practices).")

    if WRITING_STYLE.exists():
        parts.append(f"# WRITING STYLE GUIDE (sentence-level — for context, copyedit-skill is primary)\n\n{WRITING_STYLE.read_text()}")

    if not quick and CORPUS_FILE.exists():
        parts.append(f"# 15-POST CORPUS (per-post analysis + synthesis — ground truth for exemplar references)\n\n{CORPUS_FILE.read_text()}")
    elif quick:
        parts.append("# 15-POST CORPUS — skipped (--quick). Cite genre guide rules; skip exemplar names beyond what's in the guide.")

    return "\n\n---\n\n".join(parts)


# ---------- review mode ----------

def load_review_prompt() -> str:
    return (PROMPTS_DIR / "review.md").read_text()


REVIEW_TEMPLATE = """{system}

{anchors}

---

# DRAFT TO REVIEW

**File:** {path}

```markdown
{content}
```

---

# YOUR TASK

Produce the full review per the format above. Begin output with the `# Launch Announcement Review:` header. No preamble. No "Here is the review" framing.
"""


def review_one(path: Path, anchors: str, model: str) -> str:
    content = path.read_text()
    prompt = REVIEW_TEMPLATE.format(
        system=load_review_prompt(),
        anchors=anchors,
        path=path,
        content=content,
    )
    return call_claude(prompt, model=model, timeout=600)


def write_review(out_dir: Path, draft_path: Path, review_md: str) -> tuple[Path, Path | None]:
    out_dir.mkdir(parents=True, exist_ok=True)
    base = draft_path.stem.replace(" ", "_")
    review_path = out_dir / f"{base}.review.md"
    review_path.write_text(review_md)

    interview_path: Path | None = None
    marker = "## Interview queue"
    if marker in review_md:
        body_after = review_md.split(marker, 1)[1].lstrip("\n")
        if "No interview items" not in body_after[:200]:
            interview_path = out_dir / f"{base}.interview.md"
            interview_path.write_text(
                f"# Interview queue: {draft_path.stem}\n\n"
                f"**Source review:** {review_path}\n"
                f"**Source draft:** {draft_path}\n\n"
                f"---\n\n{marker}{body_after}"
            )
    return review_path, interview_path


# ---------- scaffold mode ----------

def load_scaffold_prompt() -> str:
    return (PROMPTS_DIR / "scaffold.md").read_text()


SCAFFOLD_TEMPLATE = """{system}

{anchors}

---

# PRODUCT BRIEF

{brief}

# PARAMETERS

- target_word_count: {length}
- audience: {audience}
- cta: {cta}
- companion_post: {companion}
- today: {today}

---

# YOUR TASK

Produce the full scaffold per the format above. Begin output with the `---` frontmatter line. No preamble. No "Here is the scaffold" framing.
"""


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:60] or "launch-draft").rstrip("-")


def scaffold_one(brief: str, anchors: str, model: str, length: int, audience: str, cta: str, companion: bool) -> str:
    prompt = SCAFFOLD_TEMPLATE.format(
        system=load_scaffold_prompt(),
        anchors=anchors,
        brief=brief,
        length=length,
        audience=audience,
        cta=cta,
        companion=str(companion).lower(),
        today=dt.date.today().isoformat(),
    )
    return call_claude(prompt, model=model, timeout=600)


def write_scaffold(out_dir: Path, brief: str, scaffold_md: str) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(brief.split("—")[0].split(":")[0].strip() or brief)
    draft_path = out_dir / f"{slug}.draft.md"
    draft_path.write_text(scaffold_md)

    checklist = (
        f"# Pre-publish checklist: {slug}\n\n"
        f"**Source draft:** {draft_path}\n"
        f"**Anchors:** launch_announcement_style.md\n\n"
        "Tick each box before the launch ships:\n\n"
        "- [ ] Para 1 contains news + concrete number/comparator\n"
        "- [ ] Headline contains no buzzword (revolutionary, game-changing, cutting-edge, etc.)\n"
        "- [ ] 3–5 capability subsections, each with concrete proof\n"
        "- [ ] Single primary CTA (plus optional recruiting)\n"
        "- [ ] Strongest specific number lands in first 25%\n"
        "- [ ] Customer mentions inlined as names, not quote boxes\n"
        "- [ ] \"What's next\" names dates/quarters (or section is cut)\n"
        "- [ ] Word count in 1,200–1,800 band (or justified)\n"
        "- [ ] Companion technical post planned if architecture is interesting\n"
        "- [ ] No \"excited to announce\" / \"thrilled\" / \"revolutionize\" / \"cutting-edge\"\n"
        "\n## Next steps\n\n"
        "1. Fill in `[BRACKETED]` placeholders in the draft.\n"
        f"2. Run `fakematt-copyedit` on the filled draft for sentence-level voice.\n"
        f"3. Re-run `launch-announcement review` after the first fill to validate the structure.\n"
        f"4. Generate hero + social variants with `blog-imagery`.\n"
    )
    checklist_path = out_dir / f"{slug}.checklist.md"
    checklist_path.write_text(checklist)
    return draft_path, checklist_path


# ---------- shared ----------

def write_session_summary(out_dir: Path, mode: str, results: list[dict], model: str, started: float) -> Path:
    duration = time.time() - started
    today = dt.date.today().isoformat()
    lines = [
        f"# Launch Announcement — session summary ({mode})",
        "",
        f"**Date:** {today}",
        f"**Mode:** {mode}",
        f"**Model:** {model}",
        f"**Duration:** {duration:.1f}s",
        f"**Items:** {len(results)}",
        "",
        "## Files",
        "",
    ]
    for r in results:
        if mode == "review":
            lines.append(f"### {r['draft'].name}")
            lines.append(f"- Source: `{r['draft']}`")
            lines.append(f"- Review: `{r['review']}`")
            if r.get("interview"):
                lines.append(f"- Interview queue: `{r['interview']}`  ⚠️ has discussion items")
            else:
                lines.append("- Interview queue: none (all findings HIGH/MEDIUM)")
        else:  # scaffold
            lines.append(f"### {r['brief'][:80]}")
            lines.append(f"- Draft: `{r['draft']}`")
            lines.append(f"- Checklist: `{r['checklist']}`")
        lines.append("")
    summary = out_dir / "session-summary.md"
    summary.write_text("\n".join(lines))
    return summary


def maybe_pdf_and_open(files: list[Path], no_pdf: bool) -> None:
    if no_pdf:
        return
    if not PDF_SCRIPT.exists():
        subprocess.run(["open"] + [str(f) for f in files])
        return
    subprocess.run(["python3", str(PDF_SCRIPT)] + [str(f) for f in files])


# ---------- CLI ----------

def cmd_review(args) -> int:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    anchors = load_anchors(quick=args.quick)
    results = []
    sent_log = Path(__file__).parent / "sent-log.jsonl"
    for raw in args.drafts:
        path = Path(raw)
        if not path.exists():
            print(f"MISSING: {path}", file=sys.stderr)
            continue
        print(f"[launch-announcement review] {path.name}…", file=sys.stderr)
        # Snapshot input content BEFORE review for the learning loop
        try:
            input_content = path.read_text()
        except Exception:
            input_content = ""
        review_md = review_one(path, anchors, args.model)
        review_path, interview_path = write_review(out_dir, path, review_md)
        results.append({"draft": path, "review": review_path, "interview": interview_path})
        print(f"  → {review_path}", file=sys.stderr)
        if interview_path:
            print(f"  → {interview_path}  (LOW-confidence items)", file=sys.stderr)
        # Log for learn.py — track if Matt edits the input draft after seeing the review
        try:
            import json as _json
            with open(sent_log, "a") as f:
                f.write(_json.dumps({
                    "ts": dt.datetime.now().strftime("%Y%m%dT%H%M%S"),
                    "input_path": str(path.resolve()),
                    "input_content_at_review": input_content,
                    "review_path": str(review_path),
                    "model": args.model,
                    "checked": False,
                }) + "\n")
        except Exception as e:
            print(f"[sent-log] {e}", file=sys.stderr)
    if not results:
        print("No reviews produced.", file=sys.stderr)
        return 1
    summary = write_session_summary(out_dir, "review", results, args.model, started)
    print(f"\n[launch-announcement] summary: {summary}", file=sys.stderr)
    files: list[Path] = [summary]
    for r in results:
        files.append(r["review"])
        if r.get("interview"):
            files.append(r["interview"])
    maybe_pdf_and_open(files, args.no_pdf)
    return 0


def cmd_scaffold(args) -> int:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    if args.length < 600 or args.length > 3000:
        print(f"WARNING: --length {args.length} is outside 600-3000 band; clamping at boundary", file=sys.stderr)
        args.length = max(600, min(3000, args.length))
    anchors = load_anchors(quick=False)  # scaffold always uses full corpus
    print(f"[launch-announcement scaffold] {args.brief[:80]}…", file=sys.stderr)
    md = scaffold_one(args.brief, anchors, args.model, args.length, args.audience, args.cta, args.companion)
    draft_path, checklist_path = write_scaffold(out_dir, args.brief, md)
    print(f"  → {draft_path}", file=sys.stderr)
    print(f"  → {checklist_path}", file=sys.stderr)
    summary = write_session_summary(
        out_dir, "scaffold",
        [{"brief": args.brief, "draft": draft_path, "checklist": checklist_path}],
        args.model, started,
    )
    print(f"\n[launch-announcement] summary: {summary}", file=sys.stderr)
    maybe_pdf_and_open([summary, draft_path, checklist_path], args.no_pdf)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Launch announcement skill — review or scaffold launch posts.")
    sub = p.add_subparsers(dest="mode", required=True)

    r = sub.add_parser("review", help="Audit one or more existing drafts")
    r.add_argument("drafts", nargs="+")
    r.add_argument("--out-dir", default=str(DEFAULT_OUT))
    r.add_argument("--model", default=DEFAULT_MODEL)
    r.add_argument("--no-pdf", action="store_true")
    r.add_argument("--quick", action="store_true")
    r.set_defaults(fn=cmd_review)

    s = sub.add_parser("scaffold", help="Generate a draft skeleton from a product brief")
    s.add_argument("brief")
    s.add_argument("--out-dir", default=str(DEFAULT_OUT))
    s.add_argument("--model", default=DEFAULT_MODEL)
    s.add_argument("--length", type=int, default=1500)
    s.add_argument("--audience", default="infra-engineer", choices=["infra-engineer", "designer", "fintech-buyer", "general-tech"])
    s.add_argument("--cta", default="try", choices=["try", "waitlist", "docs", "sales", "none"])
    s.add_argument("--companion", action="store_true")
    s.add_argument("--no-pdf", action="store_true")
    s.set_defaults(fn=cmd_scaffold)

    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
