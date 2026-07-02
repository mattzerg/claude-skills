#!/usr/bin/env python3
"""Programmatic SEO — scaffold comparison / explainer / integration pages for Zerg.

This v0 produces page skeletons with full SEO frontmatter + structural beats + sourced
claims pulled from MattZerg/Competitive/<category>/. Body content generation via
Claude API is deferred to v0.1 (reuses launch-announcement / case-study scaffold patterns).

Usage:
    python3 ~/.claude/skills/programmatic-seo/run.py comparison \\
        --competitor linear --zerg-product zergboard [--out-dir DIR]
    python3 ~/.claude/skills/programmatic-seo/run.py explainer \\
        --topic "what is agent-native project management" [--target ai-citation] [--out-dir DIR]
    python3 ~/.claude/skills/programmatic-seo/run.py integration \\
        --partner anthropic-claude-code [--out-dir DIR]
    python3 ~/.claude/skills/programmatic-seo/run.py validate <page.md>

Pairs with: blog-imagery (hero), fakematt-copyedit (voice), competitive-review-skill (sources),
content-distribution (post-publish 14-surface playbook).
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

VAULT = Path("/Users/mattheweisner/Obsidian/Zerg/MattZerg")
COMP_DIR = VAULT / "Competitive"

# Single-product content (comparison/integration pages) goes to the PRODUCT site.
# Multi-product / category / brand content (explainers) stays on zergai.
# See memory: project_zerg_content_routing.md
ZERGAI_BLOG = Path.home() / "zerg" / "web" / "src" / "public" / "content" / "blog"

MIN_WORDS = 800

# zerg-product → (repo dir name, competitive category, public domain).
# Repo dir under ~/zerg/. Domain is where the canonical URL points.
PRODUCT_INFO = {
    "zergboard":   ("zergboard",   "pm-software",                "zergboard.com"),
    "zergchat":    ("zergchat",    "internal-chat",              "zergchat.com"),
    "zergcal":     ("zergcal",     "calendar",                   "zergcal.com"),
    "zergmeeting": ("zergmeeting", "video-meetings",             "zergmeeting.com"),
    "zergmail":    ("zergmail",    "workspace-email",            "zergmail.com"),
    "zergcrm":     ("zergcrm",     "crm",                        "zergcrm.com"),
    "zergalytics": ("zergalytics", "analytics",                  "zergalytics.com"),
    "zergwallet":  ("zergwallet",  "personal-finance-managers",  "zergwallet.com"),
}

# Backward-compat alias for any caller that imported the old name.
PRODUCT_CATEGORY = {k: v[1] for k, v in PRODUCT_INFO.items()}


def product_compare_dir(product: str) -> Path:
    """Where comparison pages for <product> are written."""
    repo, _, _ = PRODUCT_INFO[product]
    return Path.home() / "zerg" / repo / "public" / "content" / "compare"


def product_integration_dir(product: str) -> Path:
    """Where integration pages for <product> are written."""
    repo, _, _ = PRODUCT_INFO[product]
    return Path.home() / "zerg" / repo / "public" / "content" / "integrations"


def product_domain(product: str) -> str:
    return PRODUCT_INFO[product][2]


def slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or "page"


def find_positioning_file(category: str) -> Path | None:
    f = COMP_DIR / category / "positioning.md"
    return f if f.exists() else None


def find_diff_file(category: str) -> Path | None:
    f = COMP_DIR / category / "differentiation-opportunities.md"
    return f if f.exists() else None


def excerpt_from(file: Path | None, max_lines: int = 30) -> str:
    if not file:
        return "(no source file found in MattZerg/Competitive/)"
    lines = file.read_text().splitlines()[:max_lines]
    return "\n".join(lines)


def write_page(path: Path, frontmatter: dict[str, str], body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fm_lines = ["---"]
    for k, v in frontmatter.items():
        if isinstance(v, list):
            fm_lines.append(f"{k}:")
            for item in v:
                fm_lines.append(f"  - {item}")
        elif any(c in str(v) for c in [":", "#"]):
            esc = str(v).replace('"', '\\"')
            fm_lines.append(f'{k}: "{esc}"')
        else:
            fm_lines.append(f"{k}: {v}")
    fm_lines.append("---")
    path.write_text("\n".join(fm_lines) + "\n\n" + body)


def cmd_comparison(args: argparse.Namespace) -> int:
    comp = args.competitor.lower().strip()
    zerg = args.zerg_product.lower().strip()
    if zerg not in PRODUCT_INFO:
        print(f"ERROR: unknown zerg-product {zerg!r}; known: {sorted(PRODUCT_INFO)}", file=sys.stderr)
        return 1
    category = PRODUCT_CATEGORY[zerg]
    pos = find_positioning_file(category)
    diff = find_diff_file(category)
    # Slug is just the competitor — context is the /compare/<slug> route on the product site.
    slug = slugify(comp)
    title = f"{comp.title()} vs {zerg.title()}"

    out_dir = Path(args.out_dir) if args.out_dir else product_compare_dir(zerg)
    out = out_dir / f"{slug}.md"

    today = dt.date.today().isoformat()
    canonical = f"https://{product_domain(zerg)}/compare/{slug}"
    meta_desc = f"{comp.title()} vs {zerg.title()}: honest tradeoffs, pricing, and a migration path. Updated {today}."

    fm = {
        "title": title,
        "slug": slug,
        "date": today,
        "canonical": canonical,
        "description": meta_desc,
        "category": "comparison",
        "tags": [comp, zerg, "comparison"],
        "type": "comparison",
        "structured_data": "Article+FAQPage",
        "image": f"/images/blog/{slug}-hero.png",
    }

    body = (
        f"# {title}\n\n"
        f"**Updated {today}** · ~12 min read · [Honest tradeoffs included]\n\n"
        f"## TL;DR\n\n"
        f"_(80–120 words. Definition-first opener — LLM-extractable. "
        f"Lead with: when does {comp} win, when does {zerg} win, who should pick which.)_\n\n"
        f"## What is {comp.title()}?\n\n"
        f"_(150–200 words. Position {comp} fairly. Pricing range. Strengths.)_\n\n"
        f"## What is {zerg.title()}?\n\n"
        f"_(150–200 words. Anchored on `MattZerg/Competitive/{category}/positioning.md` + 4 differentiation pillars: "
        f"AI-native, Zstack-interconnected, much cheaper, much easier to automate.)_\n\n"
        f"## Honest tradeoffs (not just where we win)\n\n"
        f"_(Per Idan PR-review bar — show where {comp} legitimately wins. Avoids the 'we win every dimension' "
        f"smell that kills comparison-page credibility.)_\n\n"
        f"### Where {comp.title()} wins today\n\n"
        f"- _(2–3 honest items)_\n\n"
        f"### Where {zerg.title()} wins\n\n"
        f"- _(3–5 items, sourced from `MattZerg/Competitive/{category}/differentiation-opportunities.md`)_\n\n"
        f"## Pricing comparison\n\n"
        f"| Tier | {comp.title()} | {zerg.title()} |\n"
        f"|---|---|---|\n"
        f"| Free | _(fill from competitor research)_ | Free (real, not trial) |\n"
        f"| Basic / Standard | _(fill)_ | $1/seat |\n"
        f"| Pro / Plus | _(fill)_ | $9/seat |\n"
        f"| Bundle / Enterprise | _(fill)_ | $19/seat (Zstack Bundle) or Custom |\n\n"
        f"## Migration guide\n\n"
        f"_(How to move from {comp} to {zerg}. CTA hooks here.)_\n\n"
        f"## FAQ\n\n"
        f"_(Q&A schema for AI-citation. 4–6 questions.)_\n\n"
        f"### Q: Should I pick {comp.title()} or {zerg.title()}?\n\n"
        f"_(answer ~50 words)_\n\n"
        f"### Q: Can I try {zerg.title()} for free?\n\n"
        f"_(answer ~30 words)_\n\n"
        f"## Sources\n\n"
        f"- `MattZerg/Competitive/{category}/positioning.md`\n"
        f"- `MattZerg/Competitive/{category}/differentiation-opportunities.md`\n"
        f"- {comp.title()} pricing page (verify month of access)\n\n"
        f"---\n\n"
        f"## Source-claim excerpt (delete before publish)\n\n"
        f"### `Competitive/{category}/positioning.md`\n\n"
        f"```\n{excerpt_from(pos, 20)}\n```\n\n"
        f"### `Competitive/{category}/differentiation-opportunities.md`\n\n"
        f"```\n{excerpt_from(diff, 20)}\n```\n"
    )

    write_page(out, fm, body)
    print(f"Scaffolded comparison page: {out}")
    print(f"Canonical URL: {canonical}")
    print(f"Min word target before publish: {MIN_WORDS} (current scaffold is ~250; Matt or Claude fills the gaps)")
    print(f"Next: run `fakematt-copyedit` for voice review + `blog-imagery` for hero before publish.")
    return 0


def cmd_explainer(args: argparse.Namespace) -> int:
    topic = args.topic.strip()
    slug = slugify(topic)
    out_dir = Path(args.out_dir) if args.out_dir else ZERGAI_BLOG
    out = out_dir / f"{slug}.md"
    today = dt.date.today().isoformat()
    canonical = f"https://zergai.com/blog/{slug}"
    meta_desc = f"{topic.capitalize()}: a structured definition + how it works + when to use it. Updated {today}."

    fm = {
        "title": topic.capitalize(),
        "slug": slug,
        "date": today,
        "canonical": canonical,
        "description": meta_desc,
        "category": "explainer",
        "tags": ["explainer", "geo"],
        "type": "explainer",
        "structured_data": "Article+FAQPage+DefinedTerm",
        "image": f"/images/blog/{slug}-hero.png",
        "geo_target": args.target,
    }

    body = (
        f"# {topic.capitalize()}\n\n"
        f"**Updated {today}** · ~8 min read\n\n"
        f"## In one sentence\n\n"
        f"_(≤30 words. Definition-first opener. LLM-extractable. This is the line ChatGPT / Claude / Perplexity will quote.)_\n\n"
        f"## TL;DR\n\n"
        f"_(80–120 words. Bulleted summary, LLM-extractable.)_\n\n"
        f"- Key point 1\n"
        f"- Key point 2\n"
        f"- Key point 3\n\n"
        f"## What it is\n\n"
        f"_(200–300 words. Cite sources inline, not in a footer.)_\n\n"
        f"## How it works\n\n"
        f"_(200–300 words.)_\n\n"
        f"## When to use it (and when not to)\n\n"
        f"_(150–200 words.)_\n\n"
        f"## Examples\n\n"
        f"_(2–3 concrete examples. If applicable, link to a Zerg case study.)_\n\n"
        f"## Related concepts\n\n"
        f"_(2–3 links to other Zerg explainers — internal linking signal.)_\n\n"
        f"## FAQ\n\n"
        f"_(Q&A schema for AI-citation. 4–6 questions.)_\n\n"
        f"### Q: …\n\n"
        f"_(answer ~50 words)_\n\n"
        f"## Sources\n\n"
        f"- _(cite 3–5 external authoritative sources — NN/g, Baymard, IETF, RFCs, peer-reviewed papers, etc.)_\n"
        f"- _(self-link: Zerg case studies, related Zerg explainers, Zerg product pages with UTM)_\n"
    )

    write_page(out, fm, body)
    print(f"Scaffolded explainer: {out}")
    print(f"Canonical URL: {canonical}")
    print(f"GEO target: {args.target}")
    print(f"Min word target before publish: {MIN_WORDS}")
    return 0


def cmd_integration(args: argparse.Namespace) -> int:
    partner = args.partner.lower().strip()
    zerg = (args.zerg_product or "").lower().strip() if hasattr(args, "zerg_product") else ""
    slug = slugify(partner)

    # If --zerg-product is given AND it's a known single-product integration → product site.
    # Otherwise (multi-product / brand-level integration story) → zergai blog.
    if zerg and zerg in PRODUCT_INFO:
        out_dir = Path(args.out_dir) if args.out_dir else product_integration_dir(zerg)
        canonical = f"https://{product_domain(zerg)}/integrations/{slug}"
        title = f"{partner.replace('-', ' ').title()} integration for {zerg.title()}"
    else:
        out_dir = Path(args.out_dir) if args.out_dir else ZERGAI_BLOG
        canonical = f"https://zergai.com/blog/zerg-and-{slug}"
        title = f"Zerg + {partner.replace('-', ' ').title()}: Integration Guide"
        slug = f"zerg-and-{slug}"

    out = out_dir / f"{slug}.md"
    today = dt.date.today().isoformat()

    fm = {
        "title": title,
        "slug": slug,
        "date": today,
        "canonical": canonical,
        "description": f"How Zerg + {partner.replace('-', ' ').title()} work together. Setup, examples, and what's possible.",
        "category": "integration",
        "tags": ["integration", partner],
        "type": "integration",
        "structured_data": "Article+HowTo",
        "image": f"/images/blog/{slug}-hero.png",
    }

    body = (
        f"# {title}\n\n"
        f"**Updated {today}** · ~10 min read\n\n"
        f"## TL;DR\n\n"
        f"_(80–120 words. What does the integration unlock? Who is it for?)_\n\n"
        f"## Why this integration matters\n\n"
        f"_(150–200 words.)_\n\n"
        f"## What you get\n\n"
        f"_(Bulleted list of capabilities.)_\n\n"
        f"## Setup (5 minutes)\n\n"
        f"1. Step 1\n"
        f"2. Step 2\n"
        f"3. Step 3\n\n"
        f"## Example workflows\n\n"
        f"_(2–3 worked examples — code or screenshots.)_\n\n"
        f"## FAQ\n\n"
        f"_(4–6 Q&As.)_\n\n"
        f"## Sources\n\n"
        f"- {partner.replace('-', ' ').title()} official docs\n"
        f"- Zerg integration runbook: `MattZerg/Projects/Zerg-Production/Zstack/Integration.md`\n"
    )

    write_page(out, fm, body)
    print(f"Scaffolded integration page: {out}")
    print(f"Canonical URL: {canonical}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    p = Path(args.page)
    if not p.exists():
        print(f"ERROR: not found: {p}", file=sys.stderr)
        return 1
    text = p.read_text()
    issues: list[str] = []
    body = text
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end > 0:
            fm = text[4:end]
            body = text[end + 5 :]
            for required in ("title", "slug", "canonical", "description"):
                if not re.search(rf"^{required}:\s*\S", fm, re.MULTILINE):
                    issues.append(f"frontmatter missing or empty: {required}")
    else:
        issues.append("no frontmatter")
    word_count = len(re.findall(r"\b\w+\b", body))
    if word_count < MIN_WORDS:
        issues.append(f"body word count {word_count} < min {MIN_WORDS} (will be flagged thin-content)")
    # check for placeholder markers
    placeholders = len(re.findall(r"_\(", body))
    if placeholders > 5:
        issues.append(f"{placeholders} placeholder markers — page is still scaffold, not draft")
    if issues:
        print("VALIDATION ISSUES:")
        for issue in issues:
            print(f"  - {issue}")
        return 2
    print("OK")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="programmatic-seo", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("comparison", help="scaffold a single-product '<competitor> vs <product>' page (writes to product site)")
    pc.add_argument("--competitor", required=True, help="lowercase slug, e.g. linear, slack")
    pc.add_argument("--zerg-product", dest="zerg_product", required=True,
                    help=f"one of: {sorted(PRODUCT_INFO)}")
    pc.add_argument("--out-dir", dest="out_dir", help="override output directory (default: ~/zerg/<product>/public/content/compare/)")
    pc.set_defaults(func=cmd_comparison)

    pe = sub.add_parser("explainer", help="scaffold a multi-product / category explainer (writes to zergai blog)")
    pe.add_argument("--topic", required=True, help='e.g. "what is agent-native project management"')
    pe.add_argument("--target", default="ai-citation", help="distribution target (ai-citation | organic-search)")
    pe.add_argument("--out-dir", dest="out_dir", help=f"override output directory (default: {ZERGAI_BLOG})")
    pe.set_defaults(func=cmd_explainer)

    pi = sub.add_parser("integration", help="scaffold a 'Partner integration' page (single-product → product site, multi-product → zergai)")
    pi.add_argument("--partner", required=True, help='e.g. "anthropic-claude-code", "cursor", "fly"')
    pi.add_argument("--zerg-product", dest="zerg_product", default="",
                    help=f"if set, write to that product's site. Omit for a multi-product / brand-level integration story (writes to zergai). Known: {sorted(PRODUCT_INFO)}")
    pi.add_argument("--out-dir", dest="out_dir", help="override output directory")
    pi.set_defaults(func=cmd_integration)

    pv = sub.add_parser("validate", help="check a scaffold for required frontmatter + min word count")
    pv.add_argument("page")
    pv.set_defaults(func=cmd_validate)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
