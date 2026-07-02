#!/usr/bin/env python3
"""chart-builder — render Zerg-branded chart recipes.

12 recipes, defaults: labels ON, gridlines ON, smart axis formatter.
Verbs: render (inline flags), render-spec (JSON spec), batch (manifest of specs),
validate (lint a spec), recipes (list available).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".claude/skills/_consultant/python"))
from _bootstrap_helper import ensure_venv  # noqa: E402

ensure_venv(__file__)

import argparse  # noqa: E402
import json  # noqa: E402


def _write_caption(out: Path, recipe: str, palette: str, caption: str, extras: dict) -> Path:
    cap_path = out.with_suffix(".caption.md")
    body = [
        f"# {caption or '[draft action title]'}",
        "",
        f"- recipe: `{recipe}`",
        f"- palette: `{palette}`",
        f"- png: `{out}`",
    ]
    for k, v in extras.items():
        body.append(f"- {k}: {v}")
    cap_path.write_text("\n".join(body) + "\n")
    return cap_path


def _common_flags(kwargs: dict, args) -> dict:
    """Apply shared CLI flags (labels/grid/target/baseline/etc) into recipe kwargs."""
    if getattr(args, "no_labels", False):
        kwargs["labels_on"] = False
    if getattr(args, "no_grid", False):
        kwargs["grid"] = False
    if getattr(args, "target", None) is not None:
        kwargs["target"] = args.target
    if getattr(args, "baseline", None) is not None:
        kwargs["baseline"] = args.baseline
    if getattr(args, "accessible", False):
        kwargs["accessible"] = True
    if getattr(args, "semantic", False):
        kwargs["semantic"] = True
    if getattr(args, "highlight", None):
        kwargs["highlight"] = args.highlight
    if getattr(args, "currency", None):
        kwargs["currency"] = args.currency
    return kwargs


def _render_dispatch(recipe: str, args_dict: dict, out: Path, palette: str) -> dict:
    from consultant_kit import chart  # type: ignore
    return chart.render(recipe, out=out, mode=palette, **args_dict)


def _parse_series(series_arg: str) -> dict[str, list[float]]:
    """`s1=1,2,3;s2=4,5,6` → {'s1': [1,2,3], 's2': [4,5,6]}"""
    series: dict[str, list[float]] = {}
    for s in (series_arg or "").split(";"):
        if not s.strip():
            continue
        name, vals = s.split("=", 1)
        series[name.strip()] = [float(v) for v in vals.split(",")]
    return series


def render(args) -> int:
    recipe = args.recipe
    palette = args.palette or "default"
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    kwargs: dict = {}
    if recipe == "bar":
        kwargs["labels"] = args.labels.split(",")
        kwargs["values"] = [float(v) for v in args.values.split(",")]
        if args.ylabel:
            kwargs["ylabel"] = args.ylabel
        if args.horizontal:
            kwargs["horizontal"] = True
        if args.highlight_idx is not None:
            kwargs["highlight_idx"] = args.highlight_idx
    elif recipe == "line":
        kwargs["x"] = args.labels.split(",")
        series = _parse_series(args.series or "")
        if not series and args.values:
            series["series"] = [float(v) for v in args.values.split(",")]
        kwargs["series"] = series
        if args.ylabel:
            kwargs["ylabel"] = args.ylabel
        if args.xlabel:
            kwargs["xlabel"] = args.xlabel
        if args.dashed_after is not None:
            kwargs["dashed_after"] = args.dashed_after
    elif recipe == "stacked-bar":
        kwargs["labels"] = args.labels.split(",")
        kwargs["series"] = _parse_series(args.series or "")
        if args.ylabel:
            kwargs["ylabel"] = args.ylabel
    elif recipe == "waterfall":
        kwargs["labels"] = args.labels.split(",")
        kwargs["deltas"] = [float(v) for v in args.values.split(",")]
        if args.ylabel:
            kwargs["ylabel"] = args.ylabel
        if args.start_label:
            kwargs["start_label"] = args.start_label
        if args.end_label:
            kwargs["end_label"] = args.end_label
    elif recipe == "grouped-bar":
        kwargs["labels"] = args.labels.split(",")
        kwargs["series"] = _parse_series(args.series or "")
        if args.ylabel:
            kwargs["ylabel"] = args.ylabel
    elif recipe == "dot-plot":
        kwargs["labels"] = args.labels.split(",")
        kwargs["values"] = [float(v) for v in args.values.split(",")]
        if args.ylabel:
            kwargs["ylabel"] = args.ylabel
        if args.highlight_idx is not None:
            kwargs["highlight_idx"] = args.highlight_idx
        if args.no_sort:
            kwargs["sort"] = False
    else:
        print(f"ERROR: recipe {recipe!r} requires JSON spec — use `render-spec`. Inline flags support bar/line/stacked-bar/waterfall/grouped-bar/dot-plot.")
        return 1

    kwargs = _common_flags(kwargs, args)
    out_paths = _render_dispatch(recipe, kwargs, out, palette)
    cap = _write_caption(out, recipe, palette, args.caption or "", {})
    print(f"wrote {out_paths.get('png')}")
    if "svg" in out_paths:
        print(f"wrote {out_paths['svg']}")
    print(f"wrote {cap}")
    return 0


def render_spec(args) -> int:
    spec_path = Path(args.spec)
    spec = json.loads(spec_path.read_text())
    # Validate first
    from consultant_kit import chart  # type: ignore
    findings = chart.validate_spec(spec)
    high = [f for f in findings if f[0] == "HIGH"]
    if high:
        print("REFUSED — spec has HIGH-severity findings:")
        for sev, msg in high:
            print(f"  {sev}: {msg}")
        if not args.force:
            return 2
    recipe = spec.pop("recipe")
    palette = spec.pop("palette", "default")
    caption = spec.pop("caption", "")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    paths = _render_dispatch(recipe, spec, out, palette)
    cap = _write_caption(out, recipe, palette, caption, {})
    print(f"wrote {paths.get('png')}")
    if "svg" in paths:
        print(f"wrote {paths['svg']}")
    print(f"wrote {cap}")
    return 0


def batch(args) -> int:
    """Render multiple charts from a manifest JSON array."""
    from consultant_kit import chart  # type: ignore
    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text())
    if not isinstance(manifest, list):
        print("ERROR: manifest must be a JSON array of specs (each with `out` path)")
        return 1
    ok = 0
    failed = []
    for i, spec in enumerate(manifest):
        out = spec.pop("out", None)
        if not out:
            failed.append((i, "no `out` path"))
            continue
        # Resolve out relative to manifest dir
        out_path = Path(out)
        if not out_path.is_absolute():
            out_path = manifest_path.parent / out_path
        # Validate
        findings = chart.validate_spec(spec)
        high = [f for f in findings if f[0] == "HIGH"]
        if high and not args.force:
            failed.append((i, f"HIGH findings: {high}"))
            continue
        try:
            recipe = spec.pop("recipe")
            palette = spec.pop("palette", "default")
            caption = spec.pop("caption", "")
            paths = _render_dispatch(recipe, spec, out_path, palette)
            _write_caption(out_path, recipe, palette, caption, {})
            print(f"  ✓ [{i+1}/{len(manifest)}] {paths.get('png')}")
            ok += 1
        except Exception as e:  # noqa: BLE001
            failed.append((i, str(e)))
            print(f"  ✗ [{i+1}/{len(manifest)}] {e}")
    print(f"\nbatch: {ok}/{len(manifest)} rendered ({len(failed)} failed)")
    return 0 if not failed else 1


def validate(args) -> int:
    from consultant_kit import chart  # type: ignore
    spec = json.loads(Path(args.spec).read_text())
    findings = chart.validate_spec(spec)
    print(f"## chart-builder validate — {args.spec}")
    print()
    if not findings:
        print("✅ spec is valid")
        return 0
    severity_order = {"HIGH": 0, "MED": 1, "LOW": 2}
    findings.sort(key=lambda f: severity_order[f[0]])
    for sev, msg in findings:
        print(f"- **{sev}** — {msg}")
    high = sum(1 for s, _ in findings if s == "HIGH")
    return 1 if high else 0


def recipes(args) -> int:
    from consultant_kit.chart import RECIPES  # type: ignore
    for r in sorted(RECIPES):
        print(f"- {r}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="chart-builder")
    sub = p.add_subparsers(dest="cmd", required=True)

    # Shared annotation flags helper
    def _add_common(parser):
        parser.add_argument("--no-labels", action="store_true")
        parser.add_argument("--no-grid", action="store_true")
        parser.add_argument("--target", type=float, default=None)
        parser.add_argument("--baseline", type=float, default=None)
        parser.add_argument("--highlight", default=None,
                            help="series name to highlight (line) or label to highlight")
        parser.add_argument("--highlight-idx", type=int, default=None,
                            help="0-indexed bar to highlight (bar / dot-plot)")
        parser.add_argument("--accessible", action="store_true",
                            help="use Okabe-Ito color-blind-safe palette")
        parser.add_argument("--semantic", action="store_true",
                            help="positive=green, negative=primary accent (bar)")
        parser.add_argument("--currency", default="$",
                            help="currency symbol for $-formatted values")
        parser.add_argument("--palette", choices=("default", "dark"), default="default")
        parser.add_argument("--caption", default=None)

    r = sub.add_parser("render")
    r.add_argument("recipe", choices=("bar", "line", "stacked-bar", "waterfall",
                                      "grouped-bar", "dot-plot"))
    r.add_argument("--labels", required=True)
    r.add_argument("--values", default=None)
    r.add_argument("--series", default=None,
                   help="series_name=v1,v2,v3;next=v1,v2,v3 (line/stacked-bar/grouped-bar)")
    r.add_argument("--ylabel", default=None)
    r.add_argument("--xlabel", default=None)
    r.add_argument("--horizontal", action="store_true")
    r.add_argument("--start-label", default=None)
    r.add_argument("--end-label", default=None)
    r.add_argument("--dashed-after", type=int, default=None,
                   help="line: x-index after which series turns dashed (forecast)")
    r.add_argument("--no-sort", action="store_true", help="dot-plot: preserve input order")
    _add_common(r)
    r.add_argument("--out", required=True)
    r.set_defaults(func=render)

    s = sub.add_parser("render-spec")
    s.add_argument("spec")
    s.add_argument("--out", required=True)
    s.add_argument("--force", action="store_true",
                   help="render even with HIGH validation findings")
    s.set_defaults(func=render_spec)

    b = sub.add_parser("batch")
    b.add_argument("manifest")
    b.add_argument("--force", action="store_true")
    b.set_defaults(func=batch)

    v = sub.add_parser("validate")
    v.add_argument("spec")
    v.set_defaults(func=validate)

    rec = sub.add_parser("recipes")
    rec.set_defaults(func=recipes)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
