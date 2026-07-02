#!/usr/bin/env python3
"""workplan-skill — Gantt-style timeline with milestones + critical path."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".claude/skills/_consultant/python"))
from _bootstrap_helper import ensure_venv  # noqa: E402

ensure_venv(__file__)

import argparse  # noqa: E402
import datetime as _dt  # noqa: E402
import json  # noqa: E402


SCAFFOLD_BODY = """## Workplan

| ID | Task | Owner | Start | End | Depends on | Milestone |
|---|---|---|---|---|---|---|
| T1 | _[task]_ | _[owner]_ | YYYY-MM-DD | YYYY-MM-DD | — | no |

## Critical path

_[run `render` with a spec.json to auto-mark]_

## Notes

- IDs T1/T2/T3 — referenced by dependencies.
- Milestones = decision/handover points (true/false).
- Owner: one person per row.
- Re-render after edits to refresh the Gantt chart.
- Anchored on `MattZerg/_style/consultant_thinking_style.md`.
"""


def scaffold(args) -> int:
    from consultant_kit import frontmatter, io  # type: ignore

    fm = frontmatter.envelope(
        engagement=args.engagement,
        slug=f"{io.slugify(args.engagement)}-workplan",
        skill="workplan-skill",
        inputs=[],
        extra={"mode": args.mode or "ops"},
    )
    out_root = io.engagement_dir(args.engagement, args.mode or "ops")
    out_root.mkdir(parents=True, exist_ok=True)
    out_path = out_root / "07-workplan.md"
    frontmatter.write_md(out_path, fm, SCAFFOLD_BODY)
    print(f"wrote {out_path}")
    return 0


def _critical_path(tasks: list[dict]) -> list[str]:
    """Simple longest-path by date duration through DAG."""
    by_id = {t["id"]: t for t in tasks}
    memo: dict[str, tuple[int, list[str]]] = {}

    def walk(tid: str) -> tuple[int, list[str]]:
        if tid in memo:
            return memo[tid]
        t = by_id.get(tid)
        if not t:
            return 0, []
        dur = (_dt.date.fromisoformat(t["end"]) - _dt.date.fromisoformat(t["start"])).days + 1
        best_depth = 0
        best_path: list[str] = []
        for dep in t.get("depends_on", []) or []:
            d, path = walk(dep)
            if d > best_depth:
                best_depth, best_path = d, path
        result = (dur + best_depth, best_path + [tid])
        memo[tid] = result
        return result

    best = (0, [])
    for t in tasks:
        d, path = walk(t["id"])
        if d > best[0]:
            best = (d, path)
    return best[1]


def render(args) -> int:
    from consultant_kit import chart, frontmatter, io  # type: ignore

    spec = json.loads(Path(args.spec).read_text())
    tasks = spec["tasks"]
    if not tasks:
        print("ERROR: no tasks in spec")
        return 1

    crit = _critical_path(tasks)

    # Render Gantt as horizontal bar (start = position, end-start = length)
    starts = [_dt.date.fromisoformat(t["start"]) for t in tasks]
    ends = [_dt.date.fromisoformat(t["end"]) for t in tasks]
    earliest = min(starts)
    days_offset = [(s - earliest).days for s in starts]
    durations = [(e - s).days + 1 for s, e in zip(starts, ends)]

    # Use matplotlib directly for a real Gantt (offset bars)
    import matplotlib  # type: ignore
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # type: ignore
    from consultant_kit import brand  # type: ignore

    palette = brand.get("default")
    plt.rcParams.update(brand.matplotlib_rcparams("default"))
    fig, ax = plt.subplots(figsize=(10, max(3, 0.45 * len(tasks) + 1)))
    labels = []
    for i, t in enumerate(tasks):
        color = palette.accent_primary if t["id"] in crit else palette.mid_gray
        if t.get("milestone"):
            color = palette.accent_secondary_dark
        ax.barh(i, durations[i], left=days_offset[i], color=color, edgecolor="none", height=0.6)
        labels.append(f"{t['id']} {t['name']} ({t.get('owner','')})")
    ax.set_yticks(range(len(tasks)))
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel(f"Days from {earliest.isoformat()}")

    engagement = args.engagement
    mode = args.mode or "ops"
    out_root = io.engagement_dir(engagement, mode)
    charts_dir = out_root / "05-analysis/charts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    chart_path = charts_dir / "workplan-gantt.png"
    fig.tight_layout()
    fig.savefig(chart_path, facecolor=palette.paper, bbox_inches="tight")
    plt.close(fig)

    body = ["## Workplan", "",
            "| ID | Task | Owner | Start | End | Depends on | Milestone | Critical |",
            "|---|---|---|---|---|---|---|---|"]
    for t in tasks:
        body.append(
            f"| {t['id']} | {t['name']} | {t.get('owner','—')} | {t['start']} | {t['end']} | {', '.join(t.get('depends_on', []) or []) or '—'} | {'yes' if t.get('milestone') else 'no'} | {'**yes**' if t['id'] in crit else 'no'} |"
        )
    body.append("")
    body.append(f"## Critical path: {' → '.join(crit)}")
    body.append("")
    body.append(f"## Gantt: `{chart_path}`")

    fm = frontmatter.envelope(
        engagement=engagement,
        slug=f"{io.slugify(engagement)}-workplan",
        skill="workplan-skill",
        inputs=[args.spec],
        upstream=[],
        extra={"mode": mode, "critical_path": crit, "tasks": tasks},
    )
    out_path = out_root / "07-workplan.md"
    frontmatter.write_md(out_path, fm, "\n".join(body))
    print(f"wrote {out_path}")
    print(f"wrote {chart_path}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="workplan-skill")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scaffold")
    s.add_argument("--engagement", required=True)
    s.add_argument("--mode", choices=("client", "pm", "ops", "life"), default=None)
    s.set_defaults(func=scaffold)

    r = sub.add_parser("render")
    r.add_argument("spec")
    r.add_argument("--engagement", required=True)
    r.add_argument("--mode", choices=("client", "pm", "ops", "life"), default=None)
    r.set_defaults(func=render)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
