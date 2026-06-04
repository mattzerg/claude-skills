#!/Library/Developer/CommandLineTools/usr/bin/python3
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
import os
import subprocess
import sys
from pathlib import Path

SYSTEM_PYTHON = Path("/Library/Developer/CommandLineTools/usr/bin/python3")
if (
    not os.environ.get("FAKEIDAN_SYSTEM_PYTHON")
    and SYSTEM_PYTHON.exists()
    and Path(sys.executable) != SYSTEM_PYTHON
):
    os.environ["FAKEIDAN_SYSTEM_PYTHON"] = "1"
    shim = (
        "import sys; "
        "sys.argv = ['run.py', *sys.argv[1:]]; "
        f"sys.path.insert(0, {str(Path(__file__).parent)!r}); "
        "import run; "
        "raise SystemExit(run.main())"
    )
    os.execv(str(SYSTEM_PYTHON), [str(SYSTEM_PYTHON), "-c", shim, *sys.argv[1:]])
os.environ.pop("FAKEIDAN_SYSTEM_PYTHON", None)

# Reuse the existing Claude CLI subprocess wrapper from feedback-corpus.
sys.path.insert(0, str(Path.home() / ".claude" / "feedback-corpus"))
try:
    from lib.claude import call_claude  # type: ignore
except ImportError:
    print("ERROR: ~/.claude/feedback-corpus/lib/claude.py not found.", file=sys.stderr)
    sys.exit(2)


DEFAULT_MODEL = os.environ.get("FAKEIDAN_MODEL", "claude-sonnet-4-6")
_AITR_SCRIPTS = Path.home() / ".claude" / "skills" / "aitr" / "scripts"


def _routed_default_model(mode: str) -> str:
    # fakeidan is the Idan-bar review gate → high-stakes. code mode reviews code;
    # other modes review prose. FAKEIDAN_MODEL env still wins via DEFAULT_MODEL.
    if str(_AITR_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_AITR_SCRIPTS))
    try:
        from skill_default import aitr_model_or
        return aitr_model_or(
            DEFAULT_MODEL,
            task_kind="code-review" if mode == "code" else "prose-review",
            caller="fakeidan",
            quality_floor="high-stakes",
        )
    except ImportError:
        return DEFAULT_MODEL
DEFAULT_TIMEOUT = int(os.environ.get("FAKEIDAN_TIMEOUT", "360"))
QUICK_ARTIFACT_CHARS = int(os.environ.get("FAKEIDAN_QUICK_ARTIFACT_CHARS", "160000"))
DEFAULT_OUT = Path("/tmp/fakeidan")

ANCHOR_PATH = Path.home() / ".claude/skills/fakeidan/anchors/idan_review_voice.md"
MEMORY_DIR = Path.home() / ".claude/projects/-Users-mattheweisner-Library-Mobile-Documents-iCloud-md-obsidian-Documents-Zerg/memory"
PR_BAR_MEMORY = MEMORY_DIR / "feedback_idan_pr_review_bar.md"
ZERG_VOICE_MEMORY = MEMORY_DIR / "feedback_zerg_voice_no_self_deprecation.md"
BESPOKE_ENGAGEMENT_MEMORY = MEMORY_DIR / "feedback_idan_bespoke_engagement_model.md"
HONEST_SCOPING_MEMORY = MEMORY_DIR / "feedback_honest_scoping_universal.md"

# Phase 4 + 5 composites — REQUIRED for mode=code reviews. Per SKILL.md, failing
# to apply these is a HIGH-grade self-finding. Inject explicitly so the model
# can't miss them via implicit memory loading.
PHASE45_CODE_COMPOSITES = [
    ("WALKED-DIFF LEDE (opener convention)", "composite_walked_diff_lede.md"),
    ("QUICK SCORECARD (3-zone body structure)", "composite_quick_scorecard.md"),
    ("PR/SHIP GATES (ask taxonomy A*/B*/N*)", "composite_pr_and_ship_gates.md"),
    ("PRAISE PATTERN (Especially-good zone)", "composite_praise_pattern.md"),
    ("POST-MERGE FOLLOWUP (N-asks convention)", "composite_post_merge_followup.md"),
    ("ADVERSARIAL REVIEW (security sweep zone)", "composite_adversarial_review.md"),
    ("MATT PR RESPONSE FORMAT (what comes back)", "composite_matt_pr_response_format.md"),
]

PRODUCT_VIDEO_SKILL_DIR = Path.home() / ".claude/skills/product-video-skill"
VAULT_ROOT = Path(
    "/Users/mattheweisner/Library/Mobile Documents/iCloud~md~obsidian/Documents/Zerg/MattZerg"
)
ARTIFACT_QUALITY_RUBRIC = VAULT_ROOT / "_style" / "artifact_quality_rubric.md"

# Live corpora (Phase 6.A + 6.B) — Idan's real voice + concerns, refreshed by:
#   ~/.claude/skills/slack-skill/slack_corpus.py update   (daily 6:30am)
#   ~/.claude/skills/fakeidan/gh_corpus.py update         (daily 6:45am)
SLACK_CORPUS_INDEX = Path.home() / ".claude/state/slack_corpus/_index.jsonl"
GH_CORPUS_INDEX = Path.home() / ".claude/state/gh_corpus/_index.jsonl"
GH_CORPUS_DIR = Path.home() / ".claude/state/gh_corpus"
IDAN_USER_ID = "U04R0EJACMR"
IDAN_GITHUB = "idanbeck"


QUICK_ANCHORS = """# FAKE IDAN QUICK REVIEW PACK

Use this compact pack for bounded pre-flight reviews. It preserves the review bar
without loading the full long-form memory corpus.

## Mandatory Output Shape

- Start with `# Fake Idan Review: <artifact>`
- The next non-empty line must be exactly `**Verdict:** Approve`, `**Verdict:** Recommend changes`, or `**Verdict:** Changes requested`.
- Lead with architecture credits: what is solid, why it matters, and what should
  not be lost while fixing issues.
- Include a literal `## Concerns ranked` heading before the first C1/C2/S1 concern. If there are no concerns, include the heading and say "None."
- Rank concerns as C1/C2/... for code/product/spec correctness issues and
  S1/S2/... for scope/story/prose issues.
- For every concern, cite the rule it violates, the concrete evidence in the
  artifact, and the specific fix expected.
- Include `Pre-merge asks`, `Post-merge tracker`, `Verdict`, and a short
  closing paragraph addressed by name.
- Include a `## Scorecard` with total score, cap applied, dimension scores,
  top 3 score-impacting fixes, and learning tags from the artifact quality rubric.
- If there are no blocking concerns, say so directly. Do not invent blockers.

## Code / PR Review Bar

- Match shape: understand the existing local abstraction and extend it in its
  native style instead of introducing a parallel path.
- Verify then parse: check the actual data/control flow before trusting names,
  comments, or a claimed invariant.
- Preserve schema and contract invariants at boundaries. Fail closed when the
  system cannot prove the invariant.
- Watch for stale-base mistakes: two-dot vs three-dot diffs, prior review
  findings that were dropped, and hidden dependency on unrelated local changes.
- Risk-test the changed behavior, not just import success. For code touching
  deploy, auth, payments, data handling, CI, migrations, or user-visible flows,
  expect a real test/check and a rerun after fixes.
- Do not accept silent fallback behavior that hides missing credentials,
  network failures, invalid config, or partial writes.
- For automation gates, cap runtime, surface artifacts/logs, and make failure
  modes explicit enough that the next operator knows what to do.

## Prose / Product / Spec Bar

- Body must honestly support the cover claim. Remove or narrow unsupported
  promises.
- Prefer concrete observations and specific tradeoffs over generic praise.
- Keep Zerg/Matt voice direct and competent; avoid self-deprecation and
  over-explaining the process.
- Product/spec reviews should still use the code bar for data contracts,
  rollout gates, and user-impacting behavior.
"""


def compact_quick_anchor(mode: str) -> str:
    missing = []
    for label, path in (
        ("canonical voice anchor", ANCHOR_PATH),
        ("PR review bar memory", PR_BAR_MEMORY),
    ):
        if not path.exists():
            missing.append(f"- Missing {label}: {path}")

    mode_note = f"# Mode\n\nReview mode: {mode}."
    rubric = ""
    if ARTIFACT_QUALITY_RUBRIC.exists():
        rubric = "# ARTIFACT QUALITY RUBRIC\n\n" + ARTIFACT_QUALITY_RUBRIC.read_text()[:7000]
    if missing:
        parts = [QUICK_ANCHORS, mode_note, "# Missing Anchor Files\n\n" + "\n".join(missing)]
    else:
        parts = [QUICK_ANCHORS, mode_note]
    if rubric:
        parts.append(rubric)
    # Phase 4+5 — even in quick mode, mode=code MUST get the structural
    # composites. SKILL.md declares them mandatory; this is the enforcement
    # for the slim-prompt path.
    if mode == "code":
        for label, fname in PHASE45_CODE_COMPOSITES:
            path = MEMORY_DIR / fname
            if path.exists():
                parts.append(f"# {label}\n\n{path.read_text()}")
            else:
                parts.append(f"# {label} — MISSING: {path}. Flag in output as canon-incomplete self-finding.")
    return "\n\n".join(parts)


def load_live_corpus_signal(days: int = 30, max_samples: int = 8) -> str:
    """Pull recent real-Idan signal from the slack + gh corpora (Phase 6 backfill).
    Returns a compact 'freshest Idan voice' block for injection as a fakeidan anchor.

    Falls back silently when corpora aren't present (first-time install)."""
    import json
    import re
    cutoff = dt.datetime.now() - dt.timedelta(days=days)
    cutoff_iso = cutoff.isoformat()
    cutoff_unix = cutoff.timestamp()
    fake_idan = re.compile(r"\[fake idan\]", re.I)

    sections: list[str] = []

    # 1. Slack signal — recent Idan messages from the indexed corpus
    slack_quotes: list[tuple[str, str, str]] = []  # (when, channel, snippet)
    if SLACK_CORPUS_INDEX.exists():
        try:
            for line in SLACK_CORPUS_INDEX.read_text(errors="ignore").splitlines():
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r.get("user_id") != IDAN_USER_ID:
                    continue
                try:
                    ts_f = float(r.get("ts", "0"))
                except (TypeError, ValueError):
                    continue
                if ts_f < cutoff_unix:
                    continue
                snippet = r.get("snippet", "")
                if not snippet:
                    continue
                when = dt.datetime.fromtimestamp(ts_f).strftime("%Y-%m-%d")
                slack_quotes.append((when, r.get("channel", "?"), snippet))
        except OSError:
            pass

    # 2. GitHub signal — recent real-Idan PR comments (skip fake-idan paste-backs)
    gh_quotes: list[tuple[str, str, str]] = []  # (when, repo#pr, snippet)
    if GH_CORPUS_INDEX.exists():
        try:
            for line in GH_CORPUS_INDEX.read_text(errors="ignore").splitlines():
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if r.get("author") != IDAN_GITHUB:
                    continue
                ts = r.get("ts") or ""
                if ts < cutoff_iso:
                    continue
                snippet = r.get("snippet", "")
                if not snippet or fake_idan.search(snippet):
                    continue
                gh_quotes.append((ts[:10], f"{r.get('repo')}#{r.get('pr')}", snippet))
        except OSError:
            pass

    if not slack_quotes and not gh_quotes:
        return ""

    out = [f"# IDAN LIVE-CORPUS SIGNAL (last {days}d, refreshed daily)\n"]
    out.append(
        "These are REAL recent Idan utterances/comments from Slack + GitHub, "
        "auto-pulled from the local corpora. Use them to ground voice + current concerns "
        "instead of relying only on the (potentially stale) PR-bar memory.\n"
    )
    if slack_quotes:
        out.append(f"## Recent Slack ({len(slack_quotes)} msgs total, showing newest {min(len(slack_quotes), max_samples)})")
        out.append("")
        for when, ch, snippet in sorted(slack_quotes, reverse=True)[:max_samples]:
            out.append(f"- `{when}` #{ch} — {snippet}")
        out.append("")
    if gh_quotes:
        out.append(f"## Recent GitHub PR comments ({len(gh_quotes)} total, showing newest {min(len(gh_quotes), max_samples)})")
        out.append("")
        for when, ref, snippet in sorted(gh_quotes, reverse=True)[:max_samples]:
            out.append(f"- `{when}` {ref} — {snippet}")
        out.append("")
    out.append(
        "If any of the above contradicts an older pattern in `feedback_idan_pr_review_bar.md`, "
        "the live-corpus signal takes precedence — that catalog is a point-in-time snapshot."
    )
    return "\n".join(out)


def load_anchors(mode: str, quick: bool = False) -> str:
    if quick:
        return compact_quick_anchor(mode)

    parts = []
    # Live corpus signal goes FIRST so it primes the static anchors below
    live = load_live_corpus_signal()
    if live:
        parts.append(live)
    if ANCHOR_PATH.exists():
        parts.append(f"# IDAN REVIEW VOICE ANCHOR (canonical)\n\n{ANCHOR_PATH.read_text()}")
    else:
        parts.append("# IDAN REVIEW VOICE ANCHOR — MISSING. Proceed with general best practices but flag the missing anchor in the output.")

    if PR_BAR_MEMORY.exists():
        parts.append(f"# IDAN PR REVIEW BAR (memory — concrete code/architecture patterns)\n\n{PR_BAR_MEMORY.read_text()}")

    # Phase 4+5 composites — REQUIRED for mode=code. Inject EVERY one so the
    # model self-grades against them before emitting. SKILL.md declares these
    # mandatory; this is the programmatic enforcement.
    if mode == "code":
        for label, fname in PHASE45_CODE_COMPOSITES:
            path = MEMORY_DIR / fname
            if path.exists():
                parts.append(f"# {label}\n\n{path.read_text()}")
            else:
                parts.append(f"# {label} — MISSING FILE: {path}. Flag this in the review output as a self-finding (skill canon is incomplete).")

    # Voice/engagement-model anchors apply across modes — they're short and
    # always relevant when reviewing Zerg-authored or client-engagement work.
    if mode in ("prose", "spec", "product") and ZERG_VOICE_MEMORY.exists():
        parts.append(f"# ZERG VOICE — NO SELF-DEPRECATION (memory)\n\n{ZERG_VOICE_MEMORY.read_text()}")
    if mode in ("code", "spec", "product", "prose") and BESPOKE_ENGAGEMENT_MEMORY.exists():
        parts.append(f"# IDAN BESPOKE ENGAGEMENT MODEL (memory — client work, not generic SaaS)\n\n{BESPOKE_ENGAGEMENT_MEMORY.read_text()}")
    if HONEST_SCOPING_MEMORY.exists():
        parts.append(f"# HONEST SCOPING — UNIVERSAL (memory — cover-vs-body reconciliation across all genres)\n\n{HONEST_SCOPING_MEMORY.read_text()}")
    if ARTIFACT_QUALITY_RUBRIC.exists():
        parts.append(f"# ARTIFACT QUALITY RUBRIC (cross-content scorecard)\n\n{ARTIFACT_QUALITY_RUBRIC.read_text()}")

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


def truncate_artifact_text(text: str, *, label: str, quick: bool) -> str:
    if not quick or len(text) <= QUICK_ARTIFACT_CHARS:
        return text

    omitted = len(text) - QUICK_ARTIFACT_CHARS
    return (
        text[:QUICK_ARTIFACT_CHARS]
        + "\n\n"
        + f"[fakeidan quick-mode truncation: omitted {omitted} trailing chars from {label}. "
        + "If the missing tail is relevant, rerun without --quick or raise FAKEIDAN_QUICK_ARTIFACT_CHARS.]\n"
    )


SYSTEM_PROMPT_TEMPLATE = """You are Fake Idan, doing a review pass on the artifact below. Apply Idan's review patterns from the anchors. Your review must:

- Follow the **mandatory output shape** at the end of the IDAN REVIEW VOICE ANCHOR (architecture-credits-first; concerns ranked C1/C2/.../S1/S2/...; pre-merge asks numbered; post-merge tracker numbered; closing paragraph addressed by name).
- Apply **verify-then-parse** rigor: don't accept claims at face value; flag when something can't be verified from the artifact alone or the supplied context.
- Cite the **specific rule** each finding violates — name the section in the anchor or the memory rule (e.g., "feedback_idan_pr_review_bar.md item 1 'match-shape'").
- Be **structured and technical**, not Idan-voice cosplay.
- Be **honest** — if it's good, lead with what landed; if there are real concerns, rank them clearly.
- Be **scored** — include a `## Scorecard` using the artifact quality rubric: total score, cap applied, dimension scores, top 3 score-impacting fixes, and learning tags.
- The second non-empty line must be exactly `**Verdict:** Approve`, `**Verdict:** Recommend changes`, or `**Verdict:** Changes requested`. Do not replace this with a `## Verdict` section.
- Include the exact heading `## Concerns ranked`. Do not jump directly from architecture credits to `## C1`.

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
    timeout: int = DEFAULT_TIMEOUT,
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

    artifact_text = truncate_artifact_text(artifact_text, label=artifact_label, quick=quick)
    anchors = load_anchors(mode, quick=quick)
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(mode=mode)

    # Build user message
    user_message = (
        f"# Anchors\n\n{anchors}\n\n---\n\n"
        f"# Artifact under review (`{artifact_label}`, mode: `{mode}`)\n\n"
        f"```\n{artifact_text}\n```\n"
    )

    print(f"[fakeidan] reviewing {artifact_path} (mode={mode}, model={model}, timeout={timeout}s)", flush=True)
    # call_claude is a thin Claude CLI wrapper that doesn't accept a separate
    # system prompt — fold the system instructions into the prompt prefix.
    full_prompt = f"{system_prompt}\n\n---\n\n{user_message}"
    review = call_claude(prompt=full_prompt, model=model, timeout=timeout)

    today = dt.date.today().isoformat()
    out_path = out_dir / f"{artifact_path.stem}.fakeidan-{mode}.{today}.md"
    out_path.write_text(review)
    print(f"[fakeidan] wrote {out_path}", flush=True)

    # Best-effort: if the artifact maps to a tracked content slug, append the
    # findings to the per-article ledger so future sessions see prior critique
    # before re-flagging the same issues.
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path.home() / ".config" / "zerg" / "lib"))
        import article_lock as _al  # type: ignore
        slug = _al.file_path_to_slug(str(artifact_path))
        if slug:
            n = _al.ingest_review_file(out_path, slug, reviewer="idan")
            if n:
                print(f"[fakeidan] appended {n} finding(s) to feedback ledger for slug={slug}")
    except Exception as _e:  # noqa: BLE001
        print(f"[fakeidan] warn: ledger ingest failed: {_e}")

    return out_path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("artifact", nargs="+", help="Path(s) to artifact(s) to review")
    ap.add_argument("--mode", default="prose",
                    choices=["prose", "code", "video", "product", "spec"],
                    help="Review lens to apply (default: prose)")
    ap.add_argument("--out-dir", default=str(DEFAULT_OUT),
                    help=f"Output directory (default: {DEFAULT_OUT})")
    ap.add_argument("--model", default=None,
                    help=f"Claude model (default: routed via aitr; fallback {DEFAULT_MODEL})")
    ap.add_argument("--quick", action="store_true",
                    help="Skip large mode-specific catalogs to save tokens")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                    help=f"Seconds to wait for each Claude review call (default: {DEFAULT_TIMEOUT})")
    args = ap.parse_args()
    if args.model is None:
        args.model = _routed_default_model(args.mode)

    out_dir = Path(args.out_dir)
    written = []
    for art in args.artifact:
        path = Path(art).expanduser().resolve()
        out = review_artifact(
            path, mode=args.mode, out_dir=out_dir, model=args.model, quick=args.quick, timeout=args.timeout,
        )
        written.append(out)

    print(f"\n=== Done. {len(written)} review(s) written to {out_dir} ===")
    for p in written:
        print(f"  {p}")


if __name__ == "__main__":
    main()
