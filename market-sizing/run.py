#!/usr/bin/env python3
"""market-sizing — TAM/SAM/SOM with bottom-up + top-down + triangulation."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".claude/skills/_consultant/python"))
from _bootstrap_helper import ensure_venv  # noqa: E402

ensure_venv(__file__)

import argparse  # noqa: E402
import json  # noqa: E402


def size(args) -> int:
    from consultant_kit import chart, frontmatter, io  # type: ignore

    spec = json.loads(Path(args.spec).read_text())
    name = spec["name"]
    slug = io.slugify(name)[:40]
    currency = spec.get("currency", "USD")
    year = spec.get("year", "")

    bu = spec.get("bottom_up", [])
    td = spec.get("top_down")

    # Refuse if any segment lacks a source
    for s in bu:
        if not s.get("source") or "[needs-verification]" in s.get("source", ""):
            print(f"REFUSED: segment {s.get('segment')} has no source — every market-size number needs `[source: ...]`")
            return 2
    if td and (not td.get("source") or "[needs-verification]" in td.get("source", "")):
        print("REFUSED: top-down has no source — every market-size number needs `[source: ...]`")
        return 2

    # Bottom-up TAM = sum(units * arpu); SAM = same with capture-cap proxy (units * arpu * capture limit factor); SOM = sum(units * arpu * capture)
    bu_tam = sum(s["units"] * s["arpu"] for s in bu)
    bu_som = sum(s["units"] * s["arpu"] * s.get("capture", 0) for s in bu)
    # SAM defined as TAM * 30% by default (or sum where capture > 0)
    bu_sam = sum(s["units"] * s["arpu"] for s in bu if s.get("capture", 0) > 0) or (bu_tam * 0.3)

    td_tam = td_sam = td_som = None
    if td:
        td_tam = td.get("total_market", 0)
        td_sam = td_tam * td.get("addressable_pct", 0)
        td_som = td_tam * td.get("obtainable_pct", 0)

    # Triangulation
    tam = (bu_tam + (td_tam or bu_tam)) / 2
    sam = (bu_sam + (td_sam or bu_sam)) / 2
    som = (bu_som + (td_som or bu_som)) / 2

    flags = []
    if td_tam and bu_tam > 2 * td_tam:
        flags.append(f"Bottom-up TAM ({bu_tam:,.0f}) > 2× top-down ({td_tam:,.0f}) — likely double-count")
    if not td:
        flags.append("No top-down reference provided — single-method sizing")
    if not bu:
        flags.append("No bottom-up segments provided — single-method sizing")

    engagement = args.engagement or slug
    mode = args.mode or "ops"
    out_root = io.engagement_dir(engagement, mode) / "05-analysis/market-sizing"
    charts_dir = io.engagement_dir(engagement, mode) / "05-analysis/charts"
    out_root.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)

    chart_png = charts_dir / f"{slug}-stacked.png"
    series = {"Method": [tam, sam, som]}
    chart.render(
        "bar", out=chart_png,
        labels=["TAM", "SAM", "SOM"],
        values=[tam, sam, som],
        ylabel=f"{currency}",
    )

    body = [
        f"## {name}",
        "",
        f"- Currency: {currency}",
        f"- Year: {year}",
        "",
        "### Triangulated sizing",
        "",
        "| Layer | Triangulated | Bottom-up | Top-down |",
        "|---|---|---|---|",
        f"| TAM | {tam:,.0f} | {bu_tam:,.0f} | {td_tam or '—'} |",
        f"| SAM | {sam:,.0f} | {bu_sam:,.0f} | {td_sam or '—'} |",
        f"| SOM | {som:,.0f} | {bu_som:,.0f} | {td_som or '—'} |",
        "",
        "### Bottom-up segments",
        "",
        "| Segment | Units | ARPU | Capture | Segment $ | Source |",
        "|---|---|---|---|---|---|",
    ]
    for s in bu:
        seg_val = s["units"] * s["arpu"] * s.get("capture", 0)
        body.append(f"| {s['segment']} | {s['units']:,} | {s['arpu']:,} | {s.get('capture',0)*100:.2f}% | {seg_val:,.0f} | {s['source']} |")

    if td:
        body.append("")
        body.append("### Top-down reference")
        body.append("")
        body.append(f"- Total market: {td.get('total_market'):,} `{td['source']}`")
        body.append(f"- Addressable (SAM%): {td.get('addressable_pct')*100:.1f}%")
        body.append(f"- Obtainable (SOM%): {td.get('obtainable_pct')*100:.1f}%")

    if flags:
        body.append("")
        body.append("### Triangulation flags")
        for f in flags:
            body.append(f"- ⚠️ {f}")

    body.append("")
    body.append(f"### Chart: `{chart_png}`")

    fm = frontmatter.envelope(
        engagement=engagement,
        slug=f"{slug}-sizing",
        skill="market-sizing",
        inputs=[args.spec],
        upstream=[],
        source_citations=[{"claim": s.get("segment", "top-down"), "source": s.get("source", "")} for s in bu] + ([{"claim": "top-down ref", "source": td["source"]}] if td else []),
        extra={"tam": tam, "sam": sam, "som": som, "flags": flags},
    )
    out_path = out_root / f"{slug}.md"
    frontmatter.write_md(out_path, fm, "\n".join(body))
    print(f"wrote {out_path}")
    print(f"wrote {chart_png}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="market-sizing")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("size")
    s.add_argument("spec")
    s.add_argument("--engagement", default=None)
    s.add_argument("--mode", choices=("client", "pm", "ops", "life"), default=None)
    s.set_defaults(func=size)
    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
