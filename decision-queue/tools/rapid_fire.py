#!/usr/bin/env python3
"""rapid_fire.py — terminal rapid-fire decision-queue.

Walks Matt through pending decisions one at a time with full context briefing.
Single-char input: y/n/d/?/q (yes/no/defer-1d/details/quit). Writes answers
straight to decisions_log.jsonl — same shape as Slack and swipe-UI replies.

Use this on the desktop terminal when you want fast keyboard throughput.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = Path(os.path.expanduser("~/.claude/state"))
DECISIONS_JSONL = STATE_DIR / "decisions_pending.jsonl"
DECISIONS_LOG = STATE_DIR / "decisions_log.jsonl"
SKILL_DIR = Path(__file__).resolve().parent.parent

ANSI = {
    "reset": "\033[0m",
    "dim": "\033[2m",
    "bold": "\033[1m",
    "cyan": "\033[36m",
    "yellow": "\033[33m",
    "green": "\033[32m",
    "red": "\033[31m",
    "blue": "\033[34m",
    "magenta": "\033[35m",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def regen() -> None:
    subprocess.run(
        ["/usr/bin/python3", str(SKILL_DIR / "tools" / "aggregate.py")],
        check=False, capture_output=True,
    )


def load_queue() -> list[dict]:
    if not DECISIONS_JSONL.exists():
        return []
    items = []
    with DECISIONS_JSONL.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return items


def log_answer(item: dict, answer: str, note: str | None = None) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": _now_iso(),
        "id": item.get("id"),
        "answer": answer,
        "channel": "rapid_fire",
        "note": note,
        "briefing_snapshot": item,
        "source": item.get("source"),
        "autonomy_class": item.get("autonomy_class"),
    }
    with DECISIONS_LOG.open("a") as fh:
        fh.write(json.dumps(record) + "\n")


def get_char() -> str:
    """Single-keystroke read."""
    import termios, tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    return ch


def color(s: str, *cs: str) -> str:
    return "".join(ANSI[c] for c in cs) + s + ANSI["reset"]


def print_card(item: dict, i: int, total: int) -> None:
    os.system("clear")
    src = item.get("source", "?")
    cls = item.get("autonomy_class", "—") or "—"
    age = item.get("age_human", "")
    pri = item.get("priority", 50)
    ctx = item.get("context_one_line", "")
    why = item.get("why", "")
    path = item.get("entity_path", "")
    deadline = item.get("deadline")
    choices = item.get("choices") or ["yes", "no", "defer-1d", "details"]

    width = min(96, os.get_terminal_size().columns)
    print(color("─" * width, "dim"))
    print(f"{color(f'[{i}/{total}]', 'bold')}  {color(src, 'cyan')}  {color(cls, 'magenta')}  "
          f"{color('age=' + age, 'dim')}  {color('p=' + str(pri), 'dim')}")
    print(color("─" * width, "dim"))
    print()
    print(color(ctx, "bold"))
    print()
    if deadline:
        print(color(f"  ⏰ deadline: {deadline}", "yellow"))
        print()
    print(color("  why:", "dim"), why)
    print(color("  entity:", "dim"), color(path, "dim"))
    raw = item.get("raw") or {}
    if raw:
        # Print up to 3 raw KV pairs
        for k, v in list(raw.items())[:3]:
            print(color(f"  {k}:", "dim"), str(v)[:100])
    print()
    print(color("  choices:", "dim"), " / ".join(choices),
          color(f" (default={item.get('suggested_default', 'details')})", "dim"))
    print()
    print(color("  [y] yes   [n] no   [d] defer-1d   [?] details   [s] skip   [q] quit", "blue"))


def show_full_briefing(item: dict) -> None:
    print()
    print(color("--- full briefing ---", "yellow"))
    print(json.dumps(item, indent=2, default=str))
    print(color("--- end ---", "yellow"))
    print()
    print(color("Press any key to return…", "dim"))
    get_char()


def main() -> int:
    # Default: regen first so we work on fresh data
    if "--no-regen" not in sys.argv:
        regen()

    items = load_queue()
    if not items:
        print(color("Queue empty. Autonomous lanes proceeding.", "green"))
        return 0

    # Optional class filter
    class_filter = None
    for arg in sys.argv[1:]:
        if arg.startswith("--class="):
            class_filter = arg.split("=", 1)[1]
    if class_filter:
        items = [it for it in items if it.get("autonomy_class") == class_filter]
        if not items:
            print(color(f"No items with autonomy_class={class_filter}", "yellow"))
            return 0

    handled = 0
    deferred = 0
    skipped = 0
    i = 0
    total = len(items)
    while i < total:
        item = items[i]
        print_card(item, i + 1, total)
        ch = get_char().lower()
        if ch == "q":
            print(color("\n quit", "yellow"))
            break
        if ch == "y":
            log_answer(item, "yes")
            handled += 1
        elif ch == "n":
            log_answer(item, "no")
            handled += 1
        elif ch == "d":
            log_answer(item, "defer-1d")
            deferred += 1
        elif ch == "?":
            show_full_briefing(item)
            continue  # don't advance
        elif ch == "s":
            skipped += 1
        else:
            # Unknown char — skip
            continue
        i += 1

    os.system("clear")
    print(color("Session complete.", "green"))
    print(f"  handled: {handled}    deferred: {deferred}    skipped: {skipped}")
    print(f"  remaining: {total - i}")
    print(f"  log: {DECISIONS_LOG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
