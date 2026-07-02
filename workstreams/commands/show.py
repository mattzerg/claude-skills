#!/usr/bin/env python3
"""show — render the workstreams dashboard.

Usage:
  show.py                    # all non-empty workstreams
  show.py hot                # filter to hot bucket
  show.py stale              # filter to stale bucket
  show.py parked             # filter to parked bucket
  show.py all                # include empty workstreams
  show.py catchall           # only the catchall workstream
  show.py <ws-id>            # drill into one workstream (full items)
  show.py --refresh          # re-run collect first
  show.py --json             # raw state.json to stdout
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


WORKSTREAMS_DIR = Path.home() / ".claude" / "workstreams"
STATE_PATH = WORKSTREAMS_DIR / "state.json"
COLLECT = WORKSTREAMS_DIR / "collect.py"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="render workstreams dashboard")
    parser.add_argument("filter", nargs="?", default="", help="hot|warm|stale|parked|empty|all|catchall|<ws-id>")
    parser.add_argument("--refresh", action="store_true", help="run collect.py first")
    parser.add_argument("--json", action="store_true", help="print raw state.json")
    args = parser.parse_args(argv)

    sys.path.insert(0, str(WORKSTREAMS_DIR.parent))
    from workstreams import render

    if args.refresh or not STATE_PATH.exists():
        rc = subprocess.call(["/usr/bin/python3", str(COLLECT)])
        if rc != 0:
            return rc

    state = render.load_state(STATE_PATH)

    if args.json:
        print(json.dumps(state, indent=2, default=str))
        return 0

    f = args.filter.lower()
    show_empty = False
    show_other = True
    filter_buckets = None

    if f == "all":
        show_empty = True
    elif f == "catchall":
        # Drill straight into catchall.
        catchall = next(w for w in state["workstreams"].values() if w["catchall"])
        print(_drill(catchall, state))
        return 0
    elif f in {"hot", "warm", "stale", "parked", "empty", "shipped", "blocked"}:
        filter_buckets = [f]
        if f == "empty":
            show_empty = True
    elif f and f in state["workstreams"]:
        ws = state["workstreams"][f]
        print(_drill(ws, state))
        return 0
    elif f:
        print(f"unknown filter or workstream id: {f}", file=sys.stderr)
        print(f"  known workstreams: {', '.join(state['workstreams'].keys())}", file=sys.stderr)
        return 1

    print(render.render(
        state,
        filter_buckets=filter_buckets,
        show_empty=show_empty,
        show_other=show_other,
    ))
    return 0


def _age_str(ts, now: float) -> str:
    if not ts:
        return "—"
    if isinstance(ts, str):
        try:
            ts = float(ts)
        except ValueError:
            return "—"
    delta = now - ts
    if delta < 60:
        return "now"
    if delta < 3600:
        return f"{int(delta / 60)}m"
    if delta < 86400:
        return f"{int(delta / 3600)}h"
    return f"{int(delta / 86400)}d"


def _drill(ws: dict, state: dict) -> str:
    """Full per-workstream view: every item, no truncation."""
    now = time.time()
    lines = [
        f"{'═' * 80}",
        f"{ws['name']}  [{ws['scope']}/{ws['status']}/{ws['bucket']}]",
        f"id: {ws['id']}   last_touched: {_age_str(ws.get('last_touched'), now)} ago",
    ]
    if ws.get("notes"):
        lines.append(f"note: {ws['notes']}")
    pref = ws.get("session_pref") or {}
    if pref.get("preferred_name") or pref.get("cwd"):
        lines.append(f"session: name={pref.get('preferred_name') or '—'}  cwd={pref.get('cwd') or '—'}")
    lines.append("─" * 80)

    c = ws["counts"]
    if c["pr"]:
        lines.append(f"OPEN PRS ({c['pr']}):")
        for it in ws["items"]["pr"]:
            e = it["extras"]
            age = _age_str(it.get("last_touched"), now)
            lines.append(f"  {e.get('repo')}#{e.get('number')} · {age} · {it['title']}")
            if it.get("url"):
                lines.append(f"    {it['url']}")
    if c["inbox"]:
        lines.append(f"\nINBOX ({c['inbox']}):")
        for it in ws["items"]["inbox"]:
            e = it["extras"]
            lines.append(f"  [{e.get('bucket', '?')[:20]}] {it['title']}")
            if e.get("domain") or e.get("why_now"):
                lines.append(f"    domain={e.get('domain') or '—'}  why_now={e.get('why_now') or '—'}")
    if c["idea"]:
        lines.append(f"\nIDEAS ({c['idea']}):")
        for it in ws["items"]["idea"]:
            e = it["extras"]
            lines.append(f"  {it['title']}  (cat={e.get('category') or '?'}, status={e.get('status') or '?'})")
    if c["session"]:
        lines.append(f"\nSESSIONS ({c['session']}):")
        for it in ws["items"]["session"]:
            e = it["extras"]
            alive = "alive" if e.get("alive") else "dead"
            age = _age_str(it.get("last_touched"), now)
            lines.append(f"  pid={e.get('pid')} ({alive}) · {age} · {it['title']}")
            if e.get("cwd"):
                lines.append(f"    cwd={e['cwd']}")
    if ws.get("folder_activity"):
        active = [(rel, info) for rel, info in ws["folder_activity"].items()
                  if info.get("file_count_recent")]
        if active:
            lines.append(f"\nVAULT FOLDERS (recent file count):")
            for rel, info in active:
                age = _age_str(info.get("last_touched"), now)
                lines.append(f"  {rel}: {info['file_count_recent']} files in last 30d, last touched {age} ago")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
