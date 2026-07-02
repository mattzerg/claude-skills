#!/usr/bin/python3
"""browse: terminal version of the Dataview dashboard.

Six panels, same as `Ideas/README.md`:
  --top         🔥 high-conviction active ideas (default)
  --fresh       🌱 captured in last 14 days
  --idle        💤 active and idle 90+ days
  --by-category 📊 counts per category
  --tags        🏷️ top tags
  --inbox       📥 inbox queue
  --all         all six panels at once

Each line shows one idea with title, category, conviction, last_touched.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from collections import Counter
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "_lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from frontmatter import read_file  # noqa: E402
from idea_io import iter_all_ideas  # noqa: E402
from vault_paths import VAULT_ROOT, INBOX_DIR  # noqa: E402


def _load(include_inbox: bool = False) -> list[tuple[dict, Path]]:
    rows: list[tuple[dict, Path]] = []
    for p in iter_all_ideas(include_inbox=include_inbox, include_archive=False):
        try:
            meta, _ = read_file(p)
        except Exception:
            continue
        rows.append((meta, p))
    return rows


def _date(meta: dict, key: str = "last_touched") -> dt.date | None:
    raw = meta.get(key) or meta.get("created")
    if not raw:
        return None
    try:
        return dt.date.fromisoformat(str(raw))
    except Exception:
        return None


def _line(meta: dict, p: Path, *, show_tags: bool = False) -> str:
    rel = p.relative_to(VAULT_ROOT) if VAULT_ROOT in p.parents else p
    title = (meta.get("title") or p.stem)[:60]
    cat = meta.get("category") or "?"
    conv = meta.get("conviction") or "?"
    lt = meta.get("last_touched") or meta.get("created") or "?"
    base = f"  {title:<60}  {cat:<8} {conv:<6} {lt}"
    if show_tags:
        tags = ",".join(meta.get("tags") or [])
        base += f"  [{tags}]"
    base += f"\n      → {rel}"
    return base


def panel_top(rows: list, limit: int = 15) -> str:
    items = [r for r in rows if r[0].get("status") == "active" and r[0].get("conviction") == "high"]
    items.sort(key=lambda r: r[0].get("last_touched") or "", reverse=True)
    items = items[:limit]
    lines = ["🔥 Top conviction (active, high)"]
    if not items:
        lines.append("  (none)")
    for meta, p in items:
        lines.append(_line(meta, p))
    return "\n".join(lines)


def panel_fresh(rows: list, days: int = 14, limit: int = 20) -> str:
    cutoff = dt.date.today() - dt.timedelta(days=days)
    items = [(meta, p) for meta, p in rows if (_date(meta, "created") or dt.date(1970, 1, 1)) >= cutoff]
    items.sort(key=lambda r: r[0].get("created") or "", reverse=True)
    items = items[:limit]
    lines = [f"🌱 Recently captured (last {days}d)"]
    if not items:
        lines.append("  (none)")
    for meta, p in items:
        lines.append(_line(meta, p))
    return "\n".join(lines)


def panel_idle(rows: list, days: int = 90, limit: int = 15) -> str:
    cutoff = dt.date.today() - dt.timedelta(days=days)
    items = [
        (meta, p) for meta, p in rows
        if meta.get("status") == "active" and (_date(meta) or dt.date.today()) <= cutoff
    ]
    items.sort(key=lambda r: r[0].get("last_touched") or "")
    items = items[:limit]
    lines = [f"💤 Idle (active, last touched {days}+d ago)"]
    if not items:
        lines.append("  (none)")
    for meta, p in items:
        lines.append(_line(meta, p))
    return "\n".join(lines)


def panel_by_category(rows: list) -> str:
    cnt: Counter = Counter()
    active: Counter = Counter()
    raw: Counter = Counter()
    for meta, _ in rows:
        cat = meta.get("category") or "?"
        cnt[cat] += 1
        if meta.get("status") == "active":
            active[cat] += 1
        if meta.get("status") == "raw":
            raw[cat] += 1
    lines = ["📊 By category", f"  {'category':<14} {'total':>5}  {'active':>6}  {'raw':>4}"]
    for cat, n in cnt.most_common():
        lines.append(f"  {cat:<14} {n:>5}  {active[cat]:>6}  {raw[cat]:>4}")
    return "\n".join(lines)


def panel_tags(rows: list, limit: int = 20) -> str:
    cnt: Counter = Counter()
    for meta, _ in rows:
        for t in (meta.get("tags") or []):
            if t:
                cnt[t] += 1
    lines = [f"🏷️ Top tags (top {limit})"]
    for t, n in cnt.most_common(limit):
        lines.append(f"  {t:<24} {n:>4}")
    return "\n".join(lines)


def panel_inbox(limit: int = 10) -> str:
    if not INBOX_DIR.exists():
        return "📥 Inbox queue\n  (no inbox)"
    items: list[tuple[dict, Path]] = []
    for p in INBOX_DIR.rglob("*.md"):
        try:
            meta, _ = read_file(p)
        except Exception:
            continue
        items.append((meta, p))
    items.sort(key=lambda r: r[0].get("created") or "")
    total = len(items)
    items = items[:limit]
    lines = [f"📥 Inbox queue ({total} pending, oldest first)"]
    if not items:
        lines.append("  (empty)")
    for meta, p in items:
        lines.append(_line(meta, p))
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", action="store_true")
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--idle", action="store_true")
    ap.add_argument("--by-category", dest="by_category", action="store_true")
    ap.add_argument("--tags", action="store_true")
    ap.add_argument("--inbox", action="store_true")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    show = {
        "top": args.top or args.all,
        "fresh": args.fresh or args.all,
        "idle": args.idle or args.all,
        "by_category": args.by_category or args.all,
        "tags": args.tags or args.all,
        "inbox": args.inbox or args.all,
    }
    if not any(show.values()):
        show["top"] = True  # default
        show["by_category"] = True
        show["inbox"] = True

    rows = _load(include_inbox=False)

    panels: list[str] = []
    if show["top"]:
        panels.append(panel_top(rows))
    if show["fresh"]:
        panels.append(panel_fresh(rows))
    if show["idle"]:
        panels.append(panel_idle(rows))
    if show["by_category"]:
        panels.append(panel_by_category(rows))
    if show["tags"]:
        panels.append(panel_tags(rows))
    if show["inbox"]:
        panels.append(panel_inbox())

    print("\n\n".join(panels))
    return 0


if __name__ == "__main__":
    sys.exit(main())
