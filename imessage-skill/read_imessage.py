#!/usr/bin/env python3
"""Read-only access to Matt's local iMessage chat.db."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB = Path.home() / "Library" / "Messages" / "chat.db"
APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)


def connect() -> sqlite3.Connection:
    if not DB.exists():
        print(f"chat.db not found at {DB}", file=sys.stderr)
        sys.exit(1)
    return sqlite3.connect(f"file:{DB}?mode=ro", uri=True)


def apple_ts(ns: int | None) -> datetime | None:
    if not ns:
        return None
    seconds = ns / 1_000_000_000
    try:
        return APPLE_EPOCH + timedelta(seconds=seconds)
    except (OverflowError, ValueError):
        return None


def cutoff_ns(hours: int) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    delta = cutoff - APPLE_EPOCH
    return int(delta.total_seconds() * 1_000_000_000)


def fmt_row(date_ns, is_from_me, handle, text) -> str:
    dt = apple_ts(date_ns)
    ts = dt.astimezone().strftime("%Y-%m-%d %H:%M") if dt else "?"
    arrow = "→" if is_from_me else "←"
    handle = handle or "?"
    text = " ".join((text or "").split())
    if len(text) > 180:
        text = text[:179] + "…"
    return f"[{ts}] {arrow} {handle:24}  {text}"


def cmd_recent(hours: int, limit: int) -> int:
    conn = connect()
    rows = conn.execute(
        """
        SELECT m.date, m.is_from_me, h.id, m.text
        FROM message m
        LEFT JOIN handle h ON m.handle_id = h.ROWID
        WHERE m.date > ? AND m.text IS NOT NULL
        ORDER BY m.date DESC
        LIMIT ?
        """,
        (cutoff_ns(hours), limit),
    ).fetchall()
    if not rows:
        print(f"(no messages in last {hours}h)")
        return 0
    for r in rows:
        print(fmt_row(*r))
    return 0


def cmd_from(handle: str, limit: int) -> int:
    conn = connect()
    rows = conn.execute(
        """
        SELECT m.date, m.is_from_me, h.id, m.text
        FROM message m
        JOIN handle h ON m.handle_id = h.ROWID
        WHERE h.id LIKE ? AND m.text IS NOT NULL
        ORDER BY m.date DESC
        LIMIT ?
        """,
        (f"%{handle}%", limit),
    ).fetchall()
    if not rows:
        print(f"(no messages from handle matching '{handle}')")
        return 0
    for r in reversed(rows):
        print(fmt_row(*r))
    return 0


def cmd_search(query: str, hours: int, limit: int) -> int:
    conn = connect()
    rows = conn.execute(
        """
        SELECT m.date, m.is_from_me, h.id, m.text
        FROM message m
        LEFT JOIN handle h ON m.handle_id = h.ROWID
        WHERE m.date > ? AND m.text LIKE ?
        ORDER BY m.date DESC
        LIMIT ?
        """,
        (cutoff_ns(hours), f"%{query}%", limit),
    ).fetchall()
    if not rows:
        print(f"(no matches for '{query}' in last {hours}h)")
        return 0
    for r in rows:
        print(fmt_row(*r))
    return 0


def cmd_threads(limit: int) -> int:
    conn = connect()
    rows = conn.execute(
        """
        SELECT h.id, MAX(m.date) AS last_date, COUNT(*) AS msg_count
        FROM message m
        JOIN handle h ON m.handle_id = h.ROWID
        WHERE m.text IS NOT NULL
        GROUP BY h.id
        ORDER BY last_date DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    if not rows:
        print("(no threads)")
        return 0
    for handle, last_ns, count in rows:
        dt = apple_ts(last_ns)
        ts = dt.astimezone().strftime("%Y-%m-%d %H:%M") if dt else "?"
        print(f"[{ts}] {handle:30}  msgs={count}")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="read_imessage")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_recent = sub.add_parser("recent")
    p_recent.add_argument("--hours", type=int, default=24)
    p_recent.add_argument("--limit", type=int, default=50)

    p_from = sub.add_parser("from")
    p_from.add_argument("handle")
    p_from.add_argument("--limit", type=int, default=30)

    p_search = sub.add_parser("search")
    p_search.add_argument("query")
    p_search.add_argument("--hours", type=int, default=24 * 30)
    p_search.add_argument("--limit", type=int, default=30)

    p_threads = sub.add_parser("threads")
    p_threads.add_argument("--limit", type=int, default=20)

    args = ap.parse_args(argv)
    if args.cmd == "recent":
        return cmd_recent(args.hours, args.limit)
    if args.cmd == "from":
        return cmd_from(args.handle, args.limit)
    if args.cmd == "search":
        return cmd_search(args.query, args.hours, args.limit)
    if args.cmd == "threads":
        return cmd_threads(args.limit)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
