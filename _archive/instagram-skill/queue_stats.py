#!/usr/bin/env python3
"""
queue_stats.py — distribution histogram over the Detroit-hub queue.

Usage:
    queue_stats.py [--queue PATH]

Prints item counts by day / venue / pattern / state / surface / posture.
Read-only.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from datetime import datetime, date
from pathlib import Path

VAULT = Path.home() / "Obsidian/Zerg"
QUEUE_DIR = VAULT / "MattZerg/Projects/detroit-hub/queue"


def parse_fm(path: Path) -> dict | None:
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not m:
        return None
    fm = {}
    for line in m.group(1).split("\n"):
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    body = m.group(2)
    vm = re.search(r"^Venue:\s*(.+)$", body, re.MULTILINE)
    if vm:
        fm["_venue"] = vm.group(1).strip()
    return fm


def bar(n: int, total: int, width: int = 30) -> str:
    if total == 0:
        return ""
    filled = round((n / total) * width)
    return "█" * filled + "·" * (width - filled)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--queue", type=Path, default=QUEUE_DIR)
    args = p.parse_args()

    files = sorted(args.queue.glob("*.md"))
    files = [f for f in files if not f.name.startswith("_")]

    items: list[dict] = []
    for f in files:
        fm = parse_fm(f)
        if not fm:
            continue
        items.append(fm)

    print(f"Queue: {args.queue}")
    print(f"Total items: {len(items)}")
    print()

    # By state
    states = Counter(i.get("state", "?") for i in items)
    print("=== STATE ===")
    for k, n in states.most_common():
        print(f"  {n:4} {bar(n, len(items)):30} {k}")
    print()

    # By surface
    surfaces = Counter(i.get("surface", "?") for i in items)
    print("=== SURFACE ===")
    for k, n in surfaces.most_common():
        print(f"  {n:4} {bar(n, len(items)):30} {k}")
    print()

    # By pattern
    patterns = Counter(i.get("pattern", "?") for i in items)
    print("=== PATTERN ===")
    pattern_names = {"A": "Index-Card", "B": "One Sharp Line", "C": "Year+Venue+Vibe",
                     "D": "Deadpan", "E": "Reframe/OpEd", "F": "Knowing Aside",
                     "F_short": "Knowing Aside (short)", "A_carousel": "Index-Card (carousel)"}
    for k, n in patterns.most_common():
        label = pattern_names.get(k, k)
        print(f"  {n:4} {bar(n, len(items)):30} {k} — {label}")
    print()

    # By copyright posture
    postures = Counter(i.get("copyright_posture", "?") for i in items)
    print("=== COPYRIGHT POSTURE ===")
    for k, n in postures.most_common():
        print(f"  {n:4} {bar(n, len(items)):30} {k}")
    print()

    # By day
    days: dict[date, int] = {}
    for i in items:
        try:
            d = datetime.strptime(i.get("scheduled", "")[:10], "%Y-%m-%d").date()
            days[d] = days.get(d, 0) + 1
        except Exception:
            continue
    print("=== BY DAY (next 14 sched) ===")
    max_day = max(days.values()) if days else 1
    DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    for d in sorted(days.keys())[:14]:
        n = days[d]
        weekday = DAY_NAMES[d.weekday()]
        print(f"  {n:4} {bar(n, max_day):30} {weekday} {d.strftime('%b %d')}")
    print()

    # Top venues
    venues = Counter(i.get("_venue", "(unknown)") for i in items)
    print("=== TOP 15 VENUES ===")
    for k, n in venues.most_common(15):
        print(f"  {n:4} {bar(n, max(venues.values())):30} {k}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
