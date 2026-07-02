#!/usr/bin/env python3
"""content-distribution — 17-surface fanout for a Zerg launch.

Reads Growth/launches/<slug>/announcement.md (source), Growth/launches/<slug>.md
(brief), and Growth/measurement/<slug>.yaml (utm_allowlist). Emits
Growth/launches/<slug>/distribution.md — a 17-surface checklist with per-surface
copy and UTM-tagged links.

Surface canonical list aligned with MattZerg/_style/launch_distribution_playbook.md
(17 surfaces post-2026-05-27 Gigacontext post-mortem).

Usage:
    python3 ~/.claude/skills/content-distribution/run.py generate <slug> [--cards]
    python3 ~/.claude/skills/content-distribution/run.py cards <slug>
    python3 ~/.claude/skills/content-distribution/run.py list

Exit codes: 0 ok · 1 missing announcement/brief · 2 zergboard error · 3 UTM allowlist violation.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlencode

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None

VAULT = Path("/Users/mattheweisner/Obsidian/Zerg/MattZerg")
GROWTH = VAULT / "Projects" / "Zerg-Production" / "Growth"
LAUNCHES = GROWTH / "launches"
MEASUREMENT = GROWTH / "measurement"
UTM_CLI = Path.home() / ".claude" / "skills" / "utm-attribution" / "run.py"
ZERGBOARD_CLI = Path.home() / ".claude" / "skills" / "zergboard-skill" / "zergboard_skill.py"

SURFACES = [
    ("twitter", "Twitter/X thread", "social"),
    ("linkedin", "LinkedIn long-form", "social"),
    ("linkedin-company", "LinkedIn company page repost", "social"),
    ("reddit", "Reddit (per-sub variants)", "community"),
    ("hn", "Hacker News (Show HN)", "community"),
    ("producthunt", "Product Hunt", "community"),
    ("instagram", "Instagram", "social"),
    ("youtube", "YouTube (short)", "social"),
    ("threads", "Threads", "social"),
    ("bluesky", "Bluesky", "social"),
    ("mastodon", "Mastodon", "social"),
    ("discord", "Discord (per-community)", "community"),
    ("slack-communities", "Slack communities", "community"),
    ("email-newsletter", "Email newsletter (broadcast)", "email"),
    ("blog", "Blog post (zergai.com or product blog)", "organic"),
    ("docs-banner", "Webflow / docs banner", "organic"),
    ("changelog", "Changelog entry", "organic"),
]


def slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s or "post"


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


def first_h1(body: str) -> str:
    m = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    return strip_md(m.group(1)) if m else ""


def first_paragraph(body: str) -> str:
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    for p in paras:
        if p.lstrip().startswith("#"):
            continue
        return strip_md(re.sub(r"\s+", " ", p))
    return ""


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


def parse_markdown(path: Path) -> dict[str, str]:
    text = path.read_text()
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


def load_utm_allowlist(slug: str) -> dict:
    spec = MEASUREMENT / f"{slug}.yaml"
    if not spec.exists() or yaml is None:
        return {}
    try:
        data = yaml.safe_load(spec.read_text()) or {}
    except Exception:
        return {}
    return data.get("utm_allowlist", {}) or {}


def check_utm_against_allowlist(allowlist: dict, source: str, medium: str, campaign: str) -> list[str]:
    if not allowlist:
        return []
    errors: list[str] = []
    src_list = allowlist.get("utm_source") or []
    med_list = allowlist.get("utm_medium") or []
    prefix = allowlist.get("utm_campaign_prefix")
    if src_list and source not in src_list and not any(s.replace("{slug}", "") in source for s in src_list if "{" in s):
        errors.append(f"utm_source={source!r} not in allowlist {src_list}")
    if med_list and medium not in med_list:
        errors.append(f"utm_medium={medium!r} not in allowlist {med_list}")
    if prefix and not campaign.startswith(prefix):
        errors.append(f"utm_campaign={campaign!r} must start with {prefix!r}")
    return errors


def build_utm_link(base: str, source: str, medium: str, campaign: str) -> str:
    if UTM_CLI.exists():
        try:
            result = subprocess.run(
                [
                    sys.executable, str(UTM_CLI), "build",
                    "--destination", base,
                    "--source", source,
                    "--medium", medium,
                    "--campaign", campaign,
                    "--register-campaign",
                    "--no-log",
                ],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                line = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
                if line.startswith("http"):
                    return line
        except (subprocess.SubprocessError, OSError) as e:
            print(f"WARN: utm-attribution subprocess failed ({e}); falling back to inline build", file=sys.stderr)
    params = {"utm_source": source, "utm_medium": medium, "utm_campaign": campaign}
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}{urlencode(params)}"


def render_surface_copy(surface: str, ctx: dict) -> str:
    title = ctx["title"] or ctx["product_name"]
    hook = ctx["hook"] or ctx["announcing"]
    announcing = ctx["announcing"] or hook

    if surface == "twitter":
        body = truncate(f"{title}. {hook}", 220)
        return body + " " + ctx["link"]
    if surface == "linkedin":
        return (
            f"{title}\n\n"
            f"{hook}\n\n"
            f"{announcing}\n\n"
            f"Details: {ctx['link']}"
        )
    if surface == "linkedin-company":
        return f"Repost: {title}\n\n{truncate(hook, 200)}\n\n{ctx['link']}"
    if surface == "reddit":
        return (
            f"[fill from announcement, no marketing tone]\n\n"
            f"Title candidate: {title}\n"
            f"Body candidate: {hook}\n"
            f"Per-sub variants required (r/SaaS, r/SideProject, r/programming, r/AI_Agents).\n"
            f"Link (only after the body is community-native): {ctx['link']}"
        )
    if surface == "hn":
        return (
            f"Title: Show HN: {truncate(title, 60)}\n"
            f"Body:\n"
            f"- {hook}\n"
            f"- {announcing}\n"
            f"- Pricing + technical notes in the post; feedback welcome.\n"
            f"Link: {ctx['link']}"
        )
    if surface == "producthunt":
        return (
            f"Tagline: {truncate(announcing or title, 60)}\n"
            f"Description: {truncate(hook + ' ' + announcing, 260)}\n"
            f"Link: {ctx['link']}"
        )
    if surface == "instagram":
        return f"{truncate(title + '. ' + hook, 180)} (link in bio)"
    if surface == "youtube":
        return (
            f"Title: {truncate(title, 70)}\n"
            f"Description: {hook} See the full breakdown: {ctx['link']}\n"
            f"(See product-video-skill for the demo cut.)"
        )
    if surface in ("threads", "bluesky", "mastodon"):
        signoff = {"threads": "(Threads cross-post)", "bluesky": "(Bluesky cross-post)", "mastodon": "(Mastodon cross-post)"}[surface]
        body = truncate(f"{title}. {hook}", 240)
        return f"{body} {ctx['link']} {signoff}"
    if surface == "discord":
        return f"{truncate(title, 80)} — {truncate(hook, 220)}\n{ctx['link']}"
    if surface == "slack-communities":
        return f"{truncate(title, 80)} — {truncate(hook, 220)}\n{ctx['link']}"
    if surface == "email-newsletter":
        return (
            f"Subject: {truncate(title, 80)}\n\n"
            f"{hook}\n\n"
            f"{announcing}\n\n"
            f"CTA: {ctx['link']}"
        )
    if surface == "blog":
        return f"Live post: {ctx['link']}"
    if surface == "docs-banner":
        return f"{truncate(announcing or title, 90)} — {ctx['link']}"
    if surface == "changelog":
        return f"- Launched {ctx['product_name']} — {truncate(announcing or hook, 140)} — {ctx['link']}"
    return f"{title}\n{hook}\n{ctx['link']}"


def render_distribution_md(slug: str, ctx: dict, links: dict[str, str]) -> str:
    lines: list[str] = []
    lines.append(f"# {ctx['product_name']} distribution")
    lines.append("")
    lines.append(f"Brief: [launch brief](../{slug}.md)")
    lines.append(f"Announcement: [announcement](./announcement.md)")
    lines.append(f"Campaign slug: `{slug}-launch-T0`")
    lines.append("")
    lines.append("## 17-surface checklist")
    lines.append("")
    lines.append("**Rule:** this checklist refuses to close until every surface is marked complete.")
    lines.append("")
    for surface, label, medium in SURFACES:
        copy = render_surface_copy(surface, {**ctx, "link": links[surface]})
        lines.append(f"## {label}")
        lines.append(f"- Status: `[ ]`")
        lines.append(f"- Owner: Matt")
        lines.append(f"- Surface: `{surface}` · Medium: `{medium}`")
        lines.append(f"- UTM link: {links[surface]}")
        lines.append("- Copy:")
        for ln in copy.splitlines():
            lines.append(f"  > {ln}")
        lines.append("")
    lines.append("## Cadence (per launch_distribution_playbook.md)")
    lines.append("- T+0: publish + fire surfaces 1-7 + DMs to quoted people")
    lines.append("- T+0 +4h: check Day-1 engagement; if LinkedIn ≥10 reactions → trigger Day-2 quote-post wave")
    lines.append("- T+1: pull Zerglytics + X + LI metrics; quote-post wave fires")
    lines.append("- T+3: 72h analytics pull; HN / Reddit / niche-community drop decision")
    lines.append("- T+7: 7-day analytics pull; post-mortem if flagship")
    lines.append("- T+30: evergreen variants if top-5 referral driver")
    return "\n".join(lines) + "\n"


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

    brief = parse_markdown(brief_file)
    ann = parse_markdown(ann_file)
    ctx = {
        "title": ann["title"] or brief["title"],
        "hook": ann["hook"] or brief["hook"],
        "announcing": ann["announcing"] or brief["announcing"],
        "product_name": (brief["title"] or slug).replace(" launch brief", "").strip(),
    }
    base_url = f"https://zergai.com/{slug}"
    campaign = f"{slug}-launch-T0"

    allowlist = load_utm_allowlist(slug)
    links: dict[str, str] = {}
    for surface, _label, medium in SURFACES:
        violations = check_utm_against_allowlist(allowlist, surface, medium, campaign)
        if violations:
            for v in violations:
                print(f"ERROR: UTM allowlist violation for {surface}: {v}", file=sys.stderr)
            return 3
        links[surface] = build_utm_link(base_url, surface, medium, campaign)

    out = LAUNCHES / slug / "distribution.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_distribution_md(slug, ctx, links))
    print(f"distribution.md written: {out}")

    if args.cards:
        rc = create_cards(slug)
        if rc:
            return 2
    return 0


def create_cards(slug: str) -> int:
    if not ZERGBOARD_CLI.exists():
        print(f"WARN: zergboard CLI not found at {ZERGBOARD_CLI}; skipping cards.", file=sys.stderr)
        return 0
    failures = 0
    for surface, label, _medium in SURFACES:
        title = f"DIST-{slug}-{surface}"
        try:
            result = subprocess.run(
                [
                    sys.executable, str(ZERGBOARD_CLI), "create", "Marketing",
                    "--title", title,
                    "--description", f"Distribution surface for {slug}: {label}",
                ],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode != 0:
                print(f"WARN: card creation failed for {title}: {result.stderr.strip()}", file=sys.stderr)
                failures += 1
        except (subprocess.SubprocessError, OSError) as e:
            print(f"WARN: subprocess error creating {title}: {e}", file=sys.stderr)
            failures += 1
    if failures:
        print(f"zergboard: {failures} card creation failure(s)", file=sys.stderr)
        return 2
    print("zergboard: cards created")
    return 0


def cmd_cards(args: argparse.Namespace) -> int:
    slug = args.slug
    if not (LAUNCHES / slug).exists():
        print(f"ERROR: launch dir not found: {LAUNCHES / slug}", file=sys.stderr)
        return 1
    return create_cards(slug)


def cmd_list(args: argparse.Namespace) -> int:
    print("# 17 canonical distribution surfaces\n")
    for surface, label, medium in SURFACES:
        example = f"https://zergai.com/<slug>?utm_source={surface}&utm_medium={medium}&utm_campaign=<slug>-launch-T0"
        print(f"## {label} (`{surface}`, medium={medium})")
        print(f"  Example UTM: {example}")
        print()
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="content-distribution", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    pg = sub.add_parser("generate", help="render distribution.md for a launch slug")
    pg.add_argument("slug")
    pg.add_argument("--cards", action="store_true", help="also create Zergboard cards per surface")
    pg.set_defaults(func=cmd_generate)

    pc = sub.add_parser("cards", help="create Zergboard cards for an existing distribution")
    pc.add_argument("slug")
    pc.set_defaults(func=cmd_cards)

    pl = sub.add_parser("list", help="print 17 canonical surfaces with example UTM")
    pl.set_defaults(func=cmd_list)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
