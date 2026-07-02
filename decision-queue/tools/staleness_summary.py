#!/usr/bin/env python3
"""staleness_summary.py — unified staleness across the OS.

Produces a single-line summary + per-entity detail. Designed to be embedded
into morning-brief and the decision-queue index page.

Sources (read-only):
  - zpub:       file mtime of MattZerg/Projects/Zerg-Production/Growth/publishing/pub-*.md
                older than zpub_stale_days (default 7)
  - gtm-hub:    entities with `last_touch` > gtm_stale_days (default 14)
  - workstreams: items with `last_touched` > workstream_stale_days (default 3)
  - idea-backlog: ideas with mtime > idea_stale_days (default 30) AND
                  status not in {published, archived}
  - promises:   morning-brief's `inbox.md` rows tagged `[blocked:matt-review]`
                or `[blocked:idan]` older than promise_stale_days (default 5)

Output:
  - Summary line: "12 stale across [zpub:3, gtm:5, ideas:2, promises:2]"
  - --detail flag: per-entity list with path + age

Usage:
  staleness_summary.py                   # one-line summary
  staleness_summary.py --detail          # full per-entity list
  staleness_summary.py --json            # machine-readable
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # type: ignore

VAULT = Path(os.path.expanduser(
    "~/Obsidian/Zerg"
))
GROWTH = VAULT / "MattZerg/Projects/Zerg-Production/Growth"
TASKS = VAULT / "MattZerg/Tasks"
IDEAS = VAULT / "MattZerg/Ideas"
WORKSTREAM_CACHE = Path.home() / ".config/zerg/workstreams.cache.json"


@dataclass
class StaleItem:
    source: str
    entity_id: str
    entity_path: str
    age_days: float
    title: str = ""
    reason: str = ""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _age_days_path(p: Path) -> float:
    try:
        return (datetime.now().timestamp() - p.stat().st_mtime) / 86400.0
    except FileNotFoundError:
        return 0.0


def _parse_dt(s) -> datetime | None:
    if not s:
        return None
    if hasattr(s, "isoformat") and not isinstance(s, str):
        try:
            return datetime(s.year, s.month, s.day, tzinfo=timezone.utc)
        except Exception:
            return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def _frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m or yaml is None:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except Exception:
        return {}


def scan_zpub(stale_days: int) -> list[StaleItem]:
    out = []
    pub_dir = GROWTH / "publishing"
    if not pub_dir.exists():
        return out
    for p in pub_dir.glob("pub-*.md"):
        try:
            fm = _frontmatter(p.read_text())
        except Exception:
            continue
        status = (fm.get("status") or "").lower()
        if status in ("published", "killed", "archived"):
            continue
        age = _age_days_path(p)
        if age < stale_days:
            continue
        out.append(StaleItem(
            source="zpub",
            entity_id=fm.get("id", p.stem),
            entity_path=str(p),
            age_days=age,
            title=fm.get("title", p.stem),
            reason=f"status={status}, mtime > {stale_days}d",
        ))
    return out


def scan_gtm(stale_days: int) -> list[StaleItem]:
    out = []
    for folder in ("experiments", "content", "bd", "prospects", "launches"):
        d = GROWTH / folder
        if not d.exists():
            continue
        for p in d.glob("*.md"):
            try:
                fm = _frontmatter(p.read_text())
            except Exception:
                continue
            status = (fm.get("status") or "").lower()
            if status in ("done", "shipped", "archived", "killed", "completed"):
                continue
            lt_raw = fm.get("last_touch")
            lt_dt = _parse_dt(lt_raw)
            if lt_dt:
                age = (_now() - lt_dt).total_seconds() / 86400.0
            else:
                age = _age_days_path(p)
            if age < stale_days:
                continue
            out.append(StaleItem(
                source=f"gtm:{folder}",
                entity_id=fm.get("id", p.stem),
                entity_path=str(p),
                age_days=age,
                title=fm.get("title", p.stem),
                reason=f"status={status}, last_touch > {stale_days}d",
            ))
    return out


def scan_workstreams(stale_days: int) -> list[StaleItem]:
    out = []
    if not WORKSTREAM_CACHE.exists():
        return out
    try:
        data = json.loads(WORKSTREAM_CACHE.read_text())
    except Exception:
        return out
    workstreams = data.get("workstreams") or data.get("items") or []
    for ws in workstreams:
        if not isinstance(ws, dict):
            continue
        lt = _parse_dt(ws.get("last_touched"))
        if not lt:
            continue
        age = (_now() - lt).total_seconds() / 86400.0
        if age < stale_days:
            continue
        out.append(StaleItem(
            source="workstreams",
            entity_id=ws.get("id", "?"),
            entity_path=ws.get("path", ""),
            age_days=age,
            title=ws.get("title") or ws.get("id", "?"),
            reason=f"last_touched > {stale_days}d",
        ))
    return out


def scan_ideas(stale_days: int) -> list[StaleItem]:
    out = []
    if not IDEAS.exists():
        return out
    for p in IDEAS.rglob("*.md"):
        try:
            fm = _frontmatter(p.read_text())
        except Exception:
            continue
        status = (fm.get("status") or "raw").lower()
        if status in ("published", "archived", "shipped", "killed"):
            continue
        age = _age_days_path(p)
        if age < stale_days:
            continue
        out.append(StaleItem(
            source="ideas",
            entity_id=fm.get("id", p.stem),
            entity_path=str(p),
            age_days=age,
            title=fm.get("title", p.stem),
            reason=f"status={status}, idle > {stale_days}d",
        ))
    return out


def scan_promises(stale_days: int) -> list[StaleItem]:
    """Read inbox.md, find [blocked:matt-review] / [blocked:idan] lines older than X."""
    out = []
    inbox = TASKS / "inbox.md"
    if not inbox.exists():
        return out
    # File-level mtime as a coarse proxy (rows don't carry per-row dates)
    age = _age_days_path(inbox)
    text = inbox.read_text()
    for i, line in enumerate(text.splitlines(), 1):
        low = line.lower()
        if not re.match(r"^\s*[-*]\s+(?!\*)", line):
            continue
        if not ("[blocked:matt-review]" in low or "[blocked:idan]" in low):
            continue
        if age < stale_days:
            continue
        out.append(StaleItem(
            source="promises",
            entity_id=f"L{i}",
            entity_path=str(inbox),
            age_days=age,
            title=line[:80],
            reason=f"inbox row blocked, file > {stale_days}d",
        ))
    return out


def gather(args) -> dict:
    items = []
    items.extend(scan_zpub(args.zpub_stale_days))
    items.extend(scan_gtm(args.gtm_stale_days))
    items.extend(scan_workstreams(args.workstream_stale_days))
    items.extend(scan_ideas(args.idea_stale_days))
    items.extend(scan_promises(args.promise_stale_days))
    items.sort(key=lambda x: -x.age_days)
    by_source = {}
    for it in items:
        key = it.source.split(":")[0]
        by_source[key] = by_source.get(key, 0) + 1
    return {"items": items, "by_source": by_source, "total": len(items)}


def render_summary(result: dict) -> str:
    if result["total"] == 0:
        return "0 stale entities across OS"
    parts = [f"{k}:{v}" for k, v in sorted(result["by_source"].items())]
    return f"{result['total']} stale across [{', '.join(parts)}]"


def render_detail(result: dict, top: int = 30) -> str:
    lines = [render_summary(result), ""]
    if not result["items"]:
        return "\n".join(lines)
    lines.append("| Source | ID | Age | Reason | Path |")
    lines.append("|---|---|---|---|---|")
    for it in result["items"][:top]:
        lines.append(
            f"| `{it.source}` | `{it.entity_id}` | {int(it.age_days)}d | "
            f"{it.reason} | `{it.entity_path.split('/')[-1]}` |"
        )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zpub-stale-days", type=int, default=7)
    ap.add_argument("--gtm-stale-days", type=int, default=14)
    ap.add_argument("--workstream-stale-days", type=int, default=3)
    ap.add_argument("--idea-stale-days", type=int, default=30)
    ap.add_argument("--promise-stale-days", type=int, default=5)
    ap.add_argument("--detail", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = gather(args)
    if args.json:
        print(json.dumps({
            "summary": render_summary(result),
            "total": result["total"],
            "by_source": result["by_source"],
            "items": [asdict(it) for it in result["items"]],
        }, default=str))
        return 0
    if args.detail:
        print(render_detail(result))
    else:
        print(render_summary(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
