#!/usr/bin/env python3
"""cost-benefit — NPV / IRR / ROI / payback with assumptions + sensitivity."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".claude/skills/_consultant/python"))
from _bootstrap_helper import ensure_venv  # noqa: E402

ensure_venv(__file__)

import argparse  # noqa: E402
import json  # noqa: E402


def run(args) -> int:
    import numpy_financial as npf  # type: ignore
    from consultant_kit import chart, frontmatter, io  # type: ignore

    spec = json.loads(Path(args.spec).read_text())
    name = spec["name"]
    rate = float(spec.get("discount_rate", 0.10))
    periods = spec["periods"]
    invest = float(spec["investment"])  # negative
    flows = [float(x) for x in spec["cash_flows"]]
    assumptions = spec.get("assumptions", [])
    slug = io.slugify(name)[:40]

    series = [invest] + flows
    npv = float(npf.npv(rate, series))
    try:
        irr = float(npf.irr(series))
    except Exception:  # noqa: BLE001
        irr = None
    roi = (sum(flows) + invest) / max(abs(invest), 1)
    cum = 0.0
    payback_period = None
    for i, v in enumerate(series):
        cum += v
        if cum >= 0 and payback_period is None and i > 0:
            payback_period = periods[i - 1]
            break

    engagement = args.engagement or slug
    mode = args.mode or "ops"
    out_root = io.engagement_dir(engagement, mode) / "05-analysis/cost-benefit"
    charts_dir = io.engagement_dir(engagement, mode) / "05-analysis/charts"
    out_root.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)

    # Waterfall: investment then each period
    waterfall_png = charts_dir / f"{slug}-waterfall.png"
    labels = periods
    deltas = flows
    chart.render(
        "waterfall", out=waterfall_png,
        labels=labels, deltas=deltas, ylabel="$",
        start_label=f"Investment ({invest:,.0f})",
        end_label=f"Cumulative ({sum(series):,.0f})",
    )

    body = [
        f"## {name}",
        "",
        f"- Discount rate: {rate*100:.1f}%",
        f"- Investment: {invest:,.0f}",
        f"- **NPV:** {npv:,.0f}",
        f"- **IRR:** {(irr*100):.1f}%" if irr is not None else "- **IRR:** n/a (no sign change)",
        f"- **ROI:** {roi*100:.1f}%",
        f"- **Payback:** {payback_period or 'not reached'}",
        "",
        "### Assumptions",
        "",
        "| Label | Value | Source |",
        "|---|---|---|",
    ]
    has_nv = False
    for a in assumptions:
        src = a.get("source", "[needs-verification]")
        if "[needs-verification]" in src:
            has_nv = True
        body.append(f"| {a.get('label')} | {a.get('value')} | {src} |")

    body.append("")
    body.append("### Cash flow series")
    body.append("")
    body.append("| Period | Cash flow | Cumulative |")
    body.append("|---|---|---|")
    cum = 0.0
    for label, v in zip([f"Investment ({periods[0]} - 1)"] + periods, series):
        cum += v
        body.append(f"| {label} | {v:,.0f} | {cum:,.0f} |")

    body.append("")
    body.append(f"### Waterfall: `{waterfall_png}`")
    if has_nv:
        body.append("")
        body.append("⚠️ Some assumptions carry `[needs-verification]` — client-mode deck will refuse to render until resolved.")

    fm = frontmatter.envelope(
        engagement=engagement,
        slug=f"{slug}-cba",
        skill="cost-benefit",
        inputs=[args.spec],
        upstream=[],
        extra={"npv": npv, "irr": irr, "roi": roi, "payback": payback_period},
    )
    out_path = out_root / f"{slug}.md"
    frontmatter.write_md(out_path, fm, "\n".join(body))
    print(f"wrote {out_path}")
    print(f"wrote {waterfall_png}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="cost-benefit")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("spec")
    r.add_argument("--engagement", default=None)
    r.add_argument("--mode", choices=("client", "pm", "ops", "life"), default=None)
    r.set_defaults(func=run)
    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
