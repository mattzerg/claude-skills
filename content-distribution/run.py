#!/usr/bin/env python3
"""Content distribution — enforces Zerg's 14-surface playbook for a published blog post.

Given a blog post file, produces:
  1. A "Distribution checklist" Markdown card with all 14 surfaces unchecked
  2. Empty variant draft files (one per surface) ready for Matt or Claude to fill
  3. UTM validation on the source post

The card refuses to close until every surface is checked.
This v0 is the file scaffolding + UTM validation. Variant generation via Claude API
is deferred to v0.1 (uses launch-announcement / fakematt-copyedit patterns).

Usage:
    python3 ~/.claude/skills/content-distribution/run.py distribute --post-file PATH \\
        [--campaign-slug SLUG] [--no-checklist]
    python3 ~/.claude/skills/content-distribution/run.py validate --post-file PATH
    python3 ~/.claude/skills/content-distribution/run.py status --post-file PATH
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

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


VAULT = _resolve_vault_root("Zerg/MattZerg")
DIST_DIR = VAULT / "Marketing" / "Distribution"

ZERG_DOMAIN_HOSTS = {"zergai.com", "www.zergai.com", "zergboard.ai", "www.zergboard.ai"}
ZERG_DOMAIN_SUFFIXES = (".zergai.com",)

SURFACES = [
    ("blog", "Blog (zergai.com) — published source post", "blog-imagery"),
    ("x-thread", "Twitter/X thread (5–7 tweets + share-card image)", "fakematt-copyedit + blog-imagery X variant"),
    ("linkedin", "LinkedIn long-form (LI-native rewrite + LI square card)", "fakematt-copyedit + blog-imagery LI variant"),
    ("idan-repost", "Idan repost (boost on LI + X)", "manual + quote-graphic"),
    ("reddit-niche", "Reddit (1–2 niche subs)", "reddit-skill"),
    ("hn", "Hacker News (Show HN if launch-quality, else organic)", "manual"),
    ("newsletter-pitches", "Newsletter inclusions (TLDR, Bytes, Console, JS Weekly, Hacker Newsletter, SaaS Weekly)", "gmail-skill outreach template"),
    ("communities", "Slack/Discord communities (where Idan/Matt have standing)", "manual"),
    ("outbound-snippet", "Outbound snippet (2-line cold-email teaser for Solutions outbound)", "gmail-skill"),
    ("sales-deck", "Sales-enablement add (slide content for Solutions discovery deck)", "gamma-skill"),
    ("internal-slack", "Internal Slack (#zerg-internal amplification ask)", "slack-skill"),
    ("zerg-newsletter", "Email newsletter (next bi-weekly Zerg broadcast)", "email-drip"),
    ("video-brief", "Repurpose-to-video brief (if signal strong)", "product-video-skill"),
    ("webinar", "Webinar topic candidate (if 800+ engagement)", "gcal-skill + gamma-skill"),
]


def slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or "post"


def find_raw_zerg_links(body: str) -> list[str]:
    """Find Zerg-domain links missing utm_source param."""
    raw: list[str] = []
    for url in re.findall(r"https?://[^\s)\"']+", body):
        host = urlparse(url).netloc.lower()
        if host in ZERG_DOMAIN_HOSTS or any(host.endswith(s) for s in ZERG_DOMAIN_SUFFIXES):
            if "utm_source=" not in url:
                raw.append(url)
    return raw


def parse_post(post_file: Path) -> tuple[str, str, str]:
    """Return (title, slug, body). Title from H1 or filename, slug from filename."""
    text = post_file.read_text()
    body = text
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end > 0:
            body = text[end + 5 :]
            fm = text[4:end]
            tm = re.search(r"^title:\s*(.+)$", fm, re.MULTILINE)
            if tm:
                title = tm.group(1).strip().strip('"').strip("'")
                slug = post_file.stem
                return title, slug, body
    h1 = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    title = h1.group(1).strip() if h1 else post_file.stem
    return title, post_file.stem, body


def cmd_distribute(args: argparse.Namespace) -> int:
    post = Path(args.post_file)
    if not post.exists():
        print(f"ERROR: post file not found: {post}", file=sys.stderr)
        return 1

    title, slug, body = parse_post(post)
    raw = find_raw_zerg_links(body)
    if raw and not args.allow_raw_links:
        print("ERROR: source post contains raw Zerg links — UTM-instrument first via utm-attribution:", file=sys.stderr)
        for u in raw:
            print(f"  {u}", file=sys.stderr)
        print("Pass --allow-raw-links to proceed anyway (NOT recommended).", file=sys.stderr)
        return 2

    out_dir = DIST_DIR / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    campaign = args.campaign_slug or f"blog-{slug}"
    today = dt.date.today().isoformat()

    # Per-surface placeholder drafts
    for sname, sdesc, stool in SURFACES:
        sf = out_dir / f"{sname}.md"
        if sf.exists():
            continue
        sf.write_text(
            f"---\n"
            f"surface: {sname}\n"
            f"post_slug: {slug}\n"
            f"campaign: {campaign}\n"
            f"utm_content: {sname}\n"
            f"status: draft\n"
            f"created: {today}\n"
            f"tool: \"{stool}\"\n"
            f"---\n\n"
            f"# {sdesc}\n\n"
            f"_(placeholder — generate via {stool}, ensure all Zerg links route through `utm-attribution` "
            f"with `utm_campaign={campaign}` and `utm_content={sname}`)_\n\n"
            f"Source post: `{post}`\n"
        )

    # Distribution checklist
    if not args.no_checklist:
        checklist_file = out_dir / "checklist.md"
        lines = [
            f"# Distribution Checklist — {title}",
            "",
            f"**Source:** `{post}`",
            f"**Slug:** `{slug}`",
            f"**Campaign:** `{campaign}`",
            f"**Created:** {today}",
            "",
            "## 14 surfaces (per content-distribution playbook)",
            "",
            "**Rule:** this card refuses to close until every checkbox is ticked.",
            "**UTM:** every external Zerg link must route through `utm-attribution` with the campaign + per-surface `utm_content`.",
            "",
        ]
        for sname, sdesc, stool in SURFACES:
            lines.append(f"- [ ] **{sname}** — {sdesc}")
            lines.append(f"  - Draft: `{(out_dir / f'{sname}.md').relative_to(VAULT)}`")
            lines.append(f"  - Tool: `{stool}`")
            lines.append("")
        lines.extend([
            "## Status legend",
            "",
            "- `[ ]` not started · `[~]` in progress · `[x]` done · `[N/A]` not applicable for this post",
            "",
            "## Voice + style",
            "",
            "- All variants must pass `fakematt-copyedit` against `MattZerg/_style/writing_style.md` voice fingerprint",
            "- Per `feedback_blog_to_social_quote_reuse.md`: verbatim blog lines in social copy max twice per thread; default is paraphrase per channel",
            "- Per `feedback_fakematt_no_double_post.md`: one Slack message per turn; never follow-up recap",
            "",
            "## Phase-2 next: auto-generation",
            "",
            "- v0.1 of this skill will call Claude (similar to `launch-announcement` scaffold mode) to populate each variant draft. Phase 1 = manual fill.",
        ])
        checklist_file.write_text("\n".join(lines) + "\n")

    print(f"Distribution scaffolded for '{title}'")
    print(f"  Slug: {slug}")
    print(f"  Campaign: {campaign}")
    print(f"  Drafts: {out_dir}")
    print(f"  Checklist: {out_dir / 'checklist.md'}")
    print(f"  Surfaces: {len(SURFACES)}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    post = Path(args.post_file)
    if not post.exists():
        print(f"ERROR: not found: {post}", file=sys.stderr)
        return 1
    text = post.read_text()
    raw = find_raw_zerg_links(text)
    if raw:
        print(f"FAIL: raw Zerg links (UTM-instrument via utm-attribution):")
        for u in raw:
            print(f"  {u}")
        return 2
    print("OK")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    post = Path(args.post_file)
    title, slug, _ = parse_post(post) if post.exists() else (post.stem, post.stem, "")
    out_dir = DIST_DIR / slug
    if not out_dir.exists():
        print(f"(no distribution scaffolded yet — run `distribute --post-file {post}`)")
        return 0
    checklist = out_dir / "checklist.md"
    if not checklist.exists():
        print(f"(scaffolded but no checklist — re-run `distribute`)")
        return 0
    txt = checklist.read_text()
    done = len(re.findall(r"^- \[x\]", txt, re.MULTILINE))
    in_progress = len(re.findall(r"^- \[~\]", txt, re.MULTILINE))
    na = len(re.findall(r"^- \[N/A\]", txt, re.MULTILINE))
    todo = len(re.findall(r"^- \[ \]", txt, re.MULTILINE))
    total = done + in_progress + na + todo
    print(f"Distribution status — {title}")
    print(f"  Done:        {done}/{total}")
    print(f"  In progress: {in_progress}/{total}")
    print(f"  N/A:         {na}/{total}")
    print(f"  TODO:        {todo}/{total}")
    print(f"  Checklist:   {checklist}")
    if todo == 0 and in_progress == 0:
        print("  ✓ All 14 surfaces complete (or N/A).")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="content-distribution", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    pd = sub.add_parser("distribute", help="scaffold the 14-surface playbook for a post")
    pd.add_argument("--post-file", dest="post_file", required=True)
    pd.add_argument("--campaign-slug", dest="campaign_slug", help="UTM campaign (default: blog-<slug>)")
    pd.add_argument("--no-checklist", action="store_true", help="skip writing the checklist file")
    pd.add_argument("--allow-raw-links", action="store_true", help="proceed even with un-instrumented links (NOT recommended)")
    pd.set_defaults(func=cmd_distribute)

    pv = sub.add_parser("validate", help="UTM-link audit for a post")
    pv.add_argument("--post-file", dest="post_file", required=True)
    pv.set_defaults(func=cmd_validate)

    ps = sub.add_parser("status", help="show checklist completion for a post")
    ps.add_argument("--post-file", dest="post_file", required=True)
    ps.set_defaults(func=cmd_status)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
