#!/usr/bin/env python3
"""
instagram_skill.py — main CLI dispatcher for instagram-skill.

Subsumes the v0 bootstrap scripts (login.py, scrape_follows.py, sourcing_pipeline.py)
under one entry with verb dispatching. Adds read verbs (me, profile, posts, feed, saved, search).

Usage:
    instagram_skill.py login [--account L]
    instagram_skill.py accounts
    instagram_skill.py me [--account L]
    instagram_skill.py profile HANDLE [--account L]
    instagram_skill.py posts HANDLE [--limit N] [--account L]
    instagram_skill.py feed [--limit N] [--account L]
    instagram_skill.py saved [--limit N] [--account L]
    instagram_skill.py scrape-follows [--account L]
    instagram_skill.py source [--days N] [--write-queue]
    instagram_skill.py lint --file PATH | --text "..."
    instagram_skill.py queue list | show ID | approve ID | reject ID --reason ".."

Write verbs (post / story / reel) are deferred to v2 — confirmation gate stub raises NotImplementedError.

All output is JSON to stdout (channel-skill convention).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SKILL_DIR = Path.home() / ".claude" / "skills" / "instagram-skill"
STATE_DIR = SKILL_DIR / "state"


def err(msg: str, code: str = "error") -> dict:
    return {"ok": False, "error": code, "message": msg}


def ok(verb: str, account: str | None, data) -> dict:
    return {"ok": True, "verb": verb, "account": account, "data": data}


def state_file(account: str) -> Path:
    return STATE_DIR / account / "storage_state.json"


def require_session(account: str) -> Path | None:
    f = state_file(account)
    return f if f.exists() else None


# ---------------------------------------------------------------------------
# Subprocess wrappers — delegate to the v0 bootstrap scripts so we don't
# duplicate the Playwright code. Refactor inline later if needed.
# ---------------------------------------------------------------------------

def call_login(account: str) -> int:
    return subprocess.call([
        "/usr/bin/python3", "-u",
        str(SKILL_DIR / "login.py"),
        "--account", account,
    ])


def call_scrape_follows(account: str, extra: list[str]) -> int:
    return subprocess.call([
        "/usr/bin/python3",
        str(SKILL_DIR / "scrape_follows.py"),
        "--account", account,
        *extra,
    ])


def call_source(extra: list[str]) -> int:
    return subprocess.call([
        "/usr/bin/python3",
        str(SKILL_DIR / "sourcing_pipeline.py"),
        *extra,
    ])


def call_lint(extra: list[str]) -> int:
    return subprocess.call([
        "/usr/bin/python3",
        str(SKILL_DIR / "caption_lint.py"),
        *extra,
    ])


# ---------------------------------------------------------------------------
# Lazy Playwright helpers (used only by read verbs that need the live session)
# ---------------------------------------------------------------------------

def _playwright_context(account: str):
    """Returns (browser, context, page) using the saved session. Caller closes."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError("playwright not installed — run: pip install playwright && playwright install chromium")

    sf = require_session(account)
    if not sf:
        raise RuntimeError(f"no session for '{account}' — run: instagram_skill.py login --account {account}")

    p = sync_playwright().start()
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        storage_state=str(sf),
        viewport={"width": 1280, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
    )
    page = context.new_page()
    return p, browser, context, page


def _close_pw(p, browser):
    try:
        browser.close()
    except Exception:
        pass
    try:
        p.stop()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Verbs
# ---------------------------------------------------------------------------

def verb_accounts() -> dict:
    if not STATE_DIR.exists():
        return ok("accounts", None, {"accounts": [], "note": "no sessions yet"})
    accounts = []
    for d in sorted(STATE_DIR.iterdir()):
        if not d.is_dir():
            continue
        sf = d / "storage_state.json"
        meta = d / "meta.json"
        meta_data = {}
        if meta.exists():
            try:
                meta_data = json.loads(meta.read_text())
            except Exception:
                pass
        accounts.append({
            "label": d.name,
            "has_session": sf.exists(),
            "session_size": sf.stat().st_size if sf.exists() else 0,
            "meta": meta_data,
        })
    return ok("accounts", None, {"accounts": accounts})


def verb_me(account: str) -> dict:
    if not require_session(account):
        return err(f"no session for '{account}' — run: instagram_skill.py login --account {account}", "no_session")
    pw_objs = None
    try:
        pw_objs = _playwright_context(account)
        p, browser, context, page = pw_objs
        page.goto(f"https://www.instagram.com/{account}/", wait_until="domcontentloaded", timeout=20000)
        time.sleep(2)
        meta = page.evaluate("""
            () => {
                const m = document.querySelector('meta[name="description"]');
                const title = document.title;
                return {title, description: m ? m.getAttribute('content') : ''};
            }
        """)
        return ok("me", account, {"profile_url": f"https://www.instagram.com/{account}/", **meta})
    except Exception as e:
        return err(str(e), "playwright_error")
    finally:
        if pw_objs:
            _close_pw(pw_objs[0], pw_objs[1])


def verb_profile(account: str, handle: str) -> dict:
    if not require_session(account):
        return err(f"no session for '{account}'", "no_session")
    pw_objs = None
    try:
        pw_objs = _playwright_context(account)
        p, browser, context, page = pw_objs
        page.goto(f"https://www.instagram.com/{handle}/", wait_until="domcontentloaded", timeout=20000)
        time.sleep(2)
        meta = page.evaluate("""
            () => {
                const m = document.querySelector('meta[name="description"]');
                const og_title = document.querySelector('meta[property="og:title"]');
                return {
                    description: m ? m.getAttribute('content') : '',
                    og_title: og_title ? og_title.getAttribute('content') : '',
                    title: document.title,
                };
            }
        """)
        # Quick check for "page isn't available"
        body = page.evaluate("() => document.body.innerText.slice(0, 500)") or ""
        not_found = "Sorry, this page" in body or "isn't available" in body
        return ok("profile", account, {
            "handle": handle,
            "exists": not not_found,
            "url": f"https://www.instagram.com/{handle}/",
            **meta,
        })
    except Exception as e:
        return err(str(e), "playwright_error")
    finally:
        if pw_objs:
            _close_pw(pw_objs[0], pw_objs[1])


def verb_check_handles(account: str, handles: list[str]) -> dict:
    """Bulk-check availability for a list of handles via logged-in profile pages."""
    if not require_session(account):
        return err(f"no session for '{account}'", "no_session")
    pw_objs = None
    results = []
    try:
        pw_objs = _playwright_context(account)
        p, browser, context, page = pw_objs
        for h in handles:
            try:
                page.goto(f"https://www.instagram.com/{h}/", wait_until="domcontentloaded", timeout=15000)
                time.sleep(1.5)
                body = page.evaluate("() => document.body.innerText.slice(0, 500)") or ""
                title = page.title()
                available = "Sorry, this page" in body or "isn't available" in body or "Page Not Found" in title
                results.append({
                    "handle": h,
                    "available": available,
                    "url": f"https://www.instagram.com/{h}/",
                    "title": title,
                })
            except Exception as e:
                results.append({"handle": h, "available": None, "error": str(e)})
            time.sleep(1)
        return ok("check-handles", account, {"results": results})
    finally:
        if pw_objs:
            _close_pw(pw_objs[0], pw_objs[1])


def verb_queue_list(state_filter: str | None = None) -> dict:
    queue_dir = (
        Path.home() / "Obsidian/Zerg"
        / "MattZerg/Projects/detroit-hub/queue"
    )
    if not queue_dir.exists():
        return ok("queue-list", None, {"items": [], "count": 0})

    import re
    items = []
    for f in sorted(queue_dir.glob("*.md")):
        if f.name.startswith("_"):
            continue
        try:
            text = f.read_text()
            m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
            if not m:
                continue
            fm_text = m.group(1)
            fm = {}
            for line in fm_text.split("\n"):
                if ":" in line and not line.startswith(" "):
                    k, _, v = line.partition(":")
                    fm[k.strip()] = v.strip().strip("'\"")
            if state_filter and fm.get("state") != state_filter:
                continue
            items.append({
                "slug": fm.get("slug", f.stem),
                "scheduled": fm.get("scheduled", ""),
                "state": fm.get("state", ""),
                "surface": fm.get("surface", ""),
                "format": fm.get("format", ""),
                "copyright_posture": fm.get("copyright_posture", ""),
                "path": str(f),
            })
        except Exception:
            continue
    return ok("queue-list", None, {"items": items, "count": len(items)})


def verb_help() -> dict:
    return ok("help", None, {
        "verbs": {
            "accounts": "list authenticated accounts",
            "login --account L": "visible-browser login + save session",
            "me --account L": "show whoami for the session",
            "profile HANDLE [--account L]": "fetch bio + meta for a handle",
            "check-handles H1 H2 ... [--account L]": "batch availability check",
            "scrape-follows [--account L]": "scrape Matt's follows -> seed-corpus.md",
            "source [--days N] [--write-queue]": "scrape RA/19hz events -> queue/",
            "lint --file PATH | --text \"...\"": "caption lint (anti-pattern check)",
            "queue list [--state S]": "list queue items, optionally filtered by state",
        },
        "see_also": ["~/.claude/skills/instagram-skill/SKILL.md", "~/.claude/plans/i-want-to-build-jaunty-puzzle.md"],
    })


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(json.dumps(verb_help(), indent=2))
        return 0

    verb = argv[0]
    rest = argv[1:]

    # Verbs that delegate to bootstrap scripts (exec, not import)
    if verb == "login":
        # pass through --account if present
        account = "matteisn"
        if "--account" in rest:
            account = rest[rest.index("--account") + 1]
        return call_login(account)
    if verb == "scrape-follows":
        account = "matteisn"
        extra = list(rest)
        if "--account" in extra:
            i = extra.index("--account")
            account = extra[i + 1]
            del extra[i:i+2]
        return call_scrape_follows(account, extra)
    if verb == "source":
        return call_source(rest)
    if verb == "lint":
        return call_lint(rest)

    # In-process verbs
    p = argparse.ArgumentParser(prog=f"instagram_skill.py {verb}")
    p.add_argument("--account", default="matteisn")
    p.add_argument("--state", default=None, help="filter for queue list")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("positional", nargs="*")
    args = p.parse_args(rest)

    if verb == "accounts":
        result = verb_accounts()
    elif verb == "me":
        result = verb_me(args.account)
    elif verb == "profile":
        if not args.positional:
            result = err("profile requires HANDLE", "usage")
        else:
            result = verb_profile(args.account, args.positional[0])
    elif verb == "check-handles":
        if not args.positional:
            result = err("check-handles requires at least one HANDLE", "usage")
        else:
            result = verb_check_handles(args.account, args.positional)
    elif verb in ("queue", "queue-list"):
        # support `queue list` and `queue list --state X`
        positional = args.positional
        subverb = positional[0] if positional else "list"
        if subverb == "list":
            result = verb_queue_list(state_filter=args.state)
        else:
            result = err(f"queue subverb '{subverb}' not implemented", "not_implemented")
    else:
        result = err(f"unknown verb '{verb}' — try `instagram_skill.py help`", "unknown_verb")

    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
