#!/usr/bin/env python3
"""tech-landscape — emerging-tech landscape scan scaffold."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".claude/skills/_consultant/python"))
from _bootstrap_helper import ensure_venv  # noqa: E402

ensure_venv(__file__)

import argparse  # noqa: E402


def scan(args) -> int:
    from consultant_kit import frontmatter, io  # type: ignore

    if args.mode == "life":
        print("REFUSED: tech-landscape is not available in life-mgmt mode (air-gapped from external search).")
        return 2

    category = args.category
    vendors = [v.strip() for v in (args.vendors or "").split(",") if v.strip()]
    horizon = args.horizon or "12-mo"
    slug = io.slugify(category)[:40]
    engagement = args.engagement or slug
    mode = args.mode or "ops"

    body = [
        f"## Tech landscape — {category}",
        "",
        f"**Horizon:** {horizon}",
        "",
        "### Vendor map",
        "",
        "| Vendor | Stage | Signal strength | Notable customers | Notes |",
        "|---|---|---|---|---|",
    ]
    for v in vendors or ["[Vendor 1]", "[Vendor 2]", "[Vendor 3]"]:
        body.append(f"| {v} | _innovator/early/late_ | _high/med/low_ | _[customer1, customer2]_ | _[notes]_ `[needs-verification]` |")

    body.extend([
        "",
        "### Adoption curve placement",
        "",
        "| Stage | Category position | Evidence |",
        "|---|---|---|",
        "| Innovators (2.5%) | _?_ | _[research labs / hyperscalers using it]_ |",
        "| Early adopters (13.5%) | _?_ | _[named startups + 1-2 enterprise pilots]_ |",
        "| Early majority (34%) | _?_ | _[paying enterprise customers]_ |",
        "| Late majority (34%) | _?_ | _[boring-enterprise adoption]_ |",
        "| Laggards (16%) | _?_ | _[regulated / inertial industries]_ |",
        "",
        "### Standards / protocols",
        "",
        "- _[name standard]_ — `[needs-verification]`",
        "- _[name spec]_ — `[needs-verification]`",
        "",
        "### Forward-looking risks",
        "",
        "- Platform consolidation: _[likelihood]_",
        "- Standards fragmentation: _[likelihood]_",
        "- Open-source displacement: _[likelihood]_",
        "",
        "### External search queries to run",
        "",
        "Composition (run these via `exa:search` / `firecrawl:firecrawl-search`):",
        "",
        f"- `exa:search` — \"{category} vendors 2026\"",
        f"- `exa:search` — \"{category} adoption curve enterprise\"",
        f"- `firecrawl:firecrawl-search` — \"{category} pricing leaders 2026\"",
        f"- `competitive-review-skill` — discover + scan top-5 vendors named above",
        "",
        "### Notes",
        "",
        "- Every numeric claim in vendor/customer table must carry `[source: …]` or `[needs-verification]`.",
        "- Refresh quarterly — emerging tech moves quickly.",
        "- Anchored on `MattZerg/_style/consultant_thinking_style.md`.",
    ])

    fm = frontmatter.envelope(
        engagement=engagement,
        slug=f"{slug}-landscape",
        skill="tech-landscape",
        inputs=[category],
        upstream=[],
        extra={"mode": mode, "category": category, "vendors": vendors, "horizon": horizon},
    )
    out_root = io.engagement_dir(engagement, mode) / "05-analysis"
    out_root.mkdir(parents=True, exist_ok=True)
    out_path = out_root / f"tech-landscape-{slug}.md"
    frontmatter.write_md(out_path, fm, "\n".join(body))
    print(f"wrote {out_path}")
    print("\nNEXT: dispatch the external-search queries listed at the bottom of the file.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="tech-landscape")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("category")
    s.add_argument("--engagement", default=None)
    s.add_argument("--mode", choices=("client", "pm", "ops", "life"), default=None)
    s.add_argument("--vendors", default=None)
    s.add_argument("--horizon", default=None)
    s.set_defaults(func=scan)
    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
