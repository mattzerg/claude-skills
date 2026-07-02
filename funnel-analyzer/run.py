#!/usr/bin/env python3
"""Funnel analyzer — measured conversion rates per funnel step.

Usage:
    python3 ~/.claude/skills/funnel-analyzer/run.py define \\
        --name <funnel> --product <slug> \\
        --steps "event_type:event_name,event_type:event_name,..."
    python3 ~/.claude/skills/funnel-analyzer/run.py bind --product <slug>
    python3 ~/.claude/skills/funnel-analyzer/run.py query --name <funnel> [--days N]
    python3 ~/.claude/skills/funnel-analyzer/run.py compare --name <funnel> --segment <field> [--days N]
    python3 ~/.claude/skills/funnel-analyzer/run.py top-friction [--days N]
    python3 ~/.claude/skills/funnel-analyzer/run.py list

Phase 1: stub-mode supports JSON fixture at funnels/<name>/_fixture.json for development.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

try:
    import yaml as _yaml
except ImportError:
    _yaml = None

# Override with $ZERG_VAULT for non-author runs (S2 from fakeidan review).
DEFAULT_VAULT = "/Users/mattheweisner/Obsidian/Zerg/MattZerg"
VAULT = Path(os.environ.get("ZERG_VAULT", DEFAULT_VAULT))
GROWTH_DIR = VAULT / "Projects" / "Zerg-Production" / "Growth"
FUNNELS_DIR = GROWTH_DIR / "funnels"
RUNS_DIR = FUNNELS_DIR / "_runs"
MEASUREMENT_DIR = GROWTH_DIR / "measurement"
FUNNEL_TEMPLATE = FUNNELS_DIR / "_template.yaml"
USER_EDITS_MARKER = "# --- user edits below ---"

VALID_DATA_SOURCES = ("api", "postgres", "stripe", "fixture")
DEFAULT_FRICTION = 0.50
TOP_FRICTION_MIN_HEAD = 100


def parse_yaml_funnel(text: str) -> dict:
    """Parse a funnel YAML file. Naive parser — no nested types beyond list-of-dicts for steps."""
    if not text.startswith("---\n"):
        raise ValueError("funnel YAML must start with --- frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        end = text.rfind("---")
        if end < 0:
            raise ValueError("funnel YAML missing closing ---")
    fm = text[4:end] if text[4:end].strip() else text[4:]
    out: dict = {"steps": []}
    cur_step: dict | None = None
    in_steps = False
    for line in fm.splitlines():
        if not line.strip():
            continue
        if line.rstrip() == "steps:":
            in_steps = True
            continue
        if in_steps:
            stripped = line.lstrip()
            if line.startswith("  - "):
                if cur_step is not None:
                    out["steps"].append(cur_step)
                cur_step = {}
                rest = line[4:]
                if ":" in rest:
                    k, _, v = rest.partition(":")
                    cur_step[k.strip()] = v.strip().strip('"')
            elif line.startswith("    ") and cur_step is not None:
                k, _, v = stripped.partition(":")
                cur_step[k.strip()] = v.strip().strip('"')
            else:
                # Ended steps block
                if cur_step is not None:
                    out["steps"].append(cur_step)
                    cur_step = None
                in_steps = False
                if ":" in line:
                    k, _, v = line.partition(":")
                    out[k.strip()] = v.strip().strip('"')
        else:
            if ":" in line:
                k, _, v = line.partition(":")
                out[k.strip()] = v.strip().strip('"')
    if cur_step is not None:
        out["steps"].append(cur_step)
    return out


def render_funnel_yaml(meta: dict) -> str:
    lines = ["---"]
    for k, v in meta.items():
        if k == "steps":
            continue
        lines.append(f"{k}: {v}")
    lines.append("steps:")
    for step in meta.get("steps", []):
        first = True
        for sk, sv in step.items():
            prefix = "  - " if first else "    "
            lines.append(f"{prefix}{sk}: {sv}")
            first = False
    lines.append("---")
    return "\n".join(lines) + "\n"


def funnel_path(name: str) -> Path:
    return FUNNELS_DIR / f"{name}.yaml"


def cmd_define(args: argparse.Namespace) -> int:
    if not re.match(r"^[a-z0-9][a-z0-9-]+$", args.name):
        print("ERROR: --name must be lowercase alphanumeric + hyphens", file=sys.stderr)
        return 1
    f = funnel_path(args.name)
    if f.exists():
        print(f"ERROR: funnel {args.name!r} already exists at {f}", file=sys.stderr)
        return 1
    steps = []
    for i, raw in enumerate(args.steps.split(","), 1):
        raw = raw.strip()
        if ":" not in raw:
            print(f"ERROR: step {i} {raw!r} must be 'event_type:event_name'", file=sys.stderr)
            return 1
        et_, _, en = raw.partition(":")
        steps.append({
            "id": f"step-{i}",
            "event_type": et_.strip(),
            "event_name": en.strip(),
        })
    if len(steps) < 2:
        print("ERROR: funnel needs at least 2 steps", file=sys.stderr)
        return 1
    meta = {
        "name": args.name,
        "product": args.product,
        "data_source": args.data_source,
        "default_days": str(args.default_days),
        "friction_threshold": str(DEFAULT_FRICTION),
        "steps": steps,
    }
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(render_funnel_yaml(meta))
    print(f"Defined funnel {args.name!r} with {len(steps)} steps at {f}")
    print(f"Data source: {args.data_source}. Run query with: --name {args.name} [--days N]")
    return 0


def _load_funnel(name: str) -> dict:
    f = funnel_path(name)
    if not f.exists():
        raise FileNotFoundError(f"funnel {name!r} not defined; run `define` first")
    return parse_yaml_funnel(f.read_text())


def _query_data(funnel: dict, days: int, segment: str | None = None) -> dict:
    """Returns {(segment_value or None) → [step_count, step_count, ...]}."""
    src = funnel.get("data_source", "fixture")
    name = funnel["name"]

    if src == "fixture":
        return _query_fixture(name, len(funnel["steps"]), segment)
    if src == "api":
        url = os.environ.get("ZERGALYTICS_API_URL")
        if not url:
            raise RuntimeError(
                f"funnel {name!r} declares data_source: api but ZERGALYTICS_API_URL is unset. "
                "Wire the API or change to data_source: fixture for development."
            )
        return _query_api(url, funnel, days, segment)
    if src == "postgres":
        raise NotImplementedError(
            "data_source: postgres not yet wired (Phase 2). Use api or fixture for now."
        )
    if src == "stripe":
        raise NotImplementedError(
            "data_source: stripe not yet wired (waits on revenue plumbing)."
        )
    raise ValueError(f"unknown data_source: {src!r}")


def _query_fixture(name: str, n_steps: int, segment: str | None) -> dict:
    fpath = FUNNELS_DIR / name / "_fixture.json"
    if not fpath.exists():
        raise FileNotFoundError(
            f"fixture not found at {fpath}. Create it or change data_source. "
            f'Format: {{"counts": [N1, N2, ...], "segments": {{"v1": [...], "v2": [...]}}}}'
        )
    data = json.loads(fpath.read_text())
    if segment:
        seg_data = data.get("segments", {}).get(segment, {})
        return {k: v for k, v in seg_data.items()}
    counts = data.get("counts", [])
    if len(counts) != n_steps:
        raise ValueError(
            f"fixture has {len(counts)} step counts but funnel has {n_steps} steps"
        )
    return {None: counts}


def _query_api(url: str, funnel: dict, days: int, segment: str | None) -> dict:
    """Query Zergalytics API for step counts. Returns {segment_value: [counts]}."""
    payload = {
        "funnel": funnel["name"],
        "days": days,
        "steps": funnel["steps"],
        "segment": segment,
    }
    req = urllib.request.Request(
        f"{url.rstrip('/')}/api/funnels/query",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        raise RuntimeError(f"API call failed: {e}")
    return data.get("results", {})


def _format_funnel_table(funnel: dict, counts: list) -> tuple[str, dict]:
    """Returns (markdown_table, friction_summary)."""
    if not counts:
        return "(no data)\n", {"top_friction": None}
    head = counts[0] or 1
    rows = ["| Step | Count | Cum % | Step % | Drop |", "|---|---|---|---|---|"]
    friction_threshold = float(funnel.get("friction_threshold", DEFAULT_FRICTION))
    top_friction = None
    top_drop = -1.0
    for i, step in enumerate(funnel["steps"]):
        n = counts[i]
        cum_pct = 100.0 * n / head if head else 0.0
        step_pct = 100.0 * n / counts[i - 1] if i > 0 and counts[i - 1] else 100.0
        drop_pct = 100.0 - step_pct if i > 0 else 0.0
        bar = "▓" * int(drop_pct / 5) if i > 0 else ""
        label = f"{step.get('event_type','?')}:{step.get('event_name','') or '*'}"
        if i == 0:
            rows.append(f"| {label} | {n:,} | {cum_pct:.1f}% | — | — |")
        else:
            mark = " ⚠️" if drop_pct / 100.0 >= friction_threshold else ""
            rows.append(f"| {label} | {n:,} | {cum_pct:.1f}% | {step_pct:.1f}% | {drop_pct:.1f}% {bar}{mark} |")
            if drop_pct / 100.0 >= friction_threshold and drop_pct > top_drop:
                top_drop = drop_pct
                prev = funnel["steps"][i - 1]
                top_friction = {
                    "from_step": f"{prev.get('event_type')}:{prev.get('event_name','') or '*'}",
                    "to_step": label,
                    "drop_pct": drop_pct,
                }
    return "\n".join(rows) + "\n", {"top_friction": top_friction}


def cmd_query(args: argparse.Namespace) -> int:
    try:
        funnel = _load_funnel(args.name)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    days = args.days or int(funnel.get("default_days", 30))
    try:
        result = _query_data(funnel, days)
    except (FileNotFoundError, RuntimeError, NotImplementedError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    counts = result.get(None, [])
    if not counts:
        print(f"(no data for funnel {args.name!r} over last {days} days)")
        return 0

    today = dt.date.today().isoformat()
    title = f"# {args.name} funnel — last {days} days ({today})\n"
    table, summary = _format_funnel_table(funnel, counts)
    output = title + "\n" + table
    if summary["top_friction"]:
        tf = summary["top_friction"]
        output += (
            f"\n**Top friction:** {tf['from_step']} → {tf['to_step']} "
            f"({tf['drop_pct']:.1f}% drop).\n"
            f"**Next:** run `cro-auditor` on the source step, then `experiment-designer` "
            f"to draft a treatment.\n"
        )
    print(output)

    # Persist run record
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUNS_DIR / f"{args.name}-{today}.md"
    run_path.write_text(output)
    print(f"\n(saved run record to {run_path})", file=sys.stderr)
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    try:
        funnel = _load_funnel(args.name)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    days = args.days or int(funnel.get("default_days", 30))
    try:
        result = _query_data(funnel, days, segment=args.segment)
    except (FileNotFoundError, RuntimeError, NotImplementedError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    if not result:
        print(f"(no data for funnel {args.name!r} segmented by {args.segment} over {days} days)")
        return 0
    print(f"# {args.name} funnel — segmented by {args.segment} (last {days} days)\n")
    for seg_value, counts in result.items():
        print(f"\n## Segment: {seg_value}\n")
        table, _ = _format_funnel_table(funnel, counts)
        print(table)
    return 0


def cmd_top_friction(args: argparse.Namespace) -> int:
    if not FUNNELS_DIR.exists():
        print("(no funnels defined)")
        return 0
    findings = []
    for f in sorted(FUNNELS_DIR.glob("*.yaml")):
        try:
            funnel = parse_yaml_funnel(f.read_text())
        except ValueError:
            continue
        days = args.days or int(funnel.get("default_days", 30))
        try:
            result = _query_data(funnel, days)
        except Exception:
            continue
        counts = result.get(None, [])
        if not counts or counts[0] < TOP_FRICTION_MIN_HEAD:
            continue
        _, summary = _format_funnel_table(funnel, counts)
        if summary["top_friction"]:
            tf = summary["top_friction"]
            head = counts[0]
            findings.append({
                "funnel": funnel["name"],
                "from": tf["from_step"],
                "to": tf["to_step"],
                "drop_pct": tf["drop_pct"],
                "head": head,
                "score": tf["drop_pct"] * head,  # weighted by volume
            })
    if not findings:
        print(f"(no funnels with ≥ {TOP_FRICTION_MIN_HEAD} head events have friction)")
        return 0
    findings.sort(key=lambda f: -f["score"])
    print(f"# Top friction across all funnels (last {args.days} days)\n")
    print("| Funnel | Step | Drop | Head N |")
    print("|---|---|---|---|")
    for f in findings[:10]:
        print(f"| {f['funnel']} | {f['from']} → {f['to']} | {f['drop_pct']:.1f}% | {f['head']:,} |")
    return 0


def _hash_block(obj) -> str:
    payload = json.dumps(obj, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _render_steps_yaml(steps: list, slug: str) -> list[str]:
    lines = ["steps:"]
    for step in steps:
        lines.append(f"  - {{ event: {step}, label: \"{step.replace('_', ' ').strip().capitalize()}\" }}")
    if steps:
        lines.append(f"\nsuccess_step: {steps[-1]}")
    return lines


def _split_at_marker(text: str) -> tuple[str, str | None]:
    if USER_EDITS_MARKER in text:
        head, _, tail = text.partition(USER_EDITS_MARKER)
        return head, USER_EDITS_MARKER + tail
    return text, None


def _read_existing_hash(text: str) -> str | None:
    m = re.search(r"^#\s*generated_hash:\s*([0-9a-f]+)\s*$", text, re.MULTILINE)
    return m.group(1) if m else None


def cmd_bind(args: argparse.Namespace) -> int:
    if _yaml is None:
        print("ERROR: PyYAML required for `bind` (pip install pyyaml)", file=sys.stderr)
        return 2
    slug = args.product
    src = MEASUREMENT_DIR / f"{slug}.yaml"
    if not src.exists():
        print(f"ERROR: measurement spec not found at {src}", file=sys.stderr)
        return 1
    try:
        with src.open() as f:
            spec = _yaml.safe_load(f) or {}
    except _yaml.YAMLError as e:
        print(f"ERROR: failed to parse {src}: {e}", file=sys.stderr)
        return 2
    funnels = spec.get("funnels") or {}
    if not isinstance(funnels, dict) or not funnels:
        print(f"ERROR: no `funnels:` block found in {src}", file=sys.stderr)
        return 2

    FUNNELS_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    skipped: list[Path] = []
    updated: list[Path] = []

    for funnel_name, steps in funnels.items():
        if not isinstance(steps, list) or not steps:
            print(f"WARN: funnel {funnel_name!r} has no steps; skipping")
            continue
        steps = [str(s) for s in steps]
        target = FUNNELS_DIR / f"{slug}-{funnel_name}.yaml"
        block_hash = _hash_block({"funnel": funnel_name, "steps": steps})

        header_lines = [
            f"# generated_hash: {block_hash}",
            f"# Source: measurement/{slug}.yaml funnels.{funnel_name}",
            f"# Regenerate via: python3 ~/.claude/skills/funnel-analyzer/run.py bind --product {slug}",
            "",
            f"product: {slug}",
            f"funnel_name: {funnel_name}",
            "data_source: zerglytics",
            "window_days: 7",
            "",
        ]
        header_lines.extend(_render_steps_yaml(steps, slug))
        header_lines.append("")
        header_lines.append(f"notes: |")
        header_lines.append(f"  Generated from measurement/{slug}.yaml funnels.{funnel_name}.")
        header_lines.append(f"  Hand-edits below the marker are preserved on regeneration.")
        header_lines.append("")
        header_lines.append(USER_EDITS_MARKER)
        header_lines.append("")
        generated_body = "\n".join(header_lines)

        if target.exists():
            existing = target.read_text()
            existing_hash = _read_existing_hash(existing)
            if existing_hash == block_hash:
                skipped.append(target)
                continue
            _, user_tail = _split_at_marker(existing)
            if user_tail is not None:
                target.write_text(generated_body + user_tail.split(USER_EDITS_MARKER, 1)[1].lstrip("\n"))
            else:
                target.write_text(generated_body)
            updated.append(target)
        else:
            target.write_text(generated_body)
            written.append(target)

    print(f"Source: {src}")
    print(f"Funnels processed: {len(funnels)}")
    if written:
        print(f"Written ({len(written)}):")
        for p in written:
            print(f"  + {p}")
    if updated:
        print(f"Updated — hash mismatch ({len(updated)}):")
        for p in updated:
            print(f"  ~ {p}")
    if skipped:
        print(f"Skipped — already current ({len(skipped)}):")
        for p in skipped:
            print(f"  = {p}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    if not FUNNELS_DIR.exists() or not list(FUNNELS_DIR.glob("*.yaml")):
        print("(no funnels defined)")
        return 0
    print("| Name | Product | Source | Steps |")
    print("|---|---|---|---|")
    for f in sorted(FUNNELS_DIR.glob("*.yaml")):
        try:
            funnel = parse_yaml_funnel(f.read_text())
            print(f"| {funnel.get('name','?')} | {funnel.get('product','?')} | "
                  f"{funnel.get('data_source','?')} | {len(funnel.get('steps', []))} |")
        except Exception as e:
            print(f"| {f.stem} | (parse error: {e}) | | |")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="funnel-analyzer", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    pd = sub.add_parser("define", help="scaffold a new funnel YAML")
    pd.add_argument("--name", required=True)
    pd.add_argument("--product", required=True)
    pd.add_argument("--steps", required=True,
                    help="comma-separated 'event_type:event_name' pairs (≥2)")
    pd.add_argument("--data-source", dest="data_source", default="fixture",
                    choices=VALID_DATA_SOURCES)
    pd.add_argument("--default-days", dest="default_days", type=int, default=30)
    pd.set_defaults(func=cmd_define)

    pq = sub.add_parser("query", help="measured drop-off table")
    pq.add_argument("--name", required=True)
    pq.add_argument("--days", type=int)
    pq.set_defaults(func=cmd_query)

    pc = sub.add_parser("compare", help="segmented cuts")
    pc.add_argument("--name", required=True)
    pc.add_argument("--segment", required=True,
                    help="utm_source | utm_medium | utm_campaign | plan | cohort")
    pc.add_argument("--days", type=int)
    pc.set_defaults(func=cmd_compare)

    pt = sub.add_parser("top-friction", help="worst step across funnels")
    pt.add_argument("--days", type=int, default=7)
    pt.set_defaults(func=cmd_top_friction)

    pb = sub.add_parser("bind", help="render per-funnel YAMLs from measurement/<slug>.yaml")
    pb.add_argument("--product", required=True)
    pb.set_defaults(func=cmd_bind)

    pl = sub.add_parser("list", help="list defined funnels")
    pl.set_defaults(func=cmd_list)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
