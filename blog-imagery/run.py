#!/usr/bin/env python3
"""Blog Imagery Skill orchestrator. See SKILL.md for the contract.

Each successful generation appends a record to `sent-log.jsonl` (slug + label
+ asset path + sha256 + provider + ts). `learn.py` later detects whether
the asset has been replaced (different sha256) since the generation and
records that as a "regenerated post-imagery" signal in `corrections.md`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import re
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from image_gen import generate, GenResult  # type: ignore
from brand_palette import wrap_prompt  # type: ignore

DEFAULT_OUT_DIR = Path.home() / "zerg" / "web" / "src" / "public" / "images" / "blog"
PLAN_DIR = Path("/tmp/blog-imagery")
PLAN_DIR.mkdir(parents=True, exist_ok=True)

SKILL_DIR = Path(__file__).parent
SENT_LOG = SKILL_DIR / "sent-log.jsonl"


def sha256_file(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def append_sent_log(record: dict) -> None:
    SENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(SENT_LOG, "a") as f:
        f.write(json.dumps(record) + "\n")


def parse_blog(md_path: Path) -> dict:
    """Pull title, excerpt, and a body summary from the markdown."""
    text = md_path.read_text()
    # Strip frontmatter if present
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            body = text[end + 4:].lstrip()
    # First H1 or first non-blank line for title
    title_match = re.search(r"^# (.+)$", body, re.MULTILINE)
    title = title_match.group(1) if title_match else md_path.stem.replace("-", " ").title()
    # First paragraph for excerpt-like context
    paragraphs = [p.strip() for p in body.split("\n\n") if p.strip() and not p.startswith("#")]
    excerpt = paragraphs[0][:400] if paragraphs else ""
    return {"title": title, "excerpt": excerpt, "body": body, "path": md_path}


def derive_hero_concept(blog: dict) -> str:
    """Build the hero image concept prompt from the blog's title + opening."""
    title = blog["title"]
    excerpt = blog["excerpt"]
    # Concept is title-anchored. Body provides texture.
    return (
        f"A conceptual hero image for a research/launch blog post titled \"{title}\". "
        f"The post argues: {excerpt[:280]} "
        f"Render this as a single dominant abstract visual metaphor that captures the central idea. "
        f"Glowing geometric shapes, cosmic depth, sense of motion or distillation."
    )


def derive_body_concepts(blog: dict, count: int) -> list[tuple[str, str, str]]:
    """Return [(label, concept, type), ...] for body assets.

    Heuristic:
    - If the body mentions a competitor + the post is a launch → emit one comparison-table marker + one diagram concept.
    - If it's research → emit two diagram-concept variants (process flow + results visualization).
    - Otherwise → two distinct decorative concepts derived from H2 headers.
    """
    body = blog["body"]
    title = blog["title"].lower()
    is_launch = "launch" in title or "launching" in body.lower()[:1000]
    has_competitors = any(c in body.lower() for c in ["linear", "trello", "jira", "otter", "granola", "fireflies"])
    is_research = "paper" in body.lower()[:500] or "researchers" in body.lower()[:500]

    items: list[tuple[str, str, str]] = []

    if is_launch and has_competitors and count >= 1:
        # First body asset: comparison table (markdown, no image)
        items.append(("body-1-table", "[markdown table]", "table"))
    if is_research and count >= 1:
        # Process diagram concept
        items.append(("body-1", (
            f"A process-flow visualization for the blog post \"{blog['title']}\". "
            f"Show three stages: raw failures → distilled patterns → reusable rules. "
            f"Many small particles on the left coalescing into a few larger glowing nodes on the right. "
            f"Sense of compression, distillation, knowledge formation."), "image"))

    # Pull H2 headers as concept seeds for any remaining slots
    h2s = re.findall(r"^## (.+)$", body, re.MULTILINE)
    while len(items) < count and h2s:
        h2 = h2s.pop(0)
        idx = len(items) + 1
        items.append((f"body-{idx}", (
            f"A conceptual visual representing the section \"{h2}\" from the blog post \"{blog['title']}\". "
            f"Abstract, on-brand, no text."), "image"))

    # Filler if still under count
    while len(items) < count:
        idx = len(items) + 1
        items.append((f"body-{idx}", (
            f"A complementary conceptual image for the blog post \"{blog['title']}\". "
            f"Different focal element from the hero."), "image"))

    return items[:count]


def derive_share_concepts(blog: dict) -> dict:
    """Hero variants for Twitter (16:9) and LinkedIn (1:1 in-feed)."""
    title = blog["title"]
    excerpt = blog["excerpt"]
    return {
        "twitter": (
            f"A high-contrast Twitter share image for the post \"{title}\". "
            f"Wide 16:9 frame. The post argues: {excerpt[:200]} "
            f"Should grab attention in a fast-scrolling timeline — bold focal element, deep contrast."
        ),
        "linkedin": (
            f"A square LinkedIn in-feed image for the post \"{title}\". "
            f"Centered focal element with vertical breathing room. The post argues: {excerpt[:200]} "
            f"Square composition with high visual density (LinkedIn feed favors squares)."
        ),
    }


def build_comparison_table(blog: dict) -> str:
    """For launch posts with competitors, build a markdown comparison table.

    Heuristic: scan for known competitor names + key feature claims in the body.
    """
    title_low = blog["title"].lower()
    body_low = blog["body"].lower()

    if "zergmeeting" in title_low or "meeting" in title_low:
        return """\
| | Otter / Granola / Fireflies | ZergMeeting |
|---|---|---|
| **Captures the meeting** | ✓ | ✓ |
| **Generates transcript + notes** | ✓ | ✓ |
| **Drops action items onto your task board** | manual triage | automatic |
| **Assigns owners from speaker context** | — | ✓ |
| **Parses dates from "by Friday" → real date** | — | ✓ |
| **Links dependencies between extracted tasks** | — | ✓ |
| **Lives in the same stack as your task board** | — | ✓ (Zergboard) |

*Caption: Transcription is a commodity. The next move on a board is the bar.*
"""
    elif "zergboard" in title_low or "project boards" in title_low:
        return """\
| | Linear | Trello | Jira | **Zergboard** |
|---|---|---|---|---|
| **Has an API** | ✓ | ✓ | ✓ | ✓ |
| **Scoped tokens with limited blast radius** | partial | — | partial | ✓ |
| **Tenant-safe routes** | ✓ | partial | ✓ | ✓ |
| **Webhooks on the entry tier** | partial | enterprise | enterprise | ✓ |
| **Rate limits sized for queue-driven access** | — | — | — | ✓ |
| **Built for AI agents to use alongside humans from day one** | — | — | — | ✓ |

*Caption: Most project tools added agent features. Zergboard was built for them.*

> **TODO(matt):** before publish, replace ✓/— with real specifics where possible (Jira webhook tier price, Linear rate-limit number, etc.).
"""
    return ""


def write_plan(blog: dict, slug: str, results: dict, out_dir: Path) -> Path:
    """Write the imagery plan markdown showing where to insert each asset."""
    plan_path = PLAN_DIR / f"{slug}-imagery-plan.md"
    rel = lambda p: "/" + str(p.relative_to(out_dir.parents[1])) if p else ""
    lines = [
        f"# Imagery Plan: {blog['title']}",
        f"",
        f"**Source:** `{blog['path']}`",
        f"**Slug:** `{slug}`",
        f"**Generated:** {len([r for r in results.values() if r and r.get('success')])} of {len(results)} assets succeeded",
        f"",
        "## Files written",
        "",
    ]
    for label, r in results.items():
        if r and r.get("table"):
            lines.append(f"- ✅ **{label}** → inline markdown table (see insertion plan below)")
        elif r and r.get("success"):
            lines.append(f"- ✅ **{label}** → `{r.get('path')}` (provider: {r.get('provider', '?')})")
        else:
            err = r.get("error") if r else "skipped"
            lines.append(f"- ❌ **{label}** → {err}")

    lines += [
        "",
        "## Insertion plan (paste into the blog markdown)",
        "",
        "### Hero metadata field (`posts/<slug>.ts`)",
        "",
        "```typescript",
        f"  image: '/images/blog/{slug}-hero.png',",
        f"  ogImage: 'https://zergai.com/images/blog/{slug}-hero.png',",
        "```",
        "",
        "### After the opening paragraph (in `content/blog/<slug>.md`)",
        "",
    ]
    body_assets = [k for k in results if k.startswith("body-")]
    if body_assets:
        first = body_assets[0]
        if results[first].get("table"):
            lines.append("```markdown")
            lines.append(results[first]["table"])
            lines.append("```")
        else:
            lines.append(f"```markdown")
            lines.append(f"![{blog['title']} — concept diagram](/images/blog/{slug}-{first}.png)")
            lines.append(f"```")
    lines += [
        "",
        "### Mid-body, after the second main section",
        "",
    ]
    if len(body_assets) > 1:
        second = body_assets[1]
        if results[second].get("table"):
            lines.append("```markdown")
            lines.append(results[second]["table"])
            lines.append("```")
        else:
            lines.append(f"```markdown")
            lines.append(f"![{blog['title']} — secondary visual](/images/blog/{slug}-{second}.png)")
            lines.append(f"```")
    lines += [
        "",
        "### Social distribution",
        "",
        f"- **Twitter/X:** attach `{slug}-twitter.png` (1200×675, 16:9)",
        f"- **LinkedIn (in-feed post):** attach `{slug}-linkedin.png` (1200×1200, square — algorithmically favored over landscape)",
        f"- **LinkedIn (link share):** the OG card pulls `{slug}-hero.png` automatically",
        "",
    ]
    plan_path.write_text("\n".join(lines))
    return plan_path


def main() -> int:
    p = argparse.ArgumentParser(description="Blog Imagery Skill — full asset bundle for a blog post.")
    p.add_argument("blog_md", help="Path to blog markdown file (.md)")
    p.add_argument("--slug", help="Override slug (default: filename stem)")
    p.add_argument("--provider", default="auto", choices=["auto", "nano-banana", "fal", "pollinations"])
    p.add_argument("--skip", action="append", default=[], choices=["hero", "twitter", "linkedin", "body"])
    p.add_argument("--body-count", type=int, default=2)
    p.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    p.add_argument("--plan-only", action="store_true")
    p.add_argument("--apply", action="store_true", help="Edit blog md to insert image embeds")
    p.add_argument("--force", action="store_true", help="Overwrite existing image files")
    args = p.parse_args()

    md_path = Path(args.blog_md)
    if not md_path.exists():
        print(f"MISSING: {md_path}", file=sys.stderr)
        return 1

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    blog = parse_blog(md_path)
    slug = args.slug or md_path.stem

    print(f"\n[blog-imagery] Generating asset bundle for {slug!r}", file=sys.stderr)
    print(f"  title: {blog['title']}", file=sys.stderr)

    # Build the asset request list
    requests = []
    if "hero" not in args.skip:
        requests.append(("hero", derive_hero_concept(blog), "1.91:1"))
    shares = derive_share_concepts(blog)
    if "twitter" not in args.skip:
        requests.append(("twitter", shares["twitter"], "16:9"))
    if "linkedin" not in args.skip:
        requests.append(("linkedin", shares["linkedin"], "1:1"))
    if "body" not in args.skip:
        for label, concept, kind in derive_body_concepts(blog, args.body_count):
            if kind == "table":
                # Table assets get handled separately
                requests.append((label, "[table]", "table"))
            else:
                requests.append((label, concept, "16:9"))

    results: dict = {}
    for label, concept, aspect in requests:
        target = out_dir / f"{slug}-{label}.png"
        # Skip if exists + not forced
        if target.exists() and target.stat().st_size > 1000 and not args.force:
            print(f"  ↷ {label}: exists, skipping (use --force to overwrite)", file=sys.stderr)
            results[label] = {"success": True, "path": target, "provider": "existing"}
            continue
        if aspect == "table":
            # Build inline markdown table
            tbl = build_comparison_table(blog)
            if tbl:
                results[label] = {"success": True, "table": tbl}
                print(f"  ✓ {label}: inline markdown table", file=sys.stderr)
            else:
                results[label] = {"success": False, "error": "no table template matched"}
                print(f"  ⚠ {label}: no table template matched, skipping", file=sys.stderr)
            continue
        if args.plan_only:
            results[label] = {"success": False, "error": "skipped (plan-only)"}
            continue
        prompt = wrap_prompt(concept, aspect=aspect)
        print(f"  → {label} ({aspect}) via {args.provider}…", file=sys.stderr)
        result = generate(prompt, aspect, target, slug=slug, label=label, provider=args.provider)
        results[label] = {
            "success": result.success,
            "path": result.path,
            "provider": result.provider,
            "error": result.error,
        }
        if result.success:
            print(f"    ✓ {result.path} ({result.provider})", file=sys.stderr)
            asset_path = Path(result.path) if result.path else target
            append_sent_log({
                "ts": datetime.now().isoformat(timespec="seconds"),
                "slug": slug,
                "label": label,
                "aspect": aspect,
                "asset_path": str(asset_path),
                "asset_sha256": sha256_file(asset_path),
                "provider": result.provider,
            })
        else:
            print(f"    ✗ all providers failed: {result.error}", file=sys.stderr)

    plan_path = write_plan(blog, slug, results, out_dir)
    print(f"\n[blog-imagery] Plan written: {plan_path}", file=sys.stderr)

    n_ok = sum(1 for r in results.values() if r.get("success"))
    print(f"[blog-imagery] Done: {n_ok}/{len(results)} assets ready", file=sys.stderr)
    return 0 if n_ok == len(results) else 2


if __name__ == "__main__":
    raise SystemExit(main())
