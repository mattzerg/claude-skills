#!/usr/bin/env python3
"""Audit Fake Matt sent-log backlog.

The learning loop should reconcile drafts that Matt actually sent. Drafts that
were only printed to stdout or written locally can sit unchecked forever because
there is no Gmail draft/message to match. This command classifies old local-only
records as abandoned so they stop looking like learning-loop failures.

Usage:
    python3 ~/.claude/skills/fakematt-email/sent_log_audit.py
    python3 ~/.claude/skills/fakematt-email/sent_log_audit.py --days 7 --apply
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

CLAUDE_SKILLS = Path.home() / ".claude" / "skills"
DEFAULT_SKILLS = {
    "email": CLAUDE_SKILLS / "fakematt-email",
    "personal": CLAUDE_SKILLS / "fakematt-personal",
}


def parse_ts(raw: str | None) -> dt.datetime | None:
    if not raw:
        return None
    for fmt in ("%Y%m%dT%H%M%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(raw[: len(dt.datetime.now().strftime(fmt))], fmt)
        except ValueError:
            continue
    return None


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            rows.append({"_invalid_json": line, "checked": True})
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with open(path, "w") as f:
        for row in rows:
            if "_invalid_json" in row:
                f.write(row["_invalid_json"] + "\n")
            else:
                f.write(json.dumps(row, ensure_ascii=True) + "\n")


def is_local_only(row: dict[str, Any]) -> bool:
    return (
        not row.get("draft_id")
        and not row.get("sent_msg_id")
        and not row.get("create_draft_path")
    )


def audit_rows(
    rows: list[dict[str, Any]],
    *,
    stale_days: int,
    now: dt.datetime,
    apply: bool,
) -> dict[str, Any]:
    cutoff = now - dt.timedelta(days=stale_days)
    stats: dict[str, Any] = {
        "total": len(rows),
        "pending": 0,
        "stale": 0,
        "abandoned_existing": 0,
        "abandoned_new": 0,
        "synthetic": 0,
        "invalid": 0,
        "candidates": [],
    }
    for index, row in enumerate(rows):
        if row.get("_invalid_json"):
            stats["invalid"] += 1
            continue
        if row.get("synthetic"):
            stats["synthetic"] += 1
        if row.get("abandoned"):
            stats["abandoned_existing"] += 1
        if row.get("checked"):
            continue
        if row.get("synthetic"):
            continue
        stats["pending"] += 1
        ts = parse_ts(row.get("ts"))
        is_stale = ts is not None and ts <= cutoff
        if is_stale:
            stats["stale"] += 1
        if not (is_stale and is_local_only(row)):
            continue
        candidate = {
            "index": index,
            "ts": row.get("ts"),
            "to": row.get("to"),
            "subject": row.get("subject"),
            "draft_file": row.get("draft_file"),
            "age_days": (now - ts).days if ts else None,
        }
        stats["candidates"].append(candidate)
        if apply:
            row["checked"] = True
            row["abandoned"] = True
            row["abandoned_at"] = now.isoformat(timespec="seconds")
            row["abandoned_reason"] = (
                f"stale local-only draft older than {stale_days} day(s); "
                "no Gmail draft_id or sent_msg_id to reconcile"
            )
            stats["abandoned_new"] += 1
    return stats


def skill_dirs(selection: str) -> dict[str, Path]:
    if selection == "all":
        return DEFAULT_SKILLS
    return {selection: DEFAULT_SKILLS[selection]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Fake Matt sent-log backlog.")
    parser.add_argument("--skill", choices=["all", "email", "personal"], default="all")
    parser.add_argument("--days", type=int, default=7, help="mark local-only unchecked rows stale after N days")
    parser.add_argument("--apply", action="store_true", help="write abandoned markers; default is dry-run")
    parser.add_argument("--json", action="store_true", help="print machine-readable summary")
    args = parser.parse_args()

    if args.days < 0:
        print("error: --days must be >= 0", file=sys.stderr)
        return 2

    now = dt.datetime.now()
    summaries: dict[str, Any] = {}
    for label, skill_dir in skill_dirs(args.skill).items():
        path = skill_dir / "sent-log.jsonl"
        rows = read_jsonl(path)
        stats = audit_rows(rows, stale_days=args.days, now=now, apply=args.apply)
        stats["path"] = str(path)
        summaries[label] = stats
        if args.apply and stats["abandoned_new"]:
            write_jsonl(path, rows)

    if args.json:
        print(json.dumps(summaries, indent=2, sort_keys=True))
        return 0

    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"Fake Matt sent-log audit ({mode}, stale after {args.days}d)")
    for label, stats in summaries.items():
        print(f"\n## {label}")
        print(f"  path: {stats['path']}")
        print(
            "  total={total} pending={pending} stale={stale} "
            "abandoned_existing={abandoned_existing} abandoned_new={abandoned_new} "
            "synthetic={synthetic} invalid={invalid}".format(**stats)
        )
        if stats["candidates"]:
            print("  candidates:")
            for row in stats["candidates"]:
                print(
                    f"  - index={row['index']} age={row['age_days']}d "
                    f"to={row['to']} ts={row['ts']} subject={row['subject']}"
                )
        else:
            print("  candidates: none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
