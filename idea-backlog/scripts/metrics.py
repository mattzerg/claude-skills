#!/usr/bin/python3
"""metrics: summarize idea-backlog usage telemetry.

Reads `_workdir/usage.jsonl` and prints an operator-friendly snapshot.
Default windows: last 7d / last 30d / lifetime. Used by the weekly digest
and ad-hoc audits.

Usage:
    metrics.py              # all three windows, terminal table
    metrics.py --json       # raw JSON for scripts
    metrics.py --window 7   # custom day window only
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

_LIB = Path(__file__).resolve().parent / "_lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from frontmatter import read_file  # noqa: E402
from idea_io import iter_all_ideas  # noqa: E402
from usage import read_events  # noqa: E402
from vault_paths import INBOX_DIR  # noqa: E402


def _parse_ts(rec: dict) -> dt.datetime | None:
    raw = rec.get("ts")
    if not raw:
        return None
    try:
        return dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def in_window(rec: dict, since: dt.datetime | None) -> bool:
    if since is None:
        return True
    ts = _parse_ts(rec)
    return ts is not None and ts >= since


def summarize(events: list[dict], since: dt.datetime | None) -> dict[str, Any]:
    in_win = [e for e in events if in_window(e, since)]
    by_event: Counter = Counter(e.get("event") for e in in_win)

    captures = [e for e in in_win if e.get("event") == "capture"]
    captures_by_cat = Counter(e.get("category") for e in captures)

    recalls = [e for e in in_win if e.get("event") == "recall"]
    recall_hits_idea = sum(int(e.get("idea_hits") or 0) for e in recalls)
    recall_hits_task = sum(int(e.get("task_hits") or 0) for e in recalls)
    recall_zero = sum(1 for e in recalls if not e.get("idea_hits") and not e.get("task_hits"))

    triage = [e for e in in_win if e.get("event") == "triage"]
    triage_by_action = Counter(e.get("action") for e in triage)

    suggests = [e for e in in_win if e.get("event") == "auto_suggest_fire"]

    extracts = [e for e in in_win if e.get("event") == "extract_run"]
    extract_cost = sum(float(e.get("cost_usd") or 0) for e in extracts)
    extract_ideas = sum(int(e.get("ideas_extracted") or 0) for e in extracts)

    return {
        "events_total": sum(by_event.values()),
        "by_event": dict(by_event),
        "captures": {
            "total": len(captures),
            "by_category": dict(captures_by_cat),
        },
        "recalls": {
            "total": len(recalls),
            "idea_hits_total": recall_hits_idea,
            "task_hits_total": recall_hits_task,
            "zero_hit_searches": recall_zero,
            "median_idea_hits": (sorted([int(e.get("idea_hits") or 0) for e in recalls])[len(recalls) // 2] if recalls else 0),
        },
        "triage": {
            "total": len(triage),
            "by_action": dict(triage_by_action),
            "kill_rate": (triage_by_action.get("kill", 0) / len(triage)) if triage else 0.0,
        },
        "auto_suggests": {
            "total": len(suggests),
            "topics": Counter(e.get("topic") for e in suggests).most_common(5),
        },
        "extract_runs": {
            "count": len(extracts),
            "total_cost_usd": round(extract_cost, 2),
            "ideas_extracted": extract_ideas,
        },
    }


def current_state() -> dict[str, Any]:
    """Snapshot of the backlog right now (independent of usage events)."""
    today = dt.date.today()
    by_cat: Counter = Counter()
    by_status: Counter = Counter()
    by_conviction: Counter = Counter()
    idle_count = 0
    inbox_count = 0
    if INBOX_DIR.exists():
        inbox_count = sum(1 for _ in INBOX_DIR.rglob("*.md"))
    for p in iter_all_ideas(include_inbox=False, include_archive=False):
        try:
            meta, _ = read_file(p)
        except Exception:
            continue
        by_cat[meta.get("category") or "?"] += 1
        by_status[meta.get("status") or "?"] += 1
        by_conviction[meta.get("conviction") or "?"] += 1
        try:
            lt = dt.date.fromisoformat(meta.get("last_touched") or meta.get("created"))
            if meta.get("status") == "active" and (today - lt).days >= 90:
                idle_count += 1
        except Exception:
            pass
    return {
        "active_count": sum(by_cat.values()),
        "by_category": dict(by_cat),
        "by_status": dict(by_status),
        "by_conviction": dict(by_conviction),
        "idle_90d_active": idle_count,
        "inbox_pending": inbox_count,
    }


def render_table(label: str, summary: dict, *, full: bool = True) -> str:
    lines = [f"## {label}"]
    lines.append(f"  events: {summary['events_total']}")
    if summary["captures"]["total"]:
        lines.append(f"  captures: {summary['captures']['total']}  "
                     f"({', '.join(f'{k}:{v}' for k, v in summary['captures']['by_category'].items())})")
    if summary["recalls"]["total"]:
        r = summary["recalls"]
        lines.append(f"  recalls: {r['total']}  "
                     f"avg ideas/q={r['idea_hits_total']/r['total']:.1f}  "
                     f"zero-hit={r['zero_hit_searches']}")
    if summary["triage"]["total"]:
        t = summary["triage"]
        lines.append(f"  triage: {t['total']}  "
                     f"({', '.join(f'{k}:{v}' for k, v in t['by_action'].items())})  "
                     f"kill-rate={t['kill_rate']:.0%}")
    if summary["auto_suggests"]["total"]:
        s = summary["auto_suggests"]
        topics = ", ".join(f"{t}({c})" for t, c in s["topics"])
        lines.append(f"  auto-suggests: {s['total']}  top: {topics}")
    if summary["extract_runs"]["count"]:
        e = summary["extract_runs"]
        lines.append(f"  extract runs: {e['count']}  cost=${e['total_cost_usd']:.2f}  ideas={e['ideas_extracted']}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=None, help="single window in days (overrides default 7/30/lifetime)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    events = read_events()
    now = dt.datetime.now(dt.timezone.utc)

    if args.window:
        windows = [(f"last {args.window}d", now - dt.timedelta(days=args.window))]
    else:
        windows = [
            ("last 7 days", now - dt.timedelta(days=7)),
            ("last 30 days", now - dt.timedelta(days=30)),
            ("lifetime", None),
        ]

    state = current_state()

    if args.json:
        out = {
            "current_state": state,
            "windows": {label: summarize(events, since) for label, since in windows},
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    print("# idea-backlog metrics\n")
    print("## current state")
    print(f"  active ideas: {state['active_count']}")
    print(f"  by category: {state['by_category']}")
    print(f"  by status: {state['by_status']}")
    print(f"  by conviction: {state['by_conviction']}")
    print(f"  idle 90+d (active): {state['idle_90d_active']}")
    print(f"  inbox pending: {state['inbox_pending']}")
    print()
    for label, since in windows:
        print(render_table(label, summarize(events, since)))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
