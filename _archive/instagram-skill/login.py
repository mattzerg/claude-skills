#!/usr/bin/env python3
"""
Instagram login bootstrap — one-shot script for first-time auth.

Opens a visible Chromium window at instagram.com/accounts/login.
Matt logs in by hand (incl. 2FA if needed).
Script polls for post-login state, then saves the session.

Usage:
    python3 ~/.claude/skills/instagram-skill/login.py [--account matteisn]

Session lands at ~/.claude/skills/instagram-skill/state/<account>/storage_state.json
Future skill verbs reuse this state headlessly — no re-login needed.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print(
        "ERROR: playwright not installed.\n"
        "Run: pip install playwright && playwright install chromium",
        file=sys.stderr,
    )
    sys.exit(1)


SKILL_DIR = Path.home() / ".claude" / "skills" / "instagram-skill"
DEFAULT_ACCOUNT = "matteisn"
LOGIN_URL = "https://www.instagram.com/accounts/login/"
POLL_INTERVAL_S = 2
MAX_WAIT_MIN = 10  # bail after 10 minutes


def is_logged_in(url: str) -> bool:
    """Heuristic: after login, IG redirects away from /accounts/login/ to home or onetap."""
    if "/accounts/login" in url:
        return False
    if "/accounts/onetap" in url:
        # post-login "save your login info" prompt — already authenticated
        return True
    if "instagram.com/challenge" in url:
        # 2FA or security challenge in progress — keep waiting
        return False
    # Anything else on instagram.com domain = logged in (home, profile, etc.)
    return "instagram.com" in url


def main() -> int:
    parser = argparse.ArgumentParser(description="Instagram login bootstrap.")
    parser.add_argument(
        "--account",
        default=DEFAULT_ACCOUNT,
        help=f"Account label (default: {DEFAULT_ACCOUNT}). Used as state subdir name.",
    )
    args = parser.parse_args()

    state_dir = SKILL_DIR / "state" / args.account
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / "storage_state.json"
    meta_file = state_dir / "meta.json"

    print(f"[instagram-login] Account: {args.account}")
    print(f"[instagram-login] State will save to: {state_file}")
    print(f"[instagram-login] Opening visible Chromium at {LOGIN_URL}")
    print(f"[instagram-login] Log in by hand. Script will auto-save session once login completes.")
    print(f"[instagram-login] If you close the window manually, that's fine too.")
    print()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/130.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        try:
            page.goto(LOGIN_URL, wait_until="domcontentloaded")
        except Exception as e:
            print(f"[instagram-login] WARN: navigation failed: {e}", file=sys.stderr)

        deadline = time.monotonic() + (MAX_WAIT_MIN * 60)
        last_url = ""
        saved = False

        while time.monotonic() < deadline:
            try:
                current_url = page.url
                if current_url != last_url:
                    print(f"[instagram-login] URL: {current_url}")
                    last_url = current_url

                if is_logged_in(current_url):
                    # Give one extra second for any final cookies to land
                    time.sleep(1)
                    context.storage_state(path=str(state_file))
                    meta_file.write_text(
                        json.dumps(
                            {
                                "account": args.account,
                                "logged_in_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                                "login_url_landing": current_url,
                            },
                            indent=2,
                        )
                    )
                    print(f"[instagram-login] OK — session saved to {state_file}")
                    saved = True
                    break

                time.sleep(POLL_INTERVAL_S)

            except KeyboardInterrupt:
                print("[instagram-login] Interrupted by user.")
                break
            except Exception as e:
                # Window closed manually, or other transient — try one final state save
                msg = str(e)
                if "closed" in msg.lower() or "target" in msg.lower():
                    print(f"[instagram-login] Browser appears closed. Attempting state save anyway.")
                    try:
                        context.storage_state(path=str(state_file))
                        saved = True
                        print(f"[instagram-login] State saved to {state_file}")
                    except Exception as e2:
                        print(f"[instagram-login] ERROR saving state: {e2}", file=sys.stderr)
                    break
                else:
                    print(f"[instagram-login] WARN: {e}", file=sys.stderr)
                    time.sleep(POLL_INTERVAL_S)

        if not saved:
            print(
                "[instagram-login] TIMEOUT — no login detected within "
                f"{MAX_WAIT_MIN} minutes. Closing without saving state.",
                file=sys.stderr,
            )
            try:
                browser.close()
            except Exception:
                pass
            return 2

        try:
            browser.close()
        except Exception:
            pass

    print(f"[instagram-login] Done. Account '{args.account}' is now session-cached.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
