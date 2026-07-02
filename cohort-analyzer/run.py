#!/usr/bin/env python3
"""cohort-analyzer — retention curves + vintage matrix."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".claude/skills/_consultant/python"))
from _bootstrap_helper import ensure_venv  # noqa: E402

ensure_venv(__file__)

import argparse  # noqa: E402


def analyze(args) -> int:
    import pandas as pd  # type: ignore
    from consultant_kit import chart, frontmatter, io  # type: ignore

    df = pd.read_parquet(args.path)
    df[args.time_col] = pd.to_datetime(df[args.time_col])
    signup = df[df[args.event_col] == args.signup_event].groupby(args.user_col)[args.time_col].min().reset_index()
    signup.columns = [args.user_col, "cohort_time"]

    targets = df[df[args.event_col] == args.target_event][[args.user_col, args.time_col]]
    targets.columns = [args.user_col, "event_time"]

    merged = signup.merge(targets, on=args.user_col, how="left")
    merged["delta_days"] = (merged["event_time"] - merged["cohort_time"]).dt.days

    period = args.period or "week"
    if period == "week":
        merged["cohort"] = merged["cohort_time"].dt.to_period("W").astype(str)
        bucket_days = 7
    else:
        merged["cohort"] = merged["cohort_time"].dt.to_period("M").astype(str)
        bucket_days = 30

    horizon = max(1, args.horizon)
    cohorts = sorted(merged["cohort"].unique())
    if len(cohorts) < 3:
        print(f"REFUSED: only {len(cohorts)} cohorts — need ≥3 for cohort analysis")
        return 2

    # Retention matrix: cohort × period
    matrix = []
    row_labels = []
    for c in cohorts:
        sub = merged[merged["cohort"] == c]
        n = sub[args.user_col].nunique()
        row = []
        for p in range(horizon + 1):
            window_lo = p * bucket_days
            window_hi = (p + 1) * bucket_days
            converted = sub[(sub["delta_days"] >= window_lo) & (sub["delta_days"] < window_hi)][args.user_col].nunique()
            row.append(round(100 * converted / n, 2) if n else 0.0)
        matrix.append(row)
        row_labels.append(f"{c} (n={n})")

    col_labels = [f"P{p}" for p in range(horizon + 1)]

    engagement = args.engagement or io.slugify(Path(args.path).stem)[:40]
    mode = args.mode or "ops"
    out_root = io.engagement_dir(engagement, mode) / "05-analysis"
    charts_dir = out_root / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    matrix_png = charts_dir / "cohort-vintage-matrix.png"
    chart.render("heatmap", out=matrix_png, matrix=matrix, row_labels=row_labels, col_labels=col_labels, cbar_label="Conversion %")

    series = {row_labels[i]: matrix[i] for i in range(len(row_labels))}
    curves_png = charts_dir / "cohort-retention-curves.png"
    chart.render("line", out=curves_png, x=col_labels, series=series, ylabel="Conversion %", xlabel="Period since cohort start")

    body = [
        "## Cohort retention",
        "",
        f"- cohorts: {len(cohorts)}",
        f"- bucket: {period} ({bucket_days}d)",
        f"- horizon: {horizon} periods",
        "",
        "### Vintage matrix (% converted to target event by period)",
        "",
        "| Cohort | " + " | ".join(col_labels) + " |",
        "|---" + ("|---" * (horizon + 1)) + "|",
    ]
    for label, row in zip(row_labels, matrix):
        body.append(f"| {label} | " + " | ".join(f"{v:.1f}%" for v in row) + " |")
    body.append("")
    body.append("### Charts")
    body.append(f"- Retention curves: `{curves_png}`")
    body.append(f"- Vintage heatmap: `{matrix_png}`")

    fm = frontmatter.envelope(
        engagement=engagement,
        slug=f"{io.slugify(engagement)}-cohort",
        skill="cohort-analyzer",
        inputs=[args.path],
        upstream=[args.path],
        extra={"period": period, "horizon": horizon, "cohorts": len(cohorts)},
    )
    out_path = out_root / "cohort-retention.md"
    frontmatter.write_md(out_path, fm, "\n".join(body))
    print(f"wrote {out_path}")
    print(f"wrote {curves_png}")
    print(f"wrote {matrix_png}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="cohort-analyzer")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("analyze")
    a.add_argument("path")
    a.add_argument("--user-col", required=True)
    a.add_argument("--event-col", required=True)
    a.add_argument("--time-col", required=True)
    a.add_argument("--signup-event", required=True)
    a.add_argument("--target-event", required=True)
    a.add_argument("--period", choices=("week", "month"), default="week")
    a.add_argument("--horizon", type=int, default=8)
    a.add_argument("--engagement", default=None)
    a.add_argument("--mode", choices=("client", "pm", "ops", "life"), default=None)
    a.set_defaults(func=analyze)
    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
