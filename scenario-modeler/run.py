#!/usr/bin/env python3
"""scenario-modeler — what-if sweeps, tornado charts, simple Monte Carlo."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".claude/skills/_consultant/python"))
from _bootstrap_helper import ensure_venv  # noqa: E402

ensure_venv(__file__)

import argparse  # noqa: E402
import json  # noqa: E402


def _evaluate(model: str, params: dict) -> float:
    safe_builtins = {"min": min, "max": max, "abs": abs, "round": round}
    return float(eval(model, {"__builtins__": safe_builtins}, params))  # noqa: S307


def run(args) -> int:
    import numpy as np  # type: ignore
    from consultant_kit import chart, frontmatter, io  # type: ignore

    spec = json.loads(Path(args.spec).read_text())
    model = spec["model"]
    params = spec["params"]
    name = spec.get("name", "scenario")
    outcome = spec.get("outcome", "outcome")
    slug = io.slugify(name)[:40]

    base = {k: v["base"] for k, v in params.items()}
    base_val = _evaluate(model, base)

    # Scenarios
    low_p = {k: v.get("low", v["base"]) for k, v in params.items()}
    high_p = {k: v.get("high", v["base"]) for k, v in params.items()}
    low_val = _evaluate(model, low_p)
    high_val = _evaluate(model, high_p)

    # Tornado: per-param swing
    tornado = []
    for k in params:
        lo_only = dict(base)
        lo_only[k] = params[k].get("low", params[k]["base"])
        hi_only = dict(base)
        hi_only[k] = params[k].get("high", params[k]["base"])
        lo_v = _evaluate(model, lo_only)
        hi_v = _evaluate(model, hi_only)
        swing = abs(hi_v - lo_v)
        tornado.append((k, lo_v, hi_v, swing))
    tornado.sort(key=lambda t: -t[3])

    engagement = args.engagement or slug
    mode = args.mode or "ops"
    out_root = io.engagement_dir(engagement, mode) / "05-analysis/scenarios"
    charts_dir = io.engagement_dir(engagement, mode) / "05-analysis/charts"
    out_root.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)

    # Tornado chart (horizontal bar of swing magnitude)
    tornado_png = charts_dir / f"{slug}-tornado.png"
    chart.render(
        "bar", out=tornado_png,
        labels=[t[0] for t in tornado],
        values=[t[3] for t in tornado],
        ylabel=f"Swing in {outcome}",
        horizontal=True,
    )

    body = [
        f"## {name}",
        "",
        f"**Outcome:** {outcome}",
        f"**Model:** `{model}`",
        "",
        "### Base / low / high",
        "",
        "| Scenario | Value |",
        "|---|---|",
        f"| Base   | **{base_val:,.1f}** |",
        f"| Low    | {low_val:,.1f} |",
        f"| High   | {high_val:,.1f} |",
        "",
        "### Assumptions table",
        "",
        "| Param | Base | Low | High | Source |",
        "|---|---|---|---|---|",
    ]
    for k, v in params.items():
        body.append(
            f"| `{k}` | {v['base']} | {v.get('low', v['base'])} | {v.get('high', v['base'])} | {v.get('source', '[needs-verification]')} |"
        )

    body.append("")
    body.append("### Sensitivity (tornado — most influential first)")
    body.append("")
    body.append("| Param | Outcome at param-low | Outcome at param-high | Swing |")
    body.append("|---|---|---|---|")
    for k, lo, hi, sw in tornado:
        body.append(f"| `{k}` | {lo:,.1f} | {hi:,.1f} | {sw:,.1f} |")

    # Monte Carlo
    mc_png = None
    if args.monte_carlo:
        n = args.monte_carlo
        rng = np.random.default_rng(42)
        outs = []
        for _ in range(n):
            draw = {}
            for k, v in params.items():
                lo = v.get("low", v["base"])
                hi = v.get("high", v["base"])
                draw[k] = float(rng.uniform(lo, hi))
            outs.append(_evaluate(model, draw))
        outs_arr = np.array(outs)
        p5, p50, p95 = float(np.percentile(outs_arr, 5)), float(np.percentile(outs_arr, 50)), float(np.percentile(outs_arr, 95))
        body.append("")
        body.append(f"### Monte Carlo ({n} draws, uniform priors)")
        body.append("")
        body.append(f"- p5: {p5:,.1f}")
        body.append(f"- p50 (median): {p50:,.1f}")
        body.append(f"- p95: {p95:,.1f}")
        # render histogram-style as a bar chart of binned counts
        bins = 12
        counts, edges = np.histogram(outs_arr, bins=bins)
        labels = [f"{edges[i]:.0f}–{edges[i+1]:.0f}" for i in range(bins)]
        mc_png = charts_dir / f"{slug}-distribution.png"
        chart.render("bar", out=mc_png, labels=labels, values=counts.tolist(), ylabel=f"# draws ({outcome})")
        body.append(f"- distribution: `{mc_png}`")

    body.append("")
    body.append("### Charts")
    body.append(f"- Tornado: `{tornado_png}`")
    if mc_png:
        body.append(f"- Distribution: `{mc_png}`")

    fm = frontmatter.envelope(
        engagement=engagement,
        slug=f"{slug}-scenario",
        skill="scenario-modeler",
        inputs=[args.spec],
        upstream=[],
        extra={"name": name, "outcome": outcome, "base": base_val, "low": low_val, "high": high_val},
    )
    out_path = out_root / f"{slug}.md"
    frontmatter.write_md(out_path, fm, "\n".join(body))
    print(f"wrote {out_path}")
    print(f"wrote {tornado_png}")
    if mc_png:
        print(f"wrote {mc_png}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="scenario-modeler")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("spec")
    r.add_argument("--engagement", default=None)
    r.add_argument("--mode", choices=("client", "pm", "ops", "life"), default=None)
    r.add_argument("--monte-carlo", type=int, default=0)
    r.set_defaults(func=run)
    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
