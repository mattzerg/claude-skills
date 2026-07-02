#!/usr/bin/env python3
"""Read browser history from Chrome / Safari / Brave."""

from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

HOME = Path.home()

BROWSERS = {
    "chrome": {
        "db": HOME / "Library/Application Support/Google/Chrome/Default/History",
        "epoch": datetime(1601, 1, 1, tzinfo=timezone.utc),
        "unit": "us",  # microseconds since 1601
        "query_recent": "SELECT url, title, last_visit_time FROM urls WHERE last_visit_time > ? ORDER BY last_visit_time DESC LIMIT ?",
        "query_match": "SELECT url, title, last_visit_time FROM urls WHERE last_visit_time > ? AND (url LIKE ? OR title LIKE ?) ORDER BY last_visit_time DESC LIMIT ?",
    },
    "brave": {
        "db": HOME / "Library/Application Support/BraveSoftware/Brave-Browser/Default/History",
        "epoch": datetime(1601, 1, 1, tzinfo=timezone.utc),
        "unit": "us",
        "query_recent": "SELECT url, title, last_visit_time FROM urls WHERE last_visit_time > ? ORDER BY last_visit_time DESC LIMIT ?",
        "query_match": "SELECT url, title, last_visit_time FROM urls WHERE last_visit_time > ? AND (url LIKE ? OR title LIKE ?) ORDER BY last_visit_time DESC LIMIT ?",
    },
    "safari": {
        "db": HOME / "Library/Safari/History.db",
        "epoch": datetime(2001, 1, 1, tzinfo=timezone.utc),
        "unit": "s_real",  # seconds since 2001, REAL
        "query_recent": """
            SELECT i.url, v.title, v.visit_time
            FROM history_items i JOIN history_visits v ON v.history_item = i.id
            WHERE v.visit_time > ? ORDER BY v.visit_time DESC LIMIT ?
        """,
        "query_match": """
            SELECT i.url, v.title, v.visit_time
            FROM history_items i JOIN history_visits v ON v.history_item = i.id
            WHERE v.visit_time > ? AND (i.url LIKE ? OR v.title LIKE ?)
            ORDER BY v.visit_time DESC LIMIT ?
        """,
    },
}


def cutoff_for(browser: str, hours: int):
    spec = BROWSERS[browser]
    cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=hours)
    delta = (cutoff_dt - spec["epoch"]).total_seconds()
    if spec["unit"] == "us":
        return int(delta * 1_000_000)
    return delta


def parse_ts(browser: str, raw):
    spec = BROWSERS[browser]
    if raw is None:
        return None
    if spec["unit"] == "us":
        seconds = raw / 1_000_000
    else:
        seconds = float(raw)
    try:
        return spec["epoch"] + timedelta(seconds=seconds)
    except (OverflowError, ValueError):
        return None


def open_browser(browser: str) -> sqlite3.Connection | None:
    spec = BROWSERS[browser]
    src = spec["db"]
    if not src.exists():
        return None
    tmp = Path(tempfile.gettempdir()) / f"browser-history-{browser}.db"
    try:
        shutil.copy2(src, tmp)
    except OSError as e:
        print(f"({browser} copy failed: {e})", file=sys.stderr)
        return None
    return sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)


def fmt_row(browser: str, url: str, title: str | None, ts_raw) -> str:
    dt = parse_ts(browser, ts_raw)
    ts = dt.astimezone().strftime("%Y-%m-%d %H:%M") if dt else "?"
    title = " ".join((title or "").split())
    if len(title) > 80:
        title = title[:79] + "…"
    if len(url) > 100:
        url = url[:99] + "…"
    return f'[{ts}] {browser:7}  {url}  "{title}"'


def cmd_recent(hours: int, limit: int, only_browser: str | None) -> int:
    rows = []
    browsers = [only_browser] if only_browser else list(BROWSERS.keys())
    for b in browsers:
        if b not in BROWSERS:
            print(f"unknown browser '{b}'", file=sys.stderr)
            continue
        conn = open_browser(b)
        if conn is None:
            continue
        try:
            cur = conn.execute(
                BROWSERS[b]["query_recent"], (cutoff_for(b, hours), limit)
            )
            for url, title, ts_raw in cur.fetchall():
                rows.append((parse_ts(b, ts_raw), b, url, title, ts_raw))
        except sqlite3.Error as e:
            print(f"({b} query failed: {e})", file=sys.stderr)
        finally:
            conn.close()
    rows.sort(key=lambda r: r[0] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    if not rows:
        print(f"(no browser history in last {hours}h)")
        return 0
    for _, b, url, title, ts_raw in rows[:limit]:
        print(fmt_row(b, url, title, ts_raw))
    return 0


def cmd_search(query: str, hours: int, limit: int) -> int:
    rows = []
    pat = f"%{query}%"
    for b in BROWSERS:
        conn = open_browser(b)
        if conn is None:
            continue
        try:
            cur = conn.execute(
                BROWSERS[b]["query_match"], (cutoff_for(b, hours), pat, pat, limit)
            )
            for url, title, ts_raw in cur.fetchall():
                rows.append((parse_ts(b, ts_raw), b, url, title, ts_raw))
        except sqlite3.Error as e:
            print(f"({b} query failed: {e})", file=sys.stderr)
        finally:
            conn.close()
    rows.sort(key=lambda r: r[0] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    if not rows:
        print(f"(no matches for '{query}')")
        return 0
    for _, b, url, title, ts_raw in rows[:limit]:
        print(fmt_row(b, url, title, ts_raw))
    return 0


def cmd_for_domain(domain: str, hours: int, limit: int) -> int:
    return cmd_search(domain, hours, limit)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="read_history")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_recent = sub.add_parser("recent")
    p_recent.add_argument("--hours", type=int, default=24)
    p_recent.add_argument("--limit", type=int, default=50)
    p_recent.add_argument("--browser", default=None, choices=list(BROWSERS.keys()))

    p_search = sub.add_parser("search")
    p_search.add_argument("query")
    p_search.add_argument("--hours", type=int, default=24 * 30)
    p_search.add_argument("--limit", type=int, default=50)

    p_dom = sub.add_parser("for-domain")
    p_dom.add_argument("domain")
    p_dom.add_argument("--hours", type=int, default=24 * 30)
    p_dom.add_argument("--limit", type=int, default=50)

    args = ap.parse_args(argv)
    if args.cmd == "recent":
        return cmd_recent(args.hours, args.limit, args.browser)
    if args.cmd == "search":
        return cmd_search(args.query, args.hours, args.limit)
    if args.cmd == "for-domain":
        return cmd_for_domain(args.domain, args.hours, args.limit)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
