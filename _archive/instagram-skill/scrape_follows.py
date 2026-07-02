#!/usr/bin/env python3
"""
Scrape Matt's IG follows, saves, and bio of music/nightlife matches.

Uses the storage_state.json from `login.py` for an authenticated session.
Output: seed-corpus.md in the Detroit hub project folder.

Usage:
    python3 ~/.claude/skills/instagram-skill/scrape_follows.py [--account matteisn]
                                                                [--max-follows 600]
                                                                [--out PATH]

Strategy:
1. Open /<username>/ to confirm session works and read username.
2. Open /<username>/following/ modal, scroll to load all follows (capped).
3. Filter handles by music/nightlife keyword heuristics on handle name + bio.
4. For top matches, visit each profile to extract bio + counts.
5. Write seed-corpus.md with sections: All follows, Music/nightlife filter,
   Detroit-anchored subset, Top voice anchors.

Rate-limit-aware: 3-5s sleeps between scrolls/profile loads.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    print("ERROR: playwright not installed.", file=sys.stderr)
    sys.exit(1)


SKILL_DIR = Path.home() / ".claude" / "skills" / "instagram-skill"
DEFAULT_ACCOUNT = "matteisn"
DEFAULT_OUT = (
    Path.home()
    / "Obsidian/Zerg"
    / "MattZerg/Projects/detroit-hub/seed-corpus.md"
)
DEFAULT_MAX_FOLLOWS = 800

# Music/nightlife keyword heuristics — applied to handle name AND bio text.
MUSIC_KEYWORDS = {
    # generic music
    "music", "records", "label", "radio", "fm", "sound", "studio", "audio",
    "vinyl", "wax", "dj", "deejay", "producer", "mixtape", "mix",
    # genre / scene
    "techno", "house", "electronic", "edm", "rave", "club", "afters",
    "dance", "ambient", "jungle", "drum", "bass", "dnb", "hardcore",
    "minimal", "deep", "garage", "disco", "funk", "soul", "jazz",
    "hip", "hop", "rap", "trap", "boombap", "soundsystem",
    "metal", "punk", "indie", "rock", "shoegaze", "synth",
    # venue / events
    "venue", "club", "warehouse", "loft", "afterhours", "afters",
    "nightlife", "boiler", "openair", "festival", "fest", "party",
    "promote", "promoter", "event", "lineup", "live", "concert",
    # Detroit specific (high signal)
    "detroit", "313", "motor", "motown", "movement",
    "submerge", "metroplex", "underground", "transmission",
    "spotlite", "tv lounge", "marble", "elclub", "magicstick",
    # other cities for context (lower signal but worth tagging)
    "nyc", "brooklyn", "berlin", "london", "la", "chicago",
}

DETROIT_KEYWORDS = {
    "detroit", "313", "motor city", "motown", "movement",
    "submerge", "metroplex", "underground resistance", "ithq",
    "spotlite", "tv lounge", "marble bar", "el club", "magic stick",
    "michigan", "ann arbor", "ferndale", "hamtramck",
}


def is_music_match(handle: str, bio: str = "") -> tuple[bool, list[str]]:
    """Returns (is_match, matching_keywords)."""
    blob = f"{handle.lower()} {bio.lower()}"
    matches = [kw for kw in MUSIC_KEYWORDS if kw in blob]
    return (len(matches) > 0, matches)


def is_detroit(handle: str, bio: str = "") -> bool:
    blob = f"{handle.lower()} {bio.lower()}"
    return any(kw in blob for kw in DETROIT_KEYWORDS)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--account", default=DEFAULT_ACCOUNT)
    parser.add_argument("--max-follows", type=int, default=DEFAULT_MAX_FOLLOWS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--enrich-limit", type=int, default=80,
        help="Max number of music-match profiles to bio-enrich (rate-limit safe)"
    )
    parser.add_argument(
        "--skip-enrich", action="store_true",
        help="Skip per-profile bio enrichment (faster, less detail)"
    )
    args = parser.parse_args()

    state_file = SKILL_DIR / "state" / args.account / "storage_state.json"
    if not state_file.exists():
        print(
            f"ERROR: no session found at {state_file}\n"
            f"Run: python3 ~/.claude/skills/instagram-skill/login.py --account {args.account}",
            file=sys.stderr,
        )
        return 1

    print(f"[scrape] Loading session from {state_file}")
    args.out.parent.mkdir(parents=True, exist_ok=True)

    follows: list[str] = []
    username_resolved = args.account

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            storage_state=str(state_file),
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/130.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        # Step 1: get logged-in username
        print(f"[scrape] Confirming session by visiting /{args.account}/")
        try:
            page.goto(f"https://www.instagram.com/{args.account}/", wait_until="domcontentloaded", timeout=20000)
            time.sleep(3)
            title = page.title()
            print(f"[scrape] Profile page title: {title}")
            if "Login" in title or "Sign up" in title:
                print("[scrape] ERROR: session appears stale. Re-run login.py.", file=sys.stderr)
                browser.close()
                return 2
        except PWTimeout:
            print("[scrape] Profile page load timeout — continuing anyway.", file=sys.stderr)

        # Step 2: open following modal
        following_url = f"https://www.instagram.com/{args.account}/following/"
        print(f"[scrape] Opening follows: {following_url}")
        try:
            page.goto(following_url, wait_until="domcontentloaded", timeout=20000)
        except PWTimeout:
            print("[scrape] Follows page load timeout, retrying once...")
            time.sleep(3)
            page.goto(following_url, wait_until="domcontentloaded", timeout=20000)

        time.sleep(4)  # let modal/dialog populate

        # IG's follow dialog is a div with role="dialog" containing a scrollable inner div
        # Find the scrollable list and scroll it
        print("[scrape] Scrolling follow list...")
        seen = set()
        no_new_iterations = 0
        max_iterations = 100
        for i in range(max_iterations):
            # Extract current handles via JS — IG renders /<handle>/ as anchor hrefs in the dialog
            handles = page.evaluate("""
                () => {
                    const dialog = document.querySelector('div[role="dialog"]');
                    const root = dialog || document;
                    const links = root.querySelectorAll('a[href^="/"][role="link"]');
                    const out = new Set();
                    for (const a of links) {
                        const h = a.getAttribute('href');
                        if (!h) continue;
                        const m = h.match(/^\\/([A-Za-z0-9_.]+)\\/$/);
                        if (m && !['explore','reels','direct','accounts','p'].includes(m[1])) {
                            out.add(m[1]);
                        }
                    }
                    return Array.from(out);
                }
            """)
            before = len(seen)
            for h in handles:
                seen.add(h)
            after = len(seen)
            new = after - before
            print(f"[scrape]   iter {i+1}: +{new} new (total {after})")

            if after >= args.max_follows:
                print(f"[scrape] Hit cap ({args.max_follows}). Stopping.")
                break

            if new == 0:
                no_new_iterations += 1
                if no_new_iterations >= 4:
                    print("[scrape] No new handles in 4 consecutive scrolls — assuming done.")
                    break
            else:
                no_new_iterations = 0

            # Scroll the dialog's inner scrollable area
            page.evaluate("""
                () => {
                    const dialog = document.querySelector('div[role="dialog"]');
                    if (!dialog) {
                        window.scrollBy(0, 2000);
                        return;
                    }
                    // Find the scrollable child
                    const candidates = dialog.querySelectorAll('*');
                    for (const el of candidates) {
                        const cs = window.getComputedStyle(el);
                        if ((cs.overflowY === 'auto' || cs.overflowY === 'scroll') &&
                            el.scrollHeight > el.clientHeight) {
                            el.scrollTop = el.scrollHeight;
                            return;
                        }
                    }
                    window.scrollBy(0, 2000);
                }
            """)
            time.sleep(2.5)

        follows = sorted(seen - {args.account})  # exclude self
        print(f"[scrape] Total follows captured: {len(follows)}")

        # Step 3: keyword filter
        matches: list[dict] = []
        for h in follows:
            ok, kws = is_music_match(h)
            if ok:
                matches.append({"handle": h, "match_keywords": kws, "bio": "", "is_detroit": is_detroit(h)})

        print(f"[scrape] Music/nightlife handle-keyword matches: {len(matches)}")

        # Step 4: enrich top N music matches with bio
        if not args.skip_enrich:
            enrich_n = min(args.enrich_limit, len(matches))
            print(f"[scrape] Enriching {enrich_n} profiles with bio...")
            for idx, m in enumerate(matches[:enrich_n]):
                h = m["handle"]
                try:
                    page.goto(f"https://www.instagram.com/{h}/", wait_until="domcontentloaded", timeout=15000)
                    time.sleep(2)
                    bio = page.evaluate("""
                        () => {
                            const m = document.querySelector('meta[name="description"]');
                            if (m) return m.getAttribute('content') || '';
                            return '';
                        }
                    """) or ""
                    m["bio"] = bio
                    ok2, kws2 = is_music_match(h, bio)
                    m["match_keywords"] = sorted(set(m["match_keywords"]) | set(kws2))
                    m["is_detroit"] = is_detroit(h, bio)
                    print(f"[scrape]   ({idx+1}/{enrich_n}) @{h} -- {bio[:80]}")
                except Exception as e:
                    print(f"[scrape]   ({idx+1}/{enrich_n}) @{h} -- enrich failed: {e}", file=sys.stderr)
                time.sleep(2.5)  # rate-limit politeness

        # Also enrich any non-music-keyword handles that might still be relevant
        # (skipped for speed — Matt can re-run with different filters)

        try:
            browser.close()
        except Exception:
            pass

    # Step 5: write seed-corpus.md
    detroit_matches = [m for m in matches if m["is_detroit"]]
    print(f"[scrape] Detroit-anchored matches: {len(detroit_matches)}")

    lines = [
        "---",
        "project: detroit-hub",
        "type: seed-corpus",
        f"scraped: {time.strftime('%Y-%m-%d %H:%M %Z')}",
        f"account: @{args.account}",
        f"follow_count_captured: {len(follows)}",
        f"music_matches: {len(matches)}",
        f"detroit_matches: {len(detroit_matches)}",
        "---",
        "",
        "# Seed Corpus — Matt's Music/Nightlife IG Follows",
        "",
        "Scraped from `@matteisn` follows via the new instagram-skill Playwright session.",
        "Music/nightlife filter is keyword-based on handle + bio.",
        "",
        "## Detroit-anchored matches (highest signal)",
        "",
    ]
    if detroit_matches:
        lines.append("| Handle | Bio | Keywords |")
        lines.append("|---|---|---|")
        for m in sorted(detroit_matches, key=lambda x: x["handle"]):
            bio_short = (m["bio"] or "").replace("|", "/").replace("\n", " ")[:120]
            kws = ", ".join(m["match_keywords"][:6])
            lines.append(f"| [@{m['handle']}](https://instagram.com/{m['handle']}/) | {bio_short} | {kws} |")
    else:
        lines.append("*No Detroit-anchored matches in current keyword set. May need bio enrichment expansion.*")

    lines.extend(["", "## All music/nightlife matches", ""])
    lines.append("| Handle | Bio | Keywords | Detroit? |")
    lines.append("|---|---|---|---|")
    for m in sorted(matches, key=lambda x: (not x["is_detroit"], x["handle"])):
        bio_short = (m["bio"] or "").replace("|", "/").replace("\n", " ")[:120]
        kws = ", ".join(m["match_keywords"][:6])
        d = "✅" if m["is_detroit"] else ""
        lines.append(f"| [@{m['handle']}](https://instagram.com/{m['handle']}/) | {bio_short} | {kws} | {d} |")

    lines.extend(["", "## All captured follows (raw)", ""])
    lines.append(f"Total: {len(follows)} handles")
    lines.append("")
    lines.append("<details><summary>Click to expand full list</summary>")
    lines.append("")
    for h in follows:
        lines.append(f"- [@{h}](https://instagram.com/{h}/)")
    lines.append("")
    lines.append("</details>")
    lines.append("")

    args.out.write_text("\n".join(lines))
    print(f"[scrape] Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
