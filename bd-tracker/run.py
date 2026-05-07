#!/usr/bin/env python3
"""BD tracker — log + alert on Zerg's Product BD partner conversations.

Reads the canonical 25-target list at MattZerg/Projects/Zstack/Growth/bd-targets.md
and tracks status / next-touch / owner for each target. Mirrors to a Zergboard "BD"
board (Phase 2.1 — currently file-based only).

Usage:
    python3 ~/.claude/skills/bd-tracker/run.py list [--category integration|co-marketing|podcast|ecosystem]
    python3 ~/.claude/skills/bd-tracker/run.py log <target-name> [--note "..."] [--status NEW] [--next-touch YYYY-MM-DD]
    python3 ~/.claude/skills/bd-tracker/run.py stale [--days 14]   # Slack DM alerts (Phase 2.1; stdout for now)
    python3 ~/.claude/skills/bd-tracker/run.py status <target-name>

Status legend: planned | outreach | engaged | paused | closed-won | closed-lost
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

VAULT = Path("/Users/mattheweisner/Library/Mobile Documents/iCloud~md~obsidian/Documents/Zerg/MattZerg")
BD_FILE = VAULT / "Projects" / "Zstack" / "Growth" / "bd-targets.md"
LOG_FILE = VAULT / "Projects" / "Zstack" / "Growth" / "bd-touch-log.md"

VALID_STATUSES = {
    "planned", "outreach", "engaged", "paused", "closed-won", "closed-lost",
}


def load_targets() -> list[dict[str, str]]:
    """Parse bd-targets.md tables into a list of target dicts.

    Skips header rows + empty rows. Adds a `category` field based on the
    nearest preceding `## Category` header.
    """
    if not BD_FILE.exists():
        return []
    targets: list[dict[str, str]] = []
    current_category = "uncategorized"
    for raw in BD_FILE.read_text().splitlines():
        line = raw.rstrip()
        m = re.match(r"^##+\s+(.+?)\s*\(", line)
        if m:
            current_category = m.group(1).strip().lower().replace(" ", "-")
            continue
        if not line.startswith("|"):
            continue
        if line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        # Skip header rows
        if cells and cells[0].lower() in {"target", "show", "title"}:
            continue
        if not cells or len(cells) < 4:
            continue
        # Common shape: Target | Status | Why | Owner | Next
        # Podcast shape:  Target | Audience | Pitch angle | Owner | Next
        if cells[1].lower() in VALID_STATUSES:
            targets.append({
                "name": _strip_md(cells[0]),
                "category": current_category,
                "status": cells[1],
                "why": cells[2] if len(cells) > 2 else "",
                "owner": cells[3] if len(cells) > 3 else "",
                "next": cells[4] if len(cells) > 4 else "",
            })
        else:
            # Podcast-shape (no status column at index 1) — treat status as "planned" by default
            targets.append({
                "name": _strip_md(cells[0]),
                "category": current_category,
                "status": "planned",
                "why": cells[2] if len(cells) > 2 else "",
                "owner": cells[3] if len(cells) > 3 else "",
                "next": cells[4] if len(cells) > 4 else "",
            })
    return targets


def _strip_md(s: str) -> str:
    """Strip markdown emphasis markers anywhere in the string."""
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"\*(.+?)\*", r"\1", s)
    return s.strip()


def _normalize(s: str) -> str:
    """Normalize a name for matching: strip markdown, parentheticals, lowercase."""
    s = _strip_md(s)
    s = re.sub(r"\s*\([^)]*\)\s*", " ", s).strip()
    return s.lower()


def append_touch_log(target: str, status: str, note: str, next_touch: str | None) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not LOG_FILE.exists():
        LOG_FILE.write_text(
            "# BD Touch Log\n\nAuto-appended by bd-tracker skill.\n\n"
            "| Date | Target | Status | Note | Next Touch |\n"
            "|---|---|---|---|---|\n"
        )
    today = dt.date.today().isoformat()
    row = f"| {today} | {target} | {status} | {note} | {next_touch or ''} |\n"
    with LOG_FILE.open("a") as f:
        f.write(row)


def find_target_in_log(target: str) -> list[tuple[str, str, str, str]]:
    """Return all log entries for a target as (date, status, note, next_touch)."""
    if not LOG_FILE.exists():
        return []
    rows: list[tuple[str, str, str, str]] = []
    for line in LOG_FILE.read_text().splitlines():
        if not line.startswith("|") or line.startswith("|---") or "Date" in line:
            continue
        cells = [c.strip() for c in line.split("|")[1:-1]]
        if len(cells) >= 5 and cells[1].lower() == target.lower():
            rows.append((cells[0], cells[2], cells[3], cells[4]))
    return rows


def cmd_list(args: argparse.Namespace) -> int:
    targets = load_targets()
    if args.category:
        targets = [t for t in targets if args.category.lower() in t["category"]]
    if not targets:
        print("(no targets)")
        return 0
    print(f"{'Name':<35} {'Category':<25} {'Status':<14} {'Owner':<10} Next")
    print("-" * 110)
    for t in targets:
        name = t["name"][:33]
        cat = t["category"][:23]
        status = t["status"][:12]
        owner = t["owner"][:8]
        nxt = (t["next"] or "")[:50]
        print(f"{name:<35} {cat:<25} {status:<14} {owner:<10} {nxt}")
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    if args.status and args.status not in VALID_STATUSES:
        print(f"ERROR: --status must be one of {sorted(VALID_STATUSES)}", file=sys.stderr)
        return 1
    # Verify target exists in canonical list
    targets = load_targets()
    names = {_normalize(t["name"]) for t in targets}
    if _normalize(args.target) not in names:
        print(f"WARN: '{args.target}' not in bd-targets.md. Logging anyway.", file=sys.stderr)
    status = args.status or "engaged"
    append_touch_log(args.target, status, args.note or "", args.next_touch)
    print(f"Logged: {args.target} → {status}" + (f" (next-touch {args.next_touch})" if args.next_touch else ""))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    targets = load_targets()
    match = next((t for t in targets if _normalize(t["name"]) == _normalize(args.target)), None)
    if not match:
        print(f"ERROR: '{args.target}' not in bd-targets.md", file=sys.stderr)
        return 1
    print(f"Target:   {match['name']}")
    print(f"Category: {match['category']}")
    print(f"Status:   {match['status']}")
    print(f"Why:      {match['why']}")
    print(f"Owner:    {match['owner']}")
    print(f"Next:     {match['next']}")
    log_rows = find_target_in_log(args.target)
    if log_rows:
        print(f"\nTouch log ({len(log_rows)} entries):")
        for date, status, note, next_touch in log_rows:
            print(f"  {date}  {status:<14}  {note}" + (f"  → next {next_touch}" if next_touch else ""))
    return 0


def cmd_stale(args: argparse.Namespace) -> int:
    targets = load_targets()
    today = dt.date.today()
    threshold_days = args.days
    log_rows_by_target: dict[str, str] = {}  # latest log date per target
    if LOG_FILE.exists():
        for line in LOG_FILE.read_text().splitlines():
            if not line.startswith("|") or line.startswith("|---") or "Date" in line:
                continue
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if len(cells) >= 2:
                t_name = cells[1].lower()
                date_str = cells[0]
                if t_name not in log_rows_by_target or date_str > log_rows_by_target[t_name]:
                    log_rows_by_target[t_name] = date_str

    stale: list[tuple[dict[str, str], int]] = []
    for t in targets:
        if t["status"] in {"closed-won", "closed-lost", "paused", "planned"}:
            continue
        # active = outreach | engaged
        last_touch_date_str = log_rows_by_target.get(t["name"].lower())
        if not last_touch_date_str:
            stale.append((t, threshold_days + 1))  # never touched
            continue
        try:
            last = dt.date.fromisoformat(last_touch_date_str)
        except ValueError:
            continue
        days_since = (today - last).days
        if days_since >= threshold_days:
            stale.append((t, days_since))

    if not stale:
        print(f"No active targets stale (>{threshold_days}d).")
        return 0
    print(f"Stale active targets (no touch in ≥{threshold_days}d):")
    for t, days in stale:
        print(f"  [{t['status']:<10}] {t['name']:<30} {days}d since last touch  (owner: {t['owner']})")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="bd-tracker", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list")
    pl.add_argument("--category", help="filter by category (substring match)")
    pl.set_defaults(func=cmd_list)

    plg = sub.add_parser("log")
    plg.add_argument("target")
    plg.add_argument("--status", help=f"new status: {sorted(VALID_STATUSES)}")
    plg.add_argument("--note", help="touch note")
    plg.add_argument("--next-touch", dest="next_touch", help="YYYY-MM-DD when to follow up")
    plg.set_defaults(func=cmd_log)

    pst = sub.add_parser("status")
    pst.add_argument("target")
    pst.set_defaults(func=cmd_status)

    psta = sub.add_parser("stale")
    psta.add_argument("--days", type=int, default=14)
    psta.set_defaults(func=cmd_stale)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
