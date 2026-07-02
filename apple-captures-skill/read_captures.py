#!/usr/bin/env python3
"""Read-only Apple Notes + Reminders via AppleScript (osascript)."""

from __future__ import annotations

import argparse
import subprocess
import sys


def osa(script: str) -> str:
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        print("(osascript timed out — Notes / Reminders may be unresponsive)", file=sys.stderr)
        return ""
    if result.returncode != 0:
        err = result.stderr.strip()
        if "Not authorized" in err or "1743" in err:
            print(
                "(TCC permission missing — open System Settings → Privacy → Automation "
                "and allow Terminal/iTerm to control Notes and Reminders)",
                file=sys.stderr,
            )
        else:
            print(f"(osascript error: {err})", file=sys.stderr)
        return ""
    return result.stdout


def notes_recent(days: int) -> int:
    script = f'''
    set out to ""
    set cutoff to (current date) - (({days} * days))
    tell application "Notes"
        repeat with n in (notes whose modification date > cutoff)
            try
                set b to body of n
                set t to name of n
                set m to modification date of n as string
                set f to name of (container of n)
                set preview to text 1 thru (count of (do shell script "echo " & quoted form of b & " | sed -e 's/<[^>]*>//g' | head -c 120")) of (do shell script "echo " & quoted form of b & " | sed -e 's/<[^>]*>//g' | head -c 120")
                set out to out & m & " | " & f & " / " & t & " | " & preview & linefeed
            end try
        end repeat
    end tell
    return out
    '''
    output = osa(script)
    if not output.strip():
        print(f"(no Notes modified in last {days}d, or TCC denied)")
        return 0
    print(output.strip())
    return 0


def notes_search(query: str) -> int:
    q = query.replace('"', '\\"')
    script = f'''
    set out to ""
    tell application "Notes"
        repeat with n in (notes whose body contains "{q}")
            try
                set t to name of n
                set m to modification date of n as string
                set f to name of (container of n)
                set b to body of n
                set preview to do shell script "echo " & quoted form of b & " | sed -e 's/<[^>]*>//g' | head -c 200"
                set out to out & m & " | " & f & " / " & t & " | " & preview & linefeed
            end try
        end repeat
    end tell
    return out
    '''
    output = osa(script)
    if not output.strip():
        print(f"(no Notes matching '{query}')")
        return 0
    print(output.strip())
    return 0


def reminders_open() -> int:
    script = '''
    set out to ""
    tell application "Reminders"
        repeat with l in lists
            set ln to name of l
            repeat with r in (reminders of l whose completed is false)
                set rn to name of r
                set dd to ""
                try
                    set dd to (due date of r) as string
                end try
                set out to out & ln & " | " & rn & " | due=" & dd & linefeed
            end repeat
        end repeat
    end tell
    return out
    '''
    output = osa(script)
    if not output.strip():
        print("(no open reminders, or TCC denied)")
        return 0
    print(output.strip())
    return 0


def reminders_search(query: str) -> int:
    q = query.replace('"', '\\"')
    script = f'''
    set out to ""
    tell application "Reminders"
        repeat with l in lists
            set ln to name of l
            repeat with r in (reminders of l whose name contains "{q}")
                set rn to name of r
                set comp to completed of r
                set out to out & ln & " | " & rn & " | completed=" & comp & linefeed
            end repeat
        end repeat
    end tell
    return out
    '''
    output = osa(script)
    if not output.strip():
        print(f"(no reminders matching '{query}')")
        return 0
    print(output.strip())
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="read_captures")
    sub = ap.add_subparsers(dest="domain", required=True)

    p_notes = sub.add_parser("notes")
    p_notes_sub = p_notes.add_subparsers(dest="action", required=True)
    p_nr = p_notes_sub.add_parser("recent")
    p_nr.add_argument("--days", type=int, default=14)
    p_ns = p_notes_sub.add_parser("search")
    p_ns.add_argument("query")

    p_rem = sub.add_parser("reminders")
    p_rem_sub = p_rem.add_subparsers(dest="action", required=True)
    p_rem_sub.add_parser("open")
    p_rs = p_rem_sub.add_parser("search")
    p_rs.add_argument("query")

    args = ap.parse_args(argv)
    if args.domain == "notes":
        if args.action == "recent":
            return notes_recent(args.days)
        return notes_search(args.query)
    if args.domain == "reminders":
        if args.action == "open":
            return reminders_open()
        return reminders_search(args.query)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
