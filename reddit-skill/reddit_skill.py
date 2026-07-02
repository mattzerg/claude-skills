#!/usr/bin/env python3
"""Reddit Skill — Playwright-driven Reddit channel skill.

Drives a logged-in Chromium session per account. The Reddit Data API is gated
for non-enterprise access as of 2026-05-09, so this skill automates the web UI
through a persistent Playwright context.

Sibling of twitter-skill / linkedin-skill / slack-skill. Same conventions:
subcommand verbs, JSON output, account abstraction, confirmation-before-write.

Usage:
    python3 reddit_skill.py accounts
    python3 reddit_skill.py login [--account LABEL]
    python3 reddit_skill.py logout [--account LABEL]
    python3 reddit_skill.py me [--account LABEL]
    python3 reddit_skill.py subreddit NAME [--sort hot|new|top|rising] [--limit N] [--account LABEL]
    python3 reddit_skill.py search QUERY [--subreddit NAME] [--limit N] [--account LABEL]
    python3 reddit_skill.py post SUBREDDIT --title "..." [--body "..."|--url "..."] [--account LABEL]
    python3 reddit_skill.py comment POST_URL --body "..." [--account LABEL]

All commands print a single JSON object. Errors use:
    {"ok": false, "verb": ..., "error": "<code>", "message": "<human>"}

DO NOT log in or post without explicit user confirmation (see SKILL.md).
DO NOT submit Zerg-domain URLs without UTM params (utm-attribution skill).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

# ---------------------------------------------------------------------------
# Paths and constants
# ---------------------------------------------------------------------------

SKILL_DIR = Path(__file__).parent
STATE_DIR = SKILL_DIR / "state"
CONFIG_FILE = SKILL_DIR / "config.json"
SELECTORS_FILE = SKILL_DIR / "selectors.json"

STATE_DIR.mkdir(parents=True, exist_ok=True)

REDDIT_BASE = "https://www.reddit.com"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
LOGIN_URL = f"{REDDIT_BASE}/login/"
LOGIN_POLL_INTERVAL_S = 2
LOGIN_TIMEOUT_S = 300  # 5 min

# Zerg domains that require UTM enforcement. Kept in sync with utm-attribution.
ZERG_DOMAINS = {
    "zergai.com", "www.zergai.com",
    "zergboard.ai", "www.zergboard.ai",
    "zerglytics.fly.dev",
    "zergboard-preview.pages.dev",
}
ZERG_DOMAIN_SUFFIXES = (".zergai.com",)

URL_RE = re.compile(r"https?://[^\s)\]]+", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Output envelope
# ---------------------------------------------------------------------------

def emit(payload: dict) -> None:
    """Print a single JSON object to stdout, then exit non-zero if not ok."""
    print(json.dumps(payload, indent=2, default=str))
    sys.exit(0 if payload.get("ok") else 1)


def err(verb: str, code: str, message: str, **extra) -> None:
    payload = {"ok": False, "verb": verb, "error": code, "message": message}
    payload.update(extra)
    emit(payload)


def ok(verb: str, **data) -> None:
    payload = {"ok": True, "verb": verb}
    payload.update(data)
    emit(payload)


# ---------------------------------------------------------------------------
# Account state
# ---------------------------------------------------------------------------

def safe_label(label: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in label)


def account_dir(label: str) -> Path:
    return STATE_DIR / safe_label(label)


def storage_state_path(label: str) -> Path:
    return account_dir(label) / "storage_state.json"


def meta_path(label: str) -> Path:
    return account_dir(label) / "meta.json"


def list_accounts() -> list[dict]:
    out = []
    if not STATE_DIR.exists():
        return out
    for child in sorted(STATE_DIR.iterdir()):
        if not child.is_dir():
            continue
        ss = child / "storage_state.json"
        mt = child / "meta.json"
        meta = {}
        if mt.exists():
            try:
                meta = json.loads(mt.read_text())
            except Exception:
                meta = {}
        out.append({
            "label": child.name,
            "username": meta.get("username"),
            "has_session": ss.exists(),
            "last_login": meta.get("last_login"),
            "stale": _is_stale(meta.get("last_login")),
        })
    return out


def _is_stale(iso: Optional[str]) -> bool:
    if not iso:
        return True
    try:
        last = datetime.fromisoformat(iso)
    except Exception:
        return True
    return (datetime.now(timezone.utc) - last).days > 30


def resolve_account(verb: str, requested: Optional[str]) -> str:
    """Resolve which account label to use; error envelope if ambiguous/absent."""
    accounts = list_accounts()
    if requested:
        return requested
    authed = [a for a in accounts if a["has_session"]]
    if len(authed) == 1:
        return authed[0]["label"]
    if not authed:
        err(verb, "no_session",
            "No accounts authenticated. Run: reddit_skill.py login --account <label>")
    err(verb, "ambiguous_account",
        f"Multiple accounts available — pass --account. Found: {[a['label'] for a in authed]}")


# ---------------------------------------------------------------------------
# UTM enforcement
# ---------------------------------------------------------------------------

def is_zerg_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    if not host:
        return False
    if host in ZERG_DOMAINS:
        return True
    return any(host.endswith(s) for s in ZERG_DOMAIN_SUFFIXES)


def has_utm(url: str) -> bool:
    qs = parse_qs(urlparse(url).query)
    return bool(qs.get("utm_source"))


def check_utm_compliance(verb: str, *fields: str) -> None:
    """Hard-fail if any Zerg URL in any field lacks utm_source.

    Non-Zerg URLs are allowed through unchanged.
    """
    offenders = []
    for field in fields:
        if not field:
            continue
        for url in URL_RE.findall(field):
            # strip trailing punctuation that regex caught
            url = url.rstrip(".,;:!?")
            if is_zerg_url(url) and not has_utm(url):
                offenders.append(url)
    if offenders:
        err(
            verb, "missing_utm",
            "Zerg URL(s) detected without utm_source. Route through utm-attribution skill first.",
            offenders=offenders,
            hint="python3 ~/.claude/skills/utm-attribution/run.py build --destination ... --source reddit --medium community --campaign <slug>",
        )


# ---------------------------------------------------------------------------
# Playwright lazy import
# ---------------------------------------------------------------------------

def require_playwright(verb: str):
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return sync_playwright
    except ImportError:
        err(verb, "playwright_not_installed",
            "Playwright not installed. Run: pip install playwright && playwright install chromium")


# ---------------------------------------------------------------------------
# Selectors (drift resilience)
# ---------------------------------------------------------------------------

DEFAULT_SELECTORS = {
    "submit_title": "textarea[name=title], faceplate-textarea-input[name=title] textarea",
    "submit_body": "div[contenteditable=true], textarea[name=text]",
    "submit_url": "input[name=url]",
    "submit_button": "button[type=submit]",
    "comment_box": "div[contenteditable=true][slot=rte]",
    "comment_submit": "button:has-text('Comment')",
    "post_card": "shreddit-post, article",
    "post_title": "a[slot=title], h3",
    "search_result": "shreddit-post, article",
    "login_done_url_excludes": "/login",
}


def load_selectors() -> dict:
    if SELECTORS_FILE.exists():
        try:
            user = json.loads(SELECTORS_FILE.read_text())
            merged = {**DEFAULT_SELECTORS, **user}
            return merged
        except Exception:
            pass
    return DEFAULT_SELECTORS


# ---------------------------------------------------------------------------
# Browser context helpers
# ---------------------------------------------------------------------------

def open_context(verb: str, label: str, *, headless: bool, require_session: bool):
    """Return (playwright, browser, context, page). Caller closes."""
    sync_playwright = require_playwright(verb)
    ss = storage_state_path(label)
    if require_session and not ss.exists():
        err(verb, "no_session",
            f"No saved session for account '{label}'. Run: reddit_skill.py login --account {label}")

    p = sync_playwright().start()
    browser = p.chromium.launch(
        headless=headless,
        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
    )
    context_kwargs = {
        "viewport": {"width": 1280, "height": 900},
        "user_agent": USER_AGENT,
    }
    if ss.exists():
        context_kwargs["storage_state"] = str(ss)
    context = browser.new_context(**context_kwargs)
    page = context.new_page()
    return p, browser, context, page


def save_state(context, label: str, username: Optional[str] = None) -> None:
    account_dir(label).mkdir(parents=True, exist_ok=True)
    context.storage_state(path=str(storage_state_path(label)))
    meta = {}
    if meta_path(label).exists():
        try:
            meta = json.loads(meta_path(label).read_text())
        except Exception:
            meta = {}
    meta["last_login"] = datetime.now(timezone.utc).isoformat()
    if username:
        meta["username"] = username
    meta["label"] = label
    meta_path(label).write_text(json.dumps(meta, indent=2))
    try:
        os.chmod(storage_state_path(label), 0o600)
        os.chmod(meta_path(label), 0o600)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Verbs
# ---------------------------------------------------------------------------

def verb_accounts(args) -> None:
    accounts = list_accounts()
    note = None
    if not accounts:
        note = "No accounts authenticated. Run: reddit_skill.py login --account <label>"
    ok("accounts", accounts=accounts, note=note)


def verb_login(args) -> None:
    label = args.account or "default"
    require_playwright("login")
    print(f"Launching visible Chromium for account '{label}'...", file=sys.stderr)
    print("Log in manually. The script will detect post-login redirect and save state.",
          file=sys.stderr)
    print(f"Timeout: {LOGIN_TIMEOUT_S}s. Press Ctrl-C to abort.", file=sys.stderr)

    p, browser, context, page = open_context(
        "login", label, headless=False, require_session=False,
    )
    try:
        page.goto(LOGIN_URL, wait_until="domcontentloaded")
        deadline = time.time() + LOGIN_TIMEOUT_S
        while time.time() < deadline:
            current = page.url
            if "/login" not in current and "reddit.com" in current:
                break
            time.sleep(LOGIN_POLL_INTERVAL_S)
        else:
            err("login", "login_timeout",
                f"Did not detect post-login redirect within {LOGIN_TIMEOUT_S}s.")

        username = None
        try:
            page.goto(f"{REDDIT_BASE}/api/me.json", wait_until="domcontentloaded")
            body = page.evaluate("() => document.body.innerText")
            data = json.loads(body)
            username = data.get("name") or (data.get("data") or {}).get("name")
        except Exception:
            pass

        save_state(context, label, username=username)
        ok("login", account=label, username=username,
           state_path=str(storage_state_path(label)))
    finally:
        try:
            context.close(); browser.close(); p.stop()
        except Exception:
            pass


def verb_logout(args) -> None:
    label = args.account
    if not label:
        err("logout", "missing_account", "Pass --account <label>")
    d = account_dir(label)
    if not d.exists():
        err("logout", "not_found", f"No saved state for account '{label}'.")
    import shutil
    shutil.rmtree(d)
    ok("logout", account=label, note="Local session deleted. Revoke on Reddit side separately if needed.")


def verb_me(args) -> None:
    label = resolve_account("me", args.account)
    p, browser, context, page = open_context(
        "me", label, headless=True, require_session=True,
    )
    try:
        page.goto(f"{REDDIT_BASE}/api/me.json", wait_until="domcontentloaded")
        body = page.evaluate("() => document.body.innerText")
        data = json.loads(body)
        if not data or not (data.get("name") or (data.get("data") or {}).get("name")):
            err("me", "session_expired",
                f"Session for '{label}' appears expired. Re-run: login --account {label}")
        # persist any cookie refresh
        save_state(context, label, username=(data.get("name") or (data.get("data") or {}).get("name")))
        ok("me", account=label, profile=data)
    finally:
        try:
            context.close(); browser.close(); p.stop()
        except Exception:
            pass


def _extract_post_cards(page, limit: int) -> list[dict]:
    """Best-effort post-card extraction. Selectors live in selectors.json."""
    sel = load_selectors()
    js = """
    (sel) => {
      const cards = Array.from(document.querySelectorAll(sel.post_card)).slice(0, sel.limit);
      return cards.map(c => {
        const link = c.querySelector('a[slot=title], a[data-click-id=body], a[href*="/comments/"]');
        const title = (c.querySelector(sel.post_title) || link || c).innerText || '';
        const href = link ? link.getAttribute('href') : null;
        return {
          title: title.trim().slice(0, 300),
          url: href ? (href.startsWith('http') ? href : 'https://www.reddit.com' + href) : null,
        };
      });
    }
    """
    try:
        return page.evaluate(js, {"post_card": sel["post_card"], "post_title": sel["post_title"], "limit": limit})
    except Exception:
        return []


def verb_subreddit(args) -> None:
    label = resolve_account("subreddit", args.account)
    sub = args.name.lstrip("r/").strip("/")
    sort = args.sort or "hot"
    limit = args.limit or 25
    p, browser, context, page = open_context(
        "subreddit", label, headless=True, require_session=True,
    )
    try:
        url = f"{REDDIT_BASE}/r/{sub}/{sort}/"
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        posts = _extract_post_cards(page, limit)
        ok("subreddit", account=label, subreddit=sub, sort=sort,
           url=url, count=len(posts), posts=posts)
    finally:
        try:
            context.close(); browser.close(); p.stop()
        except Exception:
            pass


def verb_search(args) -> None:
    label = resolve_account("search", args.account)
    q = args.query
    limit = args.limit or 25
    if args.subreddit:
        url = f"{REDDIT_BASE}/r/{args.subreddit.lstrip('r/').strip('/')}/search/?q={q}&restrict_sr=1"
    else:
        url = f"{REDDIT_BASE}/search/?q={q}"
    p, browser, context, page = open_context(
        "search", label, headless=True, require_session=True,
    )
    try:
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_timeout(1500)
        posts = _extract_post_cards(page, limit)
        ok("search", account=label, query=q, subreddit=args.subreddit,
           url=url, count=len(posts), posts=posts)
    finally:
        try:
            context.close(); browser.close(); p.stop()
        except Exception:
            pass


def verb_post(args) -> None:
    if not args.body and not args.url:
        err("post", "missing_content", "Pass --body or --url.")
    if args.body and args.url:
        err("post", "ambiguous_content", "Pass exactly one of --body or --url.")
    check_utm_compliance("post", args.title or "", args.body or "", args.url or "")

    label = resolve_account("post", args.account)
    sub = args.subreddit.lstrip("r/").strip("/")
    sel = load_selectors()

    p, browser, context, page = open_context(
        "post", label, headless=False, require_session=True,
    )
    try:
        page.goto(f"{REDDIT_BASE}/r/{sub}/submit", wait_until="domcontentloaded")
        page.wait_for_timeout(1500)

        # Title
        try:
            page.fill(sel["submit_title"], args.title, timeout=10_000)
        except Exception as e:
            err("post", "title_selector_failed",
                f"Could not fill title. Selector drift? Update selectors.json. Detail: {e}")

        # Body or URL
        if args.url:
            try:
                # Click link tab if present
                try:
                    page.click("button:has-text('Link')", timeout=2000)
                except Exception:
                    pass
                page.fill(sel["submit_url"], args.url, timeout=10_000)
            except Exception as e:
                err("post", "url_selector_failed", f"Could not fill URL field. Detail: {e}")
        else:
            try:
                page.fill(sel["submit_body"], args.body, timeout=10_000)
            except Exception as e:
                err("post", "body_selector_failed", f"Could not fill body field. Detail: {e}")

        # DRY RUN BY DEFAULT — only submit if --confirm-submit
        if not args.confirm_submit:
            ok("post", account=label, subreddit=sub, dry_run=True,
               note="Form filled. Re-run with --confirm-submit to actually submit.",
               title=args.title)
            return

        try:
            page.click(sel["submit_button"], timeout=10_000)
            page.wait_for_load_state("networkidle", timeout=30_000)
        except Exception as e:
            err("post", "submit_failed", f"Submit click failed. Detail: {e}")

        # save fresh state
        save_state(context, label)
        ok("post", account=label, subreddit=sub, submitted=True,
           url=page.url, title=args.title)
    finally:
        try:
            context.close(); browser.close(); p.stop()
        except Exception:
            pass


def verb_comment(args) -> None:
    check_utm_compliance("comment", args.body or "")
    label = resolve_account("comment", args.account)
    sel = load_selectors()

    p, browser, context, page = open_context(
        "comment", label, headless=False, require_session=True,
    )
    try:
        page.goto(args.post_url, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        try:
            page.click(sel["comment_box"], timeout=10_000)
            page.keyboard.type(args.body)
        except Exception as e:
            err("comment", "comment_box_failed",
                f"Could not enter comment text. Detail: {e}")

        if not args.confirm_submit:
            ok("comment", account=label, post_url=args.post_url, dry_run=True,
               note="Comment drafted in box. Re-run with --confirm-submit to actually post.")
            return

        try:
            page.click(sel["comment_submit"], timeout=10_000)
            page.wait_for_load_state("networkidle", timeout=30_000)
        except Exception as e:
            err("comment", "submit_failed", f"Submit click failed. Detail: {e}")

        save_state(context, label)
        ok("comment", account=label, post_url=args.post_url, submitted=True)
    finally:
        try:
            context.close(); browser.close(); p.stop()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="reddit_skill.py",
        description="Reddit channel skill (Playwright-driven). See SKILL.md.",
    )
    sub = p.add_subparsers(dest="verb", required=True)

    a = sub.add_parser("accounts", help="List authenticated accounts")
    a.set_defaults(func=verb_accounts)

    l = sub.add_parser("login", help="Open visible Chromium to log in manually")
    l.add_argument("--account", help="Account label (default: 'default')")
    l.set_defaults(func=verb_login)

    o = sub.add_parser("logout", help="Delete local session state for an account")
    o.add_argument("--account", required=True)
    o.set_defaults(func=verb_logout)

    m = sub.add_parser("me", help="Current user info via /api/me.json")
    m.add_argument("--account")
    m.set_defaults(func=verb_me)

    s = sub.add_parser("subreddit", help="Read subreddit listing")
    s.add_argument("name", help="Subreddit name, with or without r/ prefix")
    s.add_argument("--sort", choices=["hot", "new", "top", "rising"], default="hot")
    s.add_argument("--limit", type=int, default=25)
    s.add_argument("--account")
    s.set_defaults(func=verb_subreddit)

    sr = sub.add_parser("search", help="Search Reddit (optionally scoped to subreddit)")
    sr.add_argument("query")
    sr.add_argument("--subreddit", help="Restrict to this subreddit")
    sr.add_argument("--limit", type=int, default=25)
    sr.add_argument("--account")
    sr.set_defaults(func=verb_search)

    po = sub.add_parser("post", help="Submit a post (DRY-RUN unless --confirm-submit)")
    po.add_argument("subreddit")
    po.add_argument("--title", required=True)
    po.add_argument("--body", help="Self-text body")
    po.add_argument("--url", help="Link URL (for link posts)")
    po.add_argument("--confirm-submit", action="store_true",
                    help="REQUIRED to actually submit. Without it, fills form and stops.")
    po.add_argument("--account")
    po.set_defaults(func=verb_post)

    co = sub.add_parser("comment", help="Comment on a post (DRY-RUN unless --confirm-submit)")
    co.add_argument("post_url")
    co.add_argument("--body", required=True)
    co.add_argument("--confirm-submit", action="store_true")
    co.add_argument("--account")
    co.set_defaults(func=verb_comment)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
