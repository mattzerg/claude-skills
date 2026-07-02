#!/usr/bin/env python3
"""ZergGuard iMessage watcher — auto-scan unknown senders for phishing."""

from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

DB = Path.home() / "Library" / "Messages" / "chat.db"
STATE = Path.home() / ".config" / "zerg-guard" / "imessage_watch.state"
LOG = Path.home() / ".config" / "zerg-guard" / "imessage_watch.log"
POLL_SECS = 60.0
CHECK = Path.home() / ".claude" / "skills" / "zergguard-scam-check" / "check.py"


def load_state() -> int:
    if not STATE.exists():
        return 0
    try:
        return int(STATE.read_text().strip())
    except (OSError, ValueError):
        return 0


def save_state(rowid: int) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(str(rowid))


def notify(title: str, body: str) -> None:
    body_safe = body.replace('"', '\\"')[:300]
    title_safe = title.replace('"', '\\"')[:60]
    script = (
        f'display notification "{body_safe}" '
        f'with title "ZergGuard" subtitle "{title_safe}" sound name "Sosumi"'
    )
    subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)


def log_event(line: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().isoformat(timespec="seconds")
    with LOG.open("a") as f:
        f.write(f"[{ts}] {line}\n")


def is_unknown_sender(conn: sqlite3.Connection, handle_id: int) -> bool:
    """A sender is 'unknown' if Matt has never sent them a message (no is_from_me=1 to this handle)."""
    row = conn.execute(
        "SELECT COUNT(*) FROM message WHERE handle_id = ? AND is_from_me = 1",
        (handle_id,),
    ).fetchone()
    return (row[0] if row else 0) == 0


def score_message(text: str) -> tuple[str, int]:
    """Return (label, exit_code) from scam-check."""
    try:
        result = subprocess.run(
            ["python3", str(CHECK), text],
            capture_output=True, text=True, timeout=10,
        )
    except subprocess.TimeoutExpired:
        return ("ERROR", -1)
    label = "?"
    for line in result.stdout.splitlines():
        if line.startswith("VERDICT:"):
            label = line.split(":", 1)[1].strip()
            break
    return (label, result.returncode)


def watch_loop() -> int:
    print("ZergGuard imessage-watch started", file=sys.stderr)
    last_rowid = load_state()
    if last_rowid == 0:
        # Baseline: take current max so we don't scan history retroactively.
        try:
            conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
            row = conn.execute("SELECT MAX(ROWID) FROM message").fetchone()
            last_rowid = row[0] or 0
            conn.close()
            save_state(last_rowid)
            print(f"baselined at rowid={last_rowid}", file=sys.stderr)
        except sqlite3.Error as e:
            print(f"baseline error: {e}", file=sys.stderr)
            time.sleep(POLL_SECS)
    while True:
        try:
            conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
            rows = conn.execute(
                """
                SELECT m.ROWID, m.handle_id, h.id, m.text
                FROM message m
                LEFT JOIN handle h ON m.handle_id = h.ROWID
                WHERE m.ROWID > ? AND m.is_from_me = 0 AND m.text IS NOT NULL
                ORDER BY m.ROWID ASC
                LIMIT 200
                """,
                (last_rowid,),
            ).fetchall()
            for rowid, handle_id, sender, text in rows:
                if not handle_id or not text:
                    last_rowid = max(last_rowid, rowid)
                    continue
                if is_unknown_sender(conn, handle_id):
                    label, _ = score_message(text)
                    log_event(f"unknown sender={sender} label={label} text={text[:120]}")
                    if label == "PHISH":
                        preview = text[:120].replace("\n", " ")
                        notify(
                            f"Possible phishing from {sender}",
                            f"{preview}  …",
                        )
                last_rowid = max(last_rowid, rowid)
            conn.close()
            save_state(last_rowid)
        except sqlite3.Error as e:
            print(f"poll error: {e}", file=sys.stderr)
        time.sleep(POLL_SECS)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="zergguard-imessage-watch")
    ap.add_argument("--baseline", action="store_true", help="reset state to current max rowid")
    args = ap.parse_args(argv)
    if args.baseline:
        try:
            conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
            row = conn.execute("SELECT MAX(ROWID) FROM message").fetchone()
            save_state(row[0] or 0)
            print(f"baselined at rowid={row[0]}")
            return 0
        except sqlite3.Error as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
    return watch_loop()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
