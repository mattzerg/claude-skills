#!/usr/bin/env python3
"""Open a visible Chromium pointed at <url>, wait for the user to log in, then exit.

The persistent_context directory captures cookies + storage so subsequent runs
of run.py --session <name> can crawl behind the auth wall.

Usage:
  python3 login_session.py <session_name> <login_url> [--success-url URL_FRAGMENT]

Quit the browser window when done logging in. Session is saved on close.
"""
from __future__ import annotations
import argparse
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

SKILL_ROOT = Path(__file__).resolve().parent
SESSIONS_ROOT = SKILL_ROOT / "sessions"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("session", help="Name for session dir (e.g. 'ca-org')")
    p.add_argument("url", help="URL to open (typically the login page)")
    p.add_argument("--success-url", default=None, help="If set, auto-close once URL contains this substring")
    p.add_argument("--timeout", type=int, default=600, help="Seconds before giving up (default 600)")
    args = p.parse_args()

    session_dir = SESSIONS_ROOT / args.session
    session_dir.mkdir(parents=True, exist_ok=True)
    print(f"[session] persistent_context → {session_dir}")
    print(f"[browser] opening {args.url} (visible window)")
    print("[browser] log in, then close the window — or wait for auto-close.")

    with sync_playwright() as pw:
        ctx = pw.chromium.launch_persistent_context(
            str(session_dir),
            headless=False,
            viewport={"width": 1440, "height": 900},
            ignore_https_errors=True,
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(args.url)

        if args.success_url:
            deadline = time.time() + args.timeout
            while time.time() < deadline:
                try:
                    if args.success_url in page.url:
                        print(f"[browser] success_url match: {page.url}")
                        time.sleep(2)
                        break
                except Exception:
                    pass
                time.sleep(1)
            else:
                print("[browser] timed out waiting for success_url")
        else:
            try:
                page.wait_for_event("close", timeout=args.timeout * 1000)
            except Exception:
                print(f"[browser] {args.timeout}s elapsed — closing")

        try:
            ctx.close()
        except Exception:
            pass

    print(f"[session] saved → {session_dir}")
    print(f"[next] python3 run.py <url> --session {args.session}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
