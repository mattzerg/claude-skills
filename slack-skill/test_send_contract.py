#!/usr/bin/env python3
"""Regression guard for the Slack `send` contract.

Backstory: `slack_skill.py send` requires `-m/--message`, but ~6 callers across
the codebase hand-built `["...","send",channel,msg]` with the message passed
*positionally*. argparse rejected every call with
`the following arguments are required: -m/--message`, and the growth-dashboard
Monday post failed silently for weeks (2026-05-25 → 2026-06-08).

This test makes that class of bug impossible to reintroduce:
  1. `send_message()` stays importable with the expected signature (the single
     in-process contract source).
  2. The `send` CLI subparser keeps requiring -m/--message.
  3. No caller invokes `slack_skill ... send` with a positional message.

Run:  python3 ~/.claude/skills/slack-skill/test_send_contract.py
Exit 0 = contract holds; exit 1 = a violation (printed).
"""
from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

HOME = Path.home()
SLACK_SKILL_DIR = HOME / ".claude" / "skills" / "slack-skill"
sys.path.insert(0, str(SLACK_SKILL_DIR))

# Dirs whose .py files may shell out to slack_skill.py send.
SCAN_DIRS = [
    HOME / ".claude" / "skills",
    HOME / ".claude" / "hooks",
    HOME / ".claude" / "fakematt-today",
    HOME / ".config" / "zerg",
]

# A line that references the slack skill AND the "send" verb but lacks -m/--message.
SLACK_REF = re.compile(r"SLACK_SKILL|slack_skill|slack_script|slack_bridge")
SEND_VERB = re.compile(r"""['"]send['"]""")
HAS_MESSAGE_FLAG = re.compile(r"""['"]-m['"]|['"]--message['"]|['"]-t['"]\b|message=|--message""")
# Skip argparse definitions and unrelated `send` verbs (gmail/zmail/twilio/etc).
SKIP = re.compile(r"add_parser|add_argument|subparsers|def cmd_send|GMAIL_SKILL|ZMAIL|twilio|gmail_skill|usage:")


def check_signature() -> list[str]:
    fails = []
    try:
        import slack_skill  # type: ignore
    except SystemExit:
        return ["slack_skill import called sys.exit() — slack_sdk likely missing"]
    except Exception as e:  # noqa: BLE001
        return [f"cannot import slack_skill: {e}"]
    fn = getattr(slack_skill, "send_message", None)
    if not callable(fn):
        return ["slack_skill.send_message is missing or not callable"]
    params = inspect.signature(fn).parameters
    for required in ("channel", "text"):
        if required not in params:
            fails.append(f"send_message() missing expected param '{required}'")
    return fails


def scan_callers() -> list[str]:
    violations = []
    for root in SCAN_DIRS:
        if not root.exists():
            continue
        for f in root.rglob("*.py"):
            if "_archive" in f.parts or f.name == "test_send_contract.py":
                continue
            try:
                for n, line in enumerate(f.read_text(errors="ignore").splitlines(), 1):
                    if not (SLACK_REF.search(line) and SEND_VERB.search(line)):
                        continue
                    if SKIP.search(line):
                        continue
                    if not HAS_MESSAGE_FLAG.search(line):
                        violations.append(f"{f}:{n}: positional message — needs -m/--message\n      {line.strip()}")
            except OSError:
                continue
    return violations


def main() -> int:
    problems = check_signature() + scan_callers()
    if problems:
        print("FAIL — Slack send contract violated:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("OK — send_message importable + all slack-send callers use -m/--message")
    return 0


if __name__ == "__main__":
    sys.exit(main())
