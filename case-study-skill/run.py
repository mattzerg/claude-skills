#!/usr/bin/env python3
"""Case-study skill — capture, scaffold, or review Zerg client case studies.

Usage:
    python3 ~/.claude/skills/case-study-skill/run.py capture  <client> [--project SLUG] [--kind delivery|advisory] [flags]
    python3 ~/.claude/skills/case-study-skill/run.py scaffold <brief-path> [--cleared-for-publication] [flags]
    python3 ~/.claude/skills/case-study-skill/run.py review   <draft.md> [<more.md>...] [flags]

Capture flags:
    --project SLUG    optional project slug; auto-derived from client+kind otherwise
    --kind X          delivery (default) | advisory
    --out-dir DIR     where to write the brief (default: skill state/briefs/)
    --model MODEL     Claude model id (default: routed via aitr; fallback claude-opus-4-8)
    --no-pdf          skip PDF + Preview open

Scaffold flags:
    --cleared-for-publication   override nda_status:unknown; refused for nda_status:restricted
    --out-dir DIR     where to write drafts (default: vault MattZerg/CaseStudies/<client>/)
    --model MODEL     Claude model id (default: routed via aitr; fallback claude-opus-4-8)
    --length WORDS    target word count (default: 1500; band 1,200-2,000)
    --no-pdf          skip PDF + Preview open

Review flags:
    --out-dir DIR     where to write reviews (default: /tmp/case-study/)
    --model MODEL     Claude model id (default: routed via aitr; fallback claude-opus-4-8)
    --no-pdf          skip PDF conversion + Preview open
    --quick           drop the full corpus from anchors (style guide only)
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
import time
from pathlib import Path

# Reuse the Claude CLI subprocess wrapper from the feedback corpus.
sys.path.insert(0, str(Path.home() / ".claude" / "feedback-corpus"))
from lib.claude import call_claude  # type: ignore

# Skill-local imports. Use a distinct package name so it doesn't shadow feedback-corpus/lib.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cs_helpers.sources import gather_evidence, slugify  # type: ignore

# Fallback when aitr (the internal model router) is unavailable. Explicit --model
# always wins; otherwise the model is routed per-run (draft-prose / high-stakes).
DEFAULT_MODEL = "claude-opus-4-8"

_AITR_SCRIPTS = Path.home() / ".claude" / "skills" / "aitr" / "scripts"


def _routed_default_model() -> str:
    if str(_AITR_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_AITR_SCRIPTS))
    try:
        from skill_default import aitr_model_or
        return aitr_model_or(
            DEFAULT_MODEL,
            task_kind="draft-prose",
            caller="case-study-skill",
            quality_floor="high-stakes",
        )
    except ImportError:
        return DEFAULT_MODEL
SKILL_ROOT = Path(__file__).resolve().parent
PROMPTS_DIR = SKILL_ROOT / "prompts"
CORPUS_FILE = SKILL_ROOT / "corpus" / "case-study-corpus.md"
STATE_DIR = SKILL_ROOT / "state"
BRIEFS_DIR = STATE_DIR / "briefs"

VAULT_ROOT = Path(
    "/Users/mattheweisner/Obsidian/Zerg/MattZerg"
)
GENRE_GUIDE = VAULT_ROOT / "_style" / "case_study_style.md"
WRITING_STYLE = VAULT_ROOT / "_style" / "writing_style.md"
CASESTUDIES_ROOT = VAULT_ROOT / "Clients"  # client-first home since 2026-06-10; drafts go to Clients/<client-slug>/case-study/
DEFAULT_REVIEW_OUT = Path("/tmp/case-study")
PDF_SCRIPT = Path("/tmp/md_to_pdf.py")


# ---------- anchors ----------

def load_anchors(quick: bool = False) -> str:
    parts = []
    if GENRE_GUIDE.exists():
        parts.append(f"# CASE STUDY GENRE GUIDE (canonical)\n\n{GENRE_GUIDE.read_text()}")
    else:
        parts.append("# CASE STUDY GENRE GUIDE — MISSING (proceed with general best practices).")

    if WRITING_STYLE.exists():
        parts.append(f"# WRITING STYLE GUIDE (sentence-level — for context, copyedit-skill is primary)\n\n{WRITING_STYLE.read_text()}")

    if not quick and CORPUS_FILE.exists():
        parts.append(f"# 12-EXEMPLAR CORPUS (per-entry analysis — ground truth for exemplar references)\n\n{CORPUS_FILE.read_text()}")
    elif quick:
        parts.append("# 12-EXEMPLAR CORPUS — skipped (--quick). Cite style guide rules; skip exemplar names beyond what's in the guide.")

    return "\n\n---\n\n".join(parts)


# ---------- capture ----------

def load_capture_prompt() -> str:
    return (PROMPTS_DIR / "capture.md").read_text()


CAPTURE_TEMPLATE = """{system}

{anchors}

---

# RAW EVIDENCE GATHERED FROM THE VAULT

The following snippets were pulled by `lib.sources.gather_evidence` from a deterministic search across the vault. Each is tagged with its source path and a weight (HIGH/MEDIUM). Trackers (Linear, Zergboard) were NOT queried by the script — note any gaps that a tracker query could close in the brief's `gaps` section.

```
{evidence}
```

# REQUEST PARAMETERS

- client: {client}
- project_slug: {project_slug}
- kind: {kind}
- today: {today}

---

# YOUR TASK

Produce the full brief per the format above. Begin output with the `---` frontmatter line. No preamble. No "Here is the brief" framing.
"""


def capture_one(client: str, project_slug: str, kind: str, anchors: str, model: str) -> tuple[str, dict]:
    evidence_blob, evidence_meta = gather_evidence(client, vault_root=VAULT_ROOT)
    prompt = CAPTURE_TEMPLATE.format(
        system=load_capture_prompt(),
        anchors=anchors,
        evidence=evidence_blob,
        client=client,
        project_slug=project_slug,
        kind=kind,
        today=dt.date.today().isoformat(),
    )
    return call_claude(prompt, model=model, timeout=600), evidence_meta


def write_brief(out_dir: Path, client: str, project_slug: str, brief_md: str, evidence_meta: dict) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{slugify(client)}-{project_slug}.brief.md"
    path.write_text(brief_md)
    return path


# ---------- scaffold ----------

def load_scaffold_prompt() -> str:
    return (PROMPTS_DIR / "scaffold.md").read_text()


SCAFFOLD_TEMPLATE = """{system}

{anchors}

---

# CAPTURED BRIEF

The following brief was produced by `case-study-skill capture` and is the ONLY source of truth for evidence. Every metric, name, and quote in your draft must trace back to a citation in this brief. If a claim cannot be cited, drop it — do not invent.

```
{brief}
```

# PARAMETERS

- target_word_count: {length}
- nda_status: {nda_status}
- nda_override: {nda_override}
- today: {today}

---

# YOUR TASK

Produce the full case study draft per the format above. Begin output with the `---` frontmatter line. No preamble. No "Here is the draft" framing.
"""


_NDA_FRONTMATTER_RE = re.compile(r"^nda_status:\s*([A-Za-z_-]+)\s*$", re.MULTILINE)


def parse_nda_status(brief_text: str) -> str:
    m = _NDA_FRONTMATTER_RE.search(brief_text)
    if not m:
        return "unknown"
    return m.group(1).strip().lower()


def scaffold_one(brief_path: Path, anchors: str, model: str, length: int, override: bool) -> tuple[str, str, str]:
    brief_text = brief_path.read_text()
    nda = parse_nda_status(brief_text)
    if nda == "restricted":
        raise SystemExit(
            f"REFUSED: brief at {brief_path} is marked nda_status: restricted. "
            "Scaffold cannot run. Flip the brief frontmatter manually only after legal/client clearance."
        )
    if nda == "unknown" and not override:
        raise SystemExit(
            f"REFUSED: brief at {brief_path} is nda_status: unknown. "
            "Re-run with --cleared-for-publication if you have explicit clearance, or set nda_status: cleared in the brief."
        )
    nda_override_str = "false"
    if override and nda != "cleared":
        nda_override_str = f"true (override applied at {dt.datetime.now().isoformat(timespec='seconds')})"
    prompt = SCAFFOLD_TEMPLATE.format(
        system=load_scaffold_prompt(),
        anchors=anchors,
        brief=brief_text,
        length=length,
        nda_status=nda,
        nda_override=nda_override_str,
        today=dt.date.today().isoformat(),
    )
    md = call_claude(prompt, model=model, timeout=600)
    return md, nda, nda_override_str


def derive_paths_from_brief(brief_path: Path) -> tuple[str, str]:
    """Recover (client_slug, project_slug) from `<client>-<project>.brief.md`."""
    stem = brief_path.stem
    if stem.endswith(".brief"):
        stem = stem[: -len(".brief")]
    if "-" in stem:
        # crude split — first hyphen group is client, remainder is project
        # (briefs created by this skill use slugify(client) so client slugs have no hyphens internally)
        client_slug, project_slug = stem.split("-", 1)
    else:
        client_slug, project_slug = stem, "engagement"
    return client_slug, project_slug


def _client_dir(client_slug: str) -> Path:
    """Match an existing Clients/<Name>/ folder case-insensitively (folders use display
    names like CesiumAstro; slugs are lowercase); fall back to the slug itself."""
    if CASESTUDIES_ROOT.exists():
        for d in CASESTUDIES_ROOT.iterdir():
            if d.is_dir() and d.name.lower().replace("-", "") == client_slug.lower().replace("-", ""):
                return d
    return CASESTUDIES_ROOT / client_slug


def write_scaffold(client_slug: str, project_slug: str, draft_md: str, out_dir_override: Path | None) -> tuple[Path, Path]:
    out_dir = out_dir_override if out_dir_override else _client_dir(client_slug) / "case-study"
    out_dir.mkdir(parents=True, exist_ok=True)
    draft_path = out_dir / f"{project_slug}.md"
    draft_path.write_text(draft_md)

    checklist = (
        f"# Pre-publish checklist: {client_slug} / {project_slug}\n\n"
        f"**Source draft:** {draft_path}\n"
        f"**Anchors:** case_study_style.md\n\n"
        "Tick each box before the case study ships externally:\n\n"
        "- [ ] Every numeric claim cites a path/URL in the source brief\n"
        "- [ ] Every named person attested in vault (`People/<name>.md` or evidence link)\n"
        "- [ ] Every quote string-matches `candidate_quotes` in the brief verbatim\n"
        "- [ ] Every product/feature claimed corresponds to a Product Glossary entry or shipped Linear issue\n"
        "- [ ] NDA cleared in writing by client (and `nda_status: cleared` in frontmatter)\n"
        "- [ ] Client logo permission on file\n"
        "- [ ] Linear / Zergboard / GitHub URLs scrubbed of internal-only IDs\n"
        "- [ ] Frontmatter complete (client, sector, products_used, outcomes, status, nda_status)\n"
        "- [ ] Linked from `Companies/<client>.md`\n"
        "- [ ] Idan signoff before any external send\n"
        "\n## Next steps\n\n"
        "1. Fill in any `[BRACKETED]` placeholders in the draft.\n"
        "2. Run `case-study-skill review` on the filled draft to verify anti-fabrication gates.\n"
        "3. Run `fakematt-copyedit` on the filled draft for sentence-level voice.\n"
        "4. Send to client for quote verification and publication clearance.\n"
        "5. After client signoff, copy draft into `~/zerg/web/` per the blog publishing workflow in `MattZerg/CLAUDE.md`.\n"
    )
    checklist_path = out_dir / f"{project_slug}.checklist.md"
    checklist_path.write_text(checklist)
    return draft_path, checklist_path


# ---------- review ----------

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

Produce the full review per the format above. Begin output with the `# Case Study Review:` header. No preamble. No "Here is the review" framing.
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


# ---------- shared ----------

def write_session_summary(out_dir: Path, mode: str, results: list[dict], model: str, started: float) -> Path:
    duration = time.time() - started
    today = dt.date.today().isoformat()
    lines = [
        f"# Case Study — session summary ({mode})",
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
        elif mode == "scaffold":
            lines.append(f"### {r['client_slug']} / {r['project_slug']}")
            lines.append(f"- Brief: `{r['brief']}`")
            lines.append(f"- Draft: `{r['draft']}`")
            lines.append(f"- Checklist: `{r['checklist']}`")
            lines.append(f"- NDA status at scaffold: `{r['nda_status']}`")
            lines.append(f"- NDA override: `{r['nda_override']}`")
        else:  # capture
            lines.append(f"### {r['client']} ({r['kind']})")
            lines.append(f"- Brief: `{r['brief']}`")
            lines.append(f"- Evidence sources scanned: {r['sources_scanned']}")
            lines.append(f"- Snippets gathered: {r['snippets']}")
        lines.append("")
    summary = out_dir / "session-summary.md"
    summary.write_text("\n".join(lines))
    return summary


def maybe_pdf_and_open(files: list[Path], open_files: bool) -> None:
    """Default: do nothing. Caller must opt-in via --open. Per Matt: review,
    interview, and session-summary files are read by Claude, not opened in
    Preview — they clutter the screen and stack duplicate windows."""
    if not open_files:
        return
    if not PDF_SCRIPT.exists():
        subprocess.run(["open"] + [str(f) for f in files])
        return
    subprocess.run(["python3", str(PDF_SCRIPT)] + [str(f) for f in files])


# ---------- CLI ----------

def cmd_capture(args) -> int:
    out_dir = Path(args.out_dir) if args.out_dir else BRIEFS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    project_slug = args.project or f"{args.kind}-engagement"
    anchors = load_anchors(quick=False)
    print(f"[case-study capture] {args.client} ({args.kind}) → project={project_slug}", file=sys.stderr)
    brief_md, evidence_meta = capture_one(args.client, project_slug, args.kind, anchors, args.model)
    brief_path = write_brief(out_dir, args.client, project_slug, brief_md, evidence_meta)
    print(f"  → {brief_path}", file=sys.stderr)
    summary = write_session_summary(
        out_dir, "capture",
        [{
            "client": args.client,
            "kind": args.kind,
            "brief": brief_path,
            "sources_scanned": evidence_meta.get("sources_scanned", 0),
            "snippets": evidence_meta.get("snippets", 0),
        }],
        args.model, started,
    )
    print(f"\n[case-study] summary: {summary}", file=sys.stderr)
    maybe_pdf_and_open([summary, brief_path], args.open)
    return 0


def cmd_scaffold(args) -> int:
    started = time.time()
    brief_path = Path(args.brief).expanduser()
    if not brief_path.exists():
        print(f"MISSING brief: {brief_path}", file=sys.stderr)
        return 1
    if args.length < 600 or args.length > 3000:
        print(f"WARNING: --length {args.length} is outside 600-3000 band; clamping", file=sys.stderr)
        args.length = max(600, min(3000, args.length))
    anchors = load_anchors(quick=False)
    print(f"[case-study scaffold] {brief_path.name}…", file=sys.stderr)
    draft_md, nda_status, nda_override = scaffold_one(brief_path, anchors, args.model, args.length, args.cleared_for_publication)
    client_slug, project_slug = derive_paths_from_brief(brief_path)
    out_dir_override = Path(args.out_dir) if args.out_dir else None
    draft_path, checklist_path = write_scaffold(client_slug, project_slug, draft_md, out_dir_override)
    print(f"  → {draft_path}", file=sys.stderr)
    print(f"  → {checklist_path}", file=sys.stderr)
    print(f"  nda_status at scaffold: {nda_status}; override: {nda_override}", file=sys.stderr)
    summary_dir = draft_path.parent
    summary = write_session_summary(
        summary_dir, "scaffold",
        [{
            "client_slug": client_slug,
            "project_slug": project_slug,
            "brief": brief_path,
            "draft": draft_path,
            "checklist": checklist_path,
            "nda_status": nda_status,
            "nda_override": nda_override,
        }],
        args.model, started,
    )
    print(f"\n[case-study] summary: {summary}", file=sys.stderr)
    maybe_pdf_and_open([summary, draft_path, checklist_path], args.open)
    return 0


def cmd_render(args) -> int:
    """Delegate to render.py — marketing-grade PDF rendering with brand styling."""
    draft = Path(args.draft).expanduser()
    if not draft.exists():
        print(f"MISSING draft: {draft}", file=sys.stderr)
        return 1
    cmd = ["python3", str(SKILL_ROOT / "render.py"), str(draft)]
    if args.draft_watermark:
        cmd.append("--draft")
    if args.no_open:
        cmd.append("--no-open")
    if args.version:
        cmd.extend(["--version", args.version])
    return subprocess.run(cmd).returncode


def cmd_review(args) -> int:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    anchors = load_anchors(quick=args.quick)
    results = []
    for raw in args.drafts:
        path = Path(raw)
        if not path.exists():
            print(f"MISSING: {path}", file=sys.stderr)
            continue
        print(f"[case-study review] {path.name}…", file=sys.stderr)
        review_md = review_one(path, anchors, args.model)
        review_path, interview_path = write_review(out_dir, path, review_md)
        results.append({"draft": path, "review": review_path, "interview": interview_path})
        print(f"  → {review_path}", file=sys.stderr)
        if interview_path:
            print(f"  → {interview_path}  (LOW-confidence items)", file=sys.stderr)
    if not results:
        print("No reviews produced.", file=sys.stderr)
        return 1
    summary = write_session_summary(out_dir, "review", results, args.model, started)
    print(f"\n[case-study] summary: {summary}", file=sys.stderr)
    files: list[Path] = [summary]
    for r in results:
        files.append(r["review"])
        if r.get("interview"):
            files.append(r["interview"])
    maybe_pdf_and_open(files, args.open)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Case study skill — capture, scaffold, or review Zerg client case studies.")
    sub = p.add_subparsers(dest="mode", required=True)

    c = sub.add_parser("capture", help="Pull raw evidence into a structured brief")
    c.add_argument("client")
    c.add_argument("--project", default=None)
    c.add_argument("--kind", default="delivery", choices=["delivery", "advisory"])
    c.add_argument("--out-dir", default=None)
    c.add_argument("--model", default=None)
    c.add_argument("--no-pdf", action="store_true", help="Deprecated; default is no-open. Kept for backward compat.")
    c.add_argument("--open", action="store_true", help="Open session-summary + brief in Preview/default app (off by default).")
    c.set_defaults(fn=cmd_capture)

    s = sub.add_parser("scaffold", help="Generate a draft case study from a brief")
    s.add_argument("brief")
    s.add_argument("--cleared-for-publication", action="store_true")
    s.add_argument("--out-dir", default=None)
    s.add_argument("--model", default=None)
    s.add_argument("--length", type=int, default=1500)
    s.add_argument("--no-pdf", action="store_true", help="Deprecated; default is no-open. Kept for backward compat.")
    s.add_argument("--open", action="store_true", help="Open session-summary + draft + checklist in Preview/default app (off by default).")
    s.set_defaults(fn=cmd_scaffold)

    r = sub.add_parser("review", help="Audit one or more existing drafts")
    r.add_argument("drafts", nargs="+")
    r.add_argument("--out-dir", default=str(DEFAULT_REVIEW_OUT))
    r.add_argument("--model", default=None)
    r.add_argument("--no-pdf", action="store_true", help="Deprecated; default is no-open. Kept for backward compat.")
    r.add_argument("--open", action="store_true", help="Open session-summary + review.md + interview.md in Preview/default app (off by default — Matt does NOT want these auto-opened).")
    r.add_argument("--quick", action="store_true")
    r.set_defaults(fn=cmd_review)

    rd = sub.add_parser("render", help="Render a marketing-grade PDF from a draft + sidecar meta.json")
    rd.add_argument("draft")
    rd.add_argument("--draft", dest="draft_watermark", action="store_true",
                    help="Add 'DRAFT — internal review' watermark banner")
    rd.add_argument("--no-open", action="store_true",
                    help="Do not open the rendered PDF in Preview (use during iteration)")
    rd.add_argument("--version", default=None, help="Manual version label (default: auto-bumped)")
    rd.set_defaults(fn=cmd_render)

    args = p.parse_args()
    # Explicit --model wins; otherwise route via aitr (loud fallback to DEFAULT_MODEL).
    if getattr(args, "model", None) is None and hasattr(args, "model"):
        args.model = _routed_default_model()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
