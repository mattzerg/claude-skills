#!/usr/bin/env python3
"""One-pager skill — scaffold or review single-page collateral against a 10-doc corpus.

Variants:
    company     — multi-use leave-behind (RELAYTO/Hoy Health hybrid)
    consulting  — services prospects (Algorand/Pento/Quit Genius brief shape)
    product     — product prospects (Hoy Health B2C / Joi / Intercept shape)

Usage:
    python3 ~/.claude/skills/one-pager-skill/run.py scaffold <variant> "<brief>" [flags]
    python3 ~/.claude/skills/one-pager-skill/run.py review <draft.md> [<more.md>...] [flags]
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

# Fallback when aitr is unavailable; explicit --model wins, else routed per-run.
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
            caller="one-pager-skill",
            quality_floor="high-stakes",
        )
    except ImportError:
        return DEFAULT_MODEL
DEFAULT_OUT = Path("/tmp/one-pager")
SKILL_ROOT = Path.home() / ".claude" / "skills" / "one-pager-skill"
PROMPTS_DIR = SKILL_ROOT / "prompts"
CORPUS_FILE = SKILL_ROOT / "corpus" / "one-pager-corpus.md"
TEMPLATES_DIR = SKILL_ROOT / "templates"

VAULT_ROOT = Path(
    "/Users/mattheweisner/Obsidian/Zerg/MattZerg"
)
GENRE_GUIDE = VAULT_ROOT / "_style" / "one_pager_style.md"
WRITING_STYLE = VAULT_ROOT / "_style" / "writing_style.md"
PDF_SCRIPT = SKILL_ROOT / "render_pdf.py"
FALLBACK_PDF_SCRIPT = Path("/tmp/md_to_pdf.py")

VARIANTS = ("company", "consulting", "product")

VARIANT_VAULT_DIR = {
    "company": VAULT_ROOT / "Zerg",
    "consulting": VAULT_ROOT / "Consulting",
    "product": VAULT_ROOT / "Projects" / "Zerg-Production" / "Zstack",
}

VARIANT_DEFAULT_AUDIENCE = {
    "company": "enterprise-sales",
    "consulting": "services-prospect",
    "product": "product-prospect",
}

VARIANT_DEFAULT_CTA = {
    "company": "contact",
    "consulting": "book-call",
    "product": "try",
}

VARIANT_POSITIONING_DOCS = {
    "company": [VAULT_ROOT / "Zerg" / "positioning.md"],
    "consulting": [VAULT_ROOT / "Consulting" / "positioning.md"],
    "product": [
        VAULT_ROOT / "Projects" / "Zerg-Production" / "Zstack" / "Zstack.md",
        VAULT_ROOT / "Projects" / "Zerg-Production" / "Zstack" / "Pricing-Snapshot.md",
        VAULT_ROOT / "Projects" / "Zerg-Production" / "Zstack" / "Integration.md",
    ],
}


def load_anchors(variant: str | None, quick: bool = False) -> str:
    parts = []
    if GENRE_GUIDE.exists():
        parts.append(f"# ONE-PAGER GENRE GUIDE (canonical)\n\n{GENRE_GUIDE.read_text()}")
    else:
        parts.append("# ONE-PAGER GENRE GUIDE — MISSING (proceed with general best practices).")

    if WRITING_STYLE.exists():
        parts.append(
            "# WRITING STYLE GUIDE (sentence-level — for context, copyedit-skill is primary)\n\n"
            + WRITING_STYLE.read_text()
        )

    if not quick and CORPUS_FILE.exists():
        parts.append(
            "# 10-DOC CORPUS (per-doc analysis + synthesis — ground truth for exemplar references)\n\n"
            + CORPUS_FILE.read_text()
        )
    elif quick:
        parts.append(
            "# 10-DOC CORPUS — skipped (--quick). Cite genre guide rules; skip exemplar names beyond what's in the guide."
        )

    if variant and variant in VARIANT_POSITIONING_DOCS:
        positioning_loaded = []
        for doc in VARIANT_POSITIONING_DOCS[variant]:
            if doc.exists():
                positioning_loaded.append(f"## {doc.name}\n\n{doc.read_text()}")
        if positioning_loaded:
            parts.append(
                f"# VARIANT POSITIONING — {variant} (load-bearing facts; do not contradict)\n\n"
                + "\n\n---\n\n".join(positioning_loaded)
            )

    return "\n\n---\n\n".join(parts)


def load_template(variant: str) -> str:
    path = TEMPLATES_DIR / f"{variant}.md.tmpl"
    if not path.exists():
        return ""
    return path.read_text()


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

Produce the full review per the format above. Begin output with the `# One-Pager Review:` header. No preamble. No "Here is the review" framing.
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

# VARIANT TEMPLATE (use as the structural skeleton — fill in placeholders, keep beat names)

```markdown
{template}
```

---

# BRIEF

{brief}

# PARAMETERS

- variant: {variant}
- target_word_count: {length}
- audience: {audience}
- cta: {cta}
- slug: {slug}
- today: {today}

---

# YOUR TASK

Produce the full one-pager scaffold per the format above. Begin output with the `---` frontmatter line. No preamble. No "Here is the scaffold" framing. The output must fit one printed page at 11pt body with 0.75in margins (~{length} words is the budget).
"""


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:60] or "one-pager").rstrip("-")


def scaffold_one(
    variant: str,
    brief: str,
    anchors: str,
    template: str,
    model: str,
    length: int,
    audience: str,
    cta: str,
    slug: str,
) -> str:
    prompt = SCAFFOLD_TEMPLATE.format(
        system=load_scaffold_prompt(),
        anchors=anchors,
        template=template,
        brief=brief,
        variant=variant,
        length=length,
        audience=audience,
        cta=cta,
        slug=slug,
        today=dt.date.today().isoformat(),
    )
    return call_claude(prompt, model=model, timeout=600)


def write_scaffold(
    out_dir: Path, slug: str, variant: str, scaffold_md: str
) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    draft_path = out_dir / f"{slug}.one-pager.md"
    draft_path.write_text(scaffold_md)

    checklist = (
        f"# Pre-publish checklist: {slug} ({variant} one-pager)\n\n"
        f"**Source draft:** {draft_path}\n"
        f"**Anchors:** one_pager_style.md\n\n"
        "Tick each box before the one-pager ships:\n\n"
        "- [ ] Fits on one printed page at 11pt body / 0.75in margins (render and check)\n"
        "- [ ] Strongest specific number / proof appears in the top third\n"
        "- [ ] Headline is a complete claim, not a category label\n"
        "- [ ] No buzzwords (revolutionary, game-changing, cutting-edge, transformative, etc.)\n"
        "- [ ] Single primary CTA with a real link / contact\n"
        "- [ ] At least one named entity (client, integration, partner, person)\n"
        "- [ ] Differentiation paragraph or section is present (why us, not what we do)\n"
        "- [ ] Pricing or engagement-model line is present (or explicit \"contact for pricing\" with reason)\n"
        "- [ ] Skim test: a reader scanning only headers + bolded text understands the offer\n"
        "- [ ] No \"excited to announce\" / \"thrilled\" / \"transformative journey\"\n"
        "\n## Next steps\n\n"
        "1. Fill in `[BRACKETED]` placeholders and resolve any `[CONFIRM]` tags from positioning.\n"
        "2. Run `fakematt-copyedit` on the filled draft for sentence-level voice.\n"
        "3. Re-run `one-pager-skill review` after the first fill to validate the structure.\n"
        "4. Render PDF; visually confirm it fits one page.\n"
        "5. Upload final PDF to Drive (vault is source-of-truth, Drive is distribution).\n"
    )
    checklist_path = out_dir / f"{slug}.checklist.md"
    checklist_path.write_text(checklist)
    return draft_path, checklist_path


# ---------- shared ----------

def write_session_summary(
    out_dir: Path, mode: str, results: list[dict], model: str, started: float
) -> Path:
    duration = time.time() - started
    today = dt.date.today().isoformat()
    lines = [
        f"# One-Pager — session summary ({mode})",
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
            lines.append(f"### {r['slug']} ({r['variant']})")
            lines.append(f"- Brief: {r['brief'][:100]}")
            lines.append(f"- Draft: `{r['draft']}`")
            lines.append(f"- Checklist: `{r['checklist']}`")
        lines.append("")
    summary = out_dir / "session-summary.md"
    summary.write_text("\n".join(lines))
    return summary


def maybe_pdf_and_open(files: list[Path], no_pdf: bool) -> None:
    if no_pdf:
        return
    # Prefer the one-pager-tuned renderer (tighter CSS, vault-side output).
    # Only call it on the actual one-pager drafts; checklists/summaries get the generic renderer.
    one_pager_drafts = [f for f in files if f.name.endswith(".one-pager.md")]
    other_files = [f for f in files if not f.name.endswith(".one-pager.md")]

    if PDF_SCRIPT.exists() and one_pager_drafts:
        subprocess.run(["python3", str(PDF_SCRIPT)] + [str(f) for f in one_pager_drafts])
    if other_files:
        if FALLBACK_PDF_SCRIPT.exists():
            subprocess.run(["python3", str(FALLBACK_PDF_SCRIPT)] + [str(f) for f in other_files])
        else:
            subprocess.run(["open"] + [str(f) for f in other_files])


def resolve_out_dir(args, variant: str | None) -> Path:
    if getattr(args, "vault_dir", None):
        return Path(args.vault_dir)
    if getattr(args, "vault", False) and variant:
        return VARIANT_VAULT_DIR[variant]
    return Path(args.out_dir)


# ---------- CLI ----------

def cmd_review(args) -> int:
    out_dir = resolve_out_dir(args, variant=None)
    out_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    anchors = load_anchors(variant=None, quick=args.quick)
    results = []
    for raw in args.drafts:
        path = Path(raw)
        if not path.exists():
            print(f"MISSING: {path}", file=sys.stderr)
            continue
        print(f"[one-pager review] {path.name}…", file=sys.stderr)
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
    print(f"\n[one-pager] summary: {summary}", file=sys.stderr)
    files: list[Path] = [summary]
    for r in results:
        files.append(r["review"])
        if r.get("interview"):
            files.append(r["interview"])
    maybe_pdf_and_open(files, args.no_pdf)
    return 0


def cmd_scaffold(args) -> int:
    if args.variant not in VARIANTS:
        print(f"ERROR: variant must be one of {VARIANTS}", file=sys.stderr)
        return 2
    if args.length < 250 or args.length > 550:
        print(
            f"WARNING: --length {args.length} outside 250-550 band; clamping",
            file=sys.stderr,
        )
        args.length = max(250, min(550, args.length))

    audience = args.audience or VARIANT_DEFAULT_AUDIENCE[args.variant]
    cta = args.cta or VARIANT_DEFAULT_CTA[args.variant]
    slug = args.slug or slugify(args.brief.split("—")[0].split(":")[0].strip() or args.brief)

    out_dir = resolve_out_dir(args, variant=args.variant)
    out_dir.mkdir(parents=True, exist_ok=True)

    started = time.time()
    anchors = load_anchors(variant=args.variant, quick=False)
    template = load_template(args.variant)

    print(
        f"[one-pager scaffold {args.variant}] slug={slug} → {out_dir}",
        file=sys.stderr,
    )
    md = scaffold_one(
        variant=args.variant,
        brief=args.brief,
        anchors=anchors,
        template=template,
        model=args.model,
        length=args.length,
        audience=audience,
        cta=cta,
        slug=slug,
    )
    draft_path, checklist_path = write_scaffold(out_dir, slug, args.variant, md)
    print(f"  → {draft_path}", file=sys.stderr)
    print(f"  → {checklist_path}", file=sys.stderr)

    summary = write_session_summary(
        out_dir,
        "scaffold",
        [
            {
                "brief": args.brief,
                "variant": args.variant,
                "slug": slug,
                "draft": draft_path,
                "checklist": checklist_path,
            }
        ],
        args.model,
        started,
    )
    print(f"\n[one-pager] summary: {summary}", file=sys.stderr)
    maybe_pdf_and_open([summary, draft_path, checklist_path], args.no_pdf)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(
        description="One-pager skill — scaffold or review single-page collateral."
    )
    sub = p.add_subparsers(dest="mode", required=True)

    r = sub.add_parser("review", help="Audit one or more existing drafts")
    r.add_argument("drafts", nargs="+")
    r.add_argument("--out-dir", default=str(DEFAULT_OUT))
    r.add_argument("--model", default=None)
    r.add_argument("--no-pdf", action="store_true")
    r.add_argument("--quick", action="store_true")
    r.set_defaults(fn=cmd_review)

    s = sub.add_parser(
        "scaffold", help="Generate a one-pager skeleton from a brief"
    )
    s.add_argument("variant", choices=VARIANTS)
    s.add_argument("brief")
    s.add_argument("--out-dir", default=str(DEFAULT_OUT))
    s.add_argument("--vault", action="store_true", help="write to vault destination per variant")
    s.add_argument("--vault-dir", default=None, help="explicit vault destination override")
    s.add_argument("--slug", default=None)
    s.add_argument("--model", default=None)
    s.add_argument("--length", type=int, default=380)
    s.add_argument(
        "--audience",
        default=None,
        choices=[
            "enterprise-sales",
            "reseller-enablement",
            "services-prospect",
            "product-prospect",
            "network-leave-behind",
            "investor",
        ],
    )
    s.add_argument(
        "--cta",
        default=None,
        choices=["try", "contact", "book-call", "docs", "none"],
    )
    s.add_argument("--no-pdf", action="store_true")
    s.set_defaults(fn=cmd_scaffold)

    args = p.parse_args()
    if getattr(args, "model", None) is None and hasattr(args, "model"):
        args.model = _routed_default_model()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
