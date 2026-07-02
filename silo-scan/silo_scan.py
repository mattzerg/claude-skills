#!/usr/bin/env python3
"""Composite read across Codex + iMessage + browser + reminders + zergaudience."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SKILLS = Path.home() / ".claude" / "skills"

SILOS = [
    {
        "name": "Codex sessions",
        "cmd": ["python3", str(SKILLS / "codex-transcript-read" / "read_codex.py"), "recent"],
        "hours_flag": "--hours",
        "key": "codex",
    },
    {
        "name": "iMessage",
        "cmd": ["python3", str(SKILLS / "imessage-skill" / "read_imessage.py"), "recent"],
        "hours_flag": "--hours",
        "extra": ["--limit", "10"],
        "key": "imessage",
    },
    {
        "name": "ZergAudience signups",
        "cmd": ["python3", str(SKILLS / "zergaudience-skill" / "read_audience.py"), "recent"],
        "hours_flag": "--days",
        "hours_to_arg": lambda h: max(1, h // 24),
        "key": "zergaudience",
    },
    {
        "name": "Browser history",
        "cmd": ["python3", str(SKILLS / "browser-history-skill" / "read_history.py"), "recent"],
        "hours_flag": "--hours",
        "extra": ["--limit", "15"],
        "key": "browser",
    },
    {
        "name": "Open reminders",
        "cmd": ["python3", str(SKILLS / "apple-captures-skill" / "read_captures.py"), "reminders", "open"],
        "hours_flag": None,
        "key": "reminders",
    },
]


def run_silo(silo: dict, hours: int) -> str:
    cmd = list(silo["cmd"])
    if silo["hours_flag"]:
        converter = silo.get("hours_to_arg", lambda h: h)
        cmd += [silo["hours_flag"], str(converter(hours))]
    cmd += silo.get("extra", [])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return "(silo timed out)"
    out = (result.stdout or "").rstrip()
    err = (result.stderr or "").rstrip()
    if not out and err:
        return f"({err.splitlines()[0]})"
    return out or "(no signal)"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="silo_scan")
    ap.add_argument("--hours", type=int, default=12)
    ap.add_argument(
        "--skip",
        action="append",
        default=[],
        help="silo key to skip (codex, imessage, browser, reminders, zergaudience)",
    )
    args = ap.parse_args(argv)

    print(f"# silo-scan (last {args.hours}h)")
    print()
    for silo in SILOS:
        if silo["key"] in args.skip:
            continue
        print(f"## {silo['name']}")
        print(run_silo(silo, args.hours))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
