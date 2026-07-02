#!/usr/bin/env python3
"""launch-campaign — generate per-tier launch copy variants from announcement + brief.

Reads Growth/launches/<slug>.md (brief) and Growth/launches/<slug>/announcement.md
(announcement), plus this skill's channels.md, and emits a campaign.md with copy
variants for each channel tier.

Usage:
    python3 ~/.claude/skills/launch-campaign/run.py generate <slug> [--cards]
    python3 ~/.claude/skills/launch-campaign/run.py list

Exit codes: 0 ok · 1 missing announcement/brief · 2 zergboard error.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

VAULT = Path("/Users/mattheweisner/Obsidian/Zerg/MattZerg")
GROWTH = VAULT / "Projects" / "Zerg-Production" / "Growth"
LAUNCHES = GROWTH / "launches"
CHANNELS_FILE = Path(__file__).resolve().parent / "channels.md"
ZERGBOARD_CLI = Path.home() / ".claude" / "skills" / "zergboard-skill" / "zergboard_skill.py"

TIERS = [
    ("product-hunt", "Product Hunt", ["coordinated-launch-day"]),
    ("hacker-news", "Hacker News", ["coordinated-launch-day"]),
    ("ai-directories", "AI directories", ["theresanaiforthat", "futuretools", "futurepedia", "aitoolhunt", "toolify"]),
    ("saas-directories", "SaaS directories", ["betalist", "launchingnext", "alternativeto", "g2", "capterra"]),
    ("communities", "Communities", ["indiehackers", "r-saas", "r-sideproject", "r-programming", "devto", "hashnode"]),
    ("newsletters", "Newsletters", ["tldr", "tldr-ai", "pragmatic-engineer", "bytes", "bens-bites", "console-dev"]),
]


def slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or "x"


def truncate(s: str, n: int) -> str:
    s = s.strip()
    if len(s) <= n:
        return s
    cut = s[: n - 1].rsplit(" ", 1)[0]
    return cut + "…"


def strip_md(s: str) -> str:
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    s = re.sub(r"[*_`>#]", "", s)
    return s.strip()


def first_paragraph(body: str) -> str:
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    for p in paras:
        if p.lstrip().startswith("#"):
            continue
        return strip_md(re.sub(r"\s+", " ", p))
    return ""


def first_h1(body: str) -> str:
    m = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    return strip_md(m.group(1)) if m else ""


def section(body: str, header: str) -> str:
    pattern = re.compile(rf"^##+\s+{re.escape(header)}\s*$(.*?)(?=^##\s|\Z)", re.MULTILINE | re.DOTALL)
    m = pattern.search(body)
    if not m:
        return ""
    chunk = m.group(1).strip()
    bullets = [strip_md(ln.lstrip("-* ").strip()) for ln in chunk.splitlines() if ln.strip().startswith(("-", "*"))]
    if bullets:
        return " ".join(bullets)
    return strip_md(re.sub(r"\s+", " ", chunk))


def parse_brief(brief_file: Path) -> dict[str, str]:
    text = brief_file.read_text()
    body = text
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end > 0:
            body = text[end + 5 :]
    return {
        "product_name": first_h1(body).replace(" launch brief", "").strip() or brief_file.stem,
        "announcing": section(body, "What we're announcing"),
        "why_now": section(body, "Why now"),
        "proof": section(body, "Proof"),
        "pricing": section(body, "Pricing tier exposure"),
    }


def parse_announcement(ann_file: Path) -> dict[str, str]:
    text = ann_file.read_text()
    body = text
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end > 0:
            body = text[end + 5 :]
    return {
        "title": first_h1(body),
        "hook": first_paragraph(body),
        "announcing": section(body, "What we're announcing"),
        "body": body,
    }


def render_ph(ctx: dict) -> dict[str, str]:
    tagline = truncate(ctx["announcing"] or ctx["title"], 60)
    desc = truncate(
        ctx["announcing"] + " " + (ctx["hook"] or ""),
        260,
    )
    gallery = f"Hero card: {ctx['title']}. Brand colors from live site; static product screenshot + tagline overlay."
    return {"Tagline": tagline, "Description": desc, "Gallery prompt": gallery}


def render_hn(ctx: dict) -> dict[str, str]:
    title = truncate(f"Show HN: {ctx['title']}", 80)
    body = (
        f"{ctx['hook']}\n\n"
        f"{ctx['announcing']} Pricing and technical details in the post. Feedback welcome.\n\n"
        f"Link: https://{ctx['domain']}"
    )
    return {"Title": title, "Body": body}


def render_ai_dirs(ctx: dict) -> dict[str, str]:
    blurb = truncate(ctx["announcing"] or ctx["title"], 140)
    out = {}
    for d in ["There's An AI For That", "Future Tools", "Futurepedia", "AI Tool Hunt", "Toolify"]:
        out[d] = blurb
    return out


def render_saas_dirs(ctx: dict) -> dict[str, str]:
    claim = truncate(ctx["announcing"] or ctx["title"], 140)
    return {
        "BetaList": f"Category: SaaS/AI tools. Claim: {claim}",
        "Launching Next": f"Category: AI/Productivity. Claim: {claim}",
        "AlternativeTo": f"Listed as alternative to Linear/Asana/Jira/ClickUp. Claim: {claim}",
        "G2": f"Category: Project Management AI. Claim: {claim}",
        "Capterra": f"Category: Project Management. Claim: {claim}",
    }


def render_communities(ctx: dict) -> dict[str, str]:
    hook = ctx["hook"] or ctx["announcing"]
    return {
        "r/SaaS": f"Built {ctx['product_name']} for {{audience}}. {hook} Pricing + tech in the post — feedback welcome.",
        "r/SideProject": f"Launched {ctx['product_name']} this week. {hook} Happy to answer questions.",
        "IndieHackers": f"{ctx['product_name']} milestone — {ctx['announcing']} Sharing the build details below.",
        "DEV.to": f"# How we built {ctx['product_name']}\n\n{hook}\n\nDeep dive: link in post.",
    }


def render_newsletters(ctx: dict) -> dict[str, str]:
    subj = truncate(f"For consideration: {ctx['product_name']} — {ctx['announcing']}", 90)
    bullets = [
        f"- {ctx['announcing']}",
        f"- {ctx['hook']}",
        f"- Audience overlap: AI builders / engineering leads / Zerg buyers.",
    ]
    pitch = subj + "\n\n" + "\n".join(bullets) + "\n\nLink to the launch post + happy to give early access to your readers."
    out = {}
    for nl in ["TLDR", "TLDR AI", "Bytes.dev", "Pragmatic Engineer", "Ben's Bites", "Console.dev"]:
        out[nl] = pitch
    return out


def write_campaign_md(slug: str, brief: dict, ann: dict) -> Path:
    ctx = {
        "title": ann["title"] or brief["product_name"],
        "hook": ann["hook"] or brief["announcing"],
        "announcing": ann["announcing"] or brief["announcing"],
        "product_name": brief["product_name"],
        "domain": f"{slug}.zergai.com",
    }
    ph = render_ph(ctx)
    hn = render_hn(ctx)
    ai = render_ai_dirs(ctx)
    saas = render_saas_dirs(ctx)
    comm = render_communities(ctx)
    news = render_newsletters(ctx)

    lines: list[str] = []
    lines.append(f"# {ctx['product_name']} launch campaign")
    lines.append("")
    lines.append(f"Brief: [launch brief](../{slug}.md)")
    lines.append(f"Announcement: [announcement](./announcement.md)")
    lines.append("")
    lines.append("## Product Hunt")
    for k, v in ph.items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("## Hacker News")
    lines.append(f"- Title: {hn['Title']}")
    lines.append("- Body:")
    for ln in hn["Body"].splitlines():
        lines.append(f"  > {ln}")
    lines.append("")
    lines.append("## AI directories")
    for k, v in ai.items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")
    lines.append("## SaaS directories")
    for k, v in saas.items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")
    lines.append("## Communities")
    for k, v in comm.items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")
    lines.append("## Newsletters")
    for k, v in news.items():
        lines.append(f"- **{k}**:")
        for ln in v.splitlines():
            lines.append(f"  > {ln}")
    lines.append("")
    lines.append("## Cadence")
    lines.append("- T+0: PH + HN")
    lines.append("- T+1: AI dirs + community posts")
    lines.append("- T+3: newsletter pitches")
    lines.append("- T+7: SaaS dirs (after social proof accumulates)")
    lines.append("")

    out = LAUNCHES / slug / "campaign.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n")
    return out


def create_cards(slug: str) -> int:
    if not ZERGBOARD_CLI.exists():
        print(f"WARN: zergboard CLI not found at {ZERGBOARD_CLI}; skipping cards.", file=sys.stderr)
        return 0
    failures = 0
    for tier_slug, tier_label, channels in TIERS:
        for ch in channels:
            title = f"LAUNCH-{slug}-{ch}"
            try:
                result = subprocess.run(
                    [
                        sys.executable, str(ZERGBOARD_CLI), "create", "Marketing",
                        "--title", title,
                        "--description", f"Launch channel card for {slug} → {tier_label} / {ch}",
                    ],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode != 0:
                    print(f"WARN: card creation failed for {title}: {result.stderr.strip()}", file=sys.stderr)
                    failures += 1
            except (subprocess.SubprocessError, OSError) as e:
                print(f"WARN: subprocess error creating {title}: {e}", file=sys.stderr)
                failures += 1
    return failures


def cmd_generate(args: argparse.Namespace) -> int:
    slug = args.slug
    brief_file = LAUNCHES / f"{slug}.md"
    ann_file = LAUNCHES / slug / "announcement.md"

    if not brief_file.exists():
        print(f"ERROR: brief not found: {brief_file}", file=sys.stderr)
        return 1
    if not ann_file.exists():
        print(f"ERROR: announcement not found: {ann_file}", file=sys.stderr)
        return 1

    brief = parse_brief(brief_file)
    ann = parse_announcement(ann_file)
    out = write_campaign_md(slug, brief, ann)
    print(f"campaign.md written: {out}")

    if args.cards:
        failures = create_cards(slug)
        if failures:
            print(f"zergboard: {failures} card creation failure(s)", file=sys.stderr)
            return 2
        print("zergboard: cards created")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    if CHANNELS_FILE.exists():
        print(f"# Channel registry: {CHANNELS_FILE}\n")
    for tier_slug, tier_label, channels in TIERS:
        print(f"## {tier_label} ({tier_slug})")
        for ch in channels:
            print(f"  - {ch}")
        print()
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="launch-campaign", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    pg = sub.add_parser("generate", help="render campaign.md for a launch slug")
    pg.add_argument("slug")
    pg.add_argument("--cards", action="store_true", help="also create Zergboard cards per channel")
    pg.set_defaults(func=cmd_generate)

    pl = sub.add_parser("list", help="print channel tiers + slots for inspection")
    pl.set_defaults(func=cmd_list)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
