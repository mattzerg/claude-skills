#!/usr/bin/env python3
"""data-pipeline — load, clean, audit, describe."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".claude/skills/_consultant/python"))
from _bootstrap_helper import ensure_venv  # noqa: E402

ensure_venv(__file__)

import argparse  # noqa: E402
import json  # noqa: E402
import urllib.parse  # noqa: E402


def _load(path: str, date_cols: list[str], drop_cols: list[str]):
    import pandas as pd  # type: ignore

    pl = path.lower()
    parsed = urllib.parse.urlparse(path)
    if parsed.scheme in ("http", "https"):
        if pl.endswith(".parquet"):
            df = pd.read_parquet(path)
        elif pl.endswith(".json"):
            df = pd.read_json(path)
        else:
            df = pd.read_csv(path)
    elif pl.endswith(".parquet"):
        df = pd.read_parquet(path)
    elif pl.endswith(".json"):
        df = pd.read_json(path)
    else:
        df = pd.read_csv(path)

    mods: list[str] = []
    if drop_cols:
        existed = [c for c in drop_cols if c in df.columns]
        if existed:
            df = df.drop(columns=existed)
            mods.append(f"Dropped columns: {existed}")
    if date_cols:
        for c in date_cols:
            if c in df.columns:
                df[c] = pd.to_datetime(df[c], errors="coerce")
                mods.append(f"Coerced `{c}` to datetime")
    return df, mods


def _audit(df, id_cols: list[str], mods: list[str]) -> str:
    import pandas as pd  # type: ignore
    import numpy as np  # type: ignore

    parts = []
    parts.append("## Schema\n")
    parts.append("| Column | Dtype | Non-null | Sample |\n|---|---|---|---|")
    for c in df.columns:
        dt = str(df[c].dtype)
        nn = int(df[c].notna().sum())
        sample = df[c].dropna().head(2).tolist()
        sample_str = ", ".join(str(s)[:24] for s in sample)
        parts.append(f"| `{c}` | {dt} | {nn} / {len(df)} | {sample_str} |")
    parts.append("")

    miss = df.isna().mean()
    high_miss = miss[miss > 0]
    if not high_miss.empty:
        parts.append("## Missing values\n")
        parts.append("| Column | Missing % |\n|---|---|")
        for c, m in high_miss.sort_values(ascending=False).items():
            parts.append(f"| `{c}` | {m*100:.1f}% |")
        parts.append("")

    num_cols = df.select_dtypes(include="number").columns.tolist()
    if num_cols:
        parts.append("## Numeric summary\n")
        parts.append("| Column | mean | median | p25 | p75 | std | n outliers (IQR) |\n|---|---|---|---|---|---|---|")
        for c in num_cols:
            s = df[c].dropna()
            if s.empty:
                continue
            q1, q3 = s.quantile(0.25), s.quantile(0.75)
            iqr = q3 - q1
            lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            outliers = int(((s < lo) | (s > hi)).sum())
            parts.append(
                f"| `{c}` | {s.mean():.3g} | {s.median():.3g} | {q1:.3g} | {q3:.3g} | {s.std():.3g} | {outliers} |"
            )
        parts.append("")

    if id_cols:
        parts.append("## Duplicates by id\n")
        for c in id_cols:
            if c in df.columns:
                dup = int(df[c].duplicated().sum())
                parts.append(f"- `{c}`: {dup} duplicate rows")
        parts.append("")

    parts.append("## Modifications applied\n")
    if mods:
        for m in mods:
            parts.append(f"- {m}")
    else:
        parts.append("- (none)")
    parts.append("")

    parts.append("## Row count\n")
    parts.append(f"- rows: {len(df)}")
    parts.append(f"- cols: {len(df.columns)}")
    return "\n".join(parts)


def load_cmd(args) -> int:
    from consultant_kit import frontmatter, io  # type: ignore

    date_cols = [c.strip() for c in (args.date_cols or "").split(",") if c.strip()]
    id_cols = [c.strip() for c in (args.id_cols or "").split(",") if c.strip()]
    drop_cols = [c.strip() for c in (args.drop_cols or "").split(",") if c.strip()]

    df, mods = _load(args.path, date_cols, drop_cols)
    audit_body = _audit(df, id_cols, mods)

    engagement = args.engagement or io.slugify(Path(args.path).stem)[:40]
    mode = args.mode or "ops"
    slug = args.slug or io.slugify(Path(args.path).stem)[:40]

    if args.engagement:
        data_dir = io.engagement_dir(engagement, mode) / "05-analysis/data"
    else:
        data_dir = Path(args.out_dir or "/tmp/consultant/data-pipeline") / slug
    data_dir.mkdir(parents=True, exist_ok=True)

    import datetime as _dt
    date = _dt.date.today().isoformat()
    pq_path = data_dir / f"{slug}-clean-{date}.parquet"
    df.to_parquet(pq_path)

    schema = {
        "columns": [{"name": c, "dtype": str(df[c].dtype), "non_null": int(df[c].notna().sum())} for c in df.columns],
        "rows": len(df),
        "modifications": mods,
    }
    schema_path = pq_path.with_suffix(".json")
    schema_path.write_text(json.dumps(schema, indent=2, default=str))

    fm = frontmatter.envelope(
        engagement=engagement,
        slug=f"{slug}-audit",
        skill="data-pipeline",
        inputs=[args.path],
        upstream=[],
        extra={"parquet": str(pq_path), "schema": str(schema_path), "rows": len(df), "cols": len(df.columns)},
    )
    audit_path = data_dir / f"{slug}-audit-{date}.md"
    frontmatter.write_md(audit_path, fm, audit_body)

    print(f"wrote {pq_path}")
    print(f"wrote {schema_path}")
    print(f"wrote {audit_path}")
    return 0


def describe(args) -> int:
    import pandas as pd  # type: ignore
    df = pd.read_parquet(args.path)
    print(_audit(df, [], []))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="data-pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)

    l = sub.add_parser("load")
    l.add_argument("path")
    l.add_argument("--engagement", default=None)
    l.add_argument("--mode", choices=("client", "pm", "ops", "life"), default=None)
    l.add_argument("--slug", default=None)
    l.add_argument("--date-cols", default=None)
    l.add_argument("--id-cols", default=None)
    l.add_argument("--drop-cols", default=None)
    l.add_argument("--out-dir", default=None)
    l.set_defaults(func=load_cmd)

    d = sub.add_parser("describe")
    d.add_argument("path")
    d.set_defaults(func=describe)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
