#!/usr/bin/env python3
"""Fake Matt feedback — learning loop.

For each owned-target run logged in sent-log.jsonl, periodically re-fetch
each page (lightweight urllib GET, no playwright) and diff body text against
the snapshot. If pages have changed substantively, append corrections to
corrections.md so promote.py can mine them.

Intentionally lightweight (urllib, not playwright) — just text diff. Picks
up "Matt edited the page" signal without full browser re-capture cost.

Usage:
    python3 ~/.claude/skills/fakematt-feedback/learn.py [--max-age-days 90]
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

SKILL_DIR = Path(__file__).parent
SENT_LOG = SKILL_DIR / "sent-log.jsonl"
CORRECTIONS = SKILL_DIR / "corrections.md"
MAX_PAGES_PER_RUN = 6   # cap re-fetches per logged run
TIMEOUT = 15
USER_AGENT = "fakematt-feedback-learn/1.0"


def fetch_text(url: str) -> str | None:
    """Lightweight HTTP GET; strip HTML to plain text."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            html = r.read().decode("utf-8", errors="ignore")
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError):
        return None
    # Strip script + style, then tags
    html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
    html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:6000]


def diff_summary(old: str, new: str) -> tuple[str, int]:
    o = [l.rstrip() for l in old.splitlines()]
    n = [l.rstrip() for l in new.splitlines()]
    diff = list(difflib.unified_diff(o, n, lineterm="", n=2))
    changed = sum(1 for l in diff if l.startswith(("+", "-")) and not l.startswith(("+++", "---")) and l[1:].strip())
    return "\n".join(diff), changed


def append_correction(record, page_url, old_text, new_text, diff_text, changed) -> None:
    if not CORRECTIONS.exists():
        CORRECTIONS.write_text(
            "# Recent corrections (feedback)\n\n"
            "When fakematt-feedback flags an issue and the affected page subsequently "
            "changes, that's the proxy signal for 'Matt acted on the finding.' "
            "Pages that don't change for 30 days are marked rejected.\n\n"
            "Older entries (>90 days) are pruned automatically.\n\n---\n\n"
        )
    today = dt.date.today().isoformat()
    with open(CORRECTIONS, "a") as f:
        # Use the URL as the "recipient" stand-in for promote.py threshold counting
        f.write(f"\n## {today} — to {page_url}\n\n")
        # Show only excerpts (full pages can be huge); promote.py needs structured pairs
        f.write(f"**Original draft:**\n\n```\n{old_text[:2000]}\n```\n\n")
        f.write(f"**What Matt sent:**\n\n```\n{new_text[:2000]}\n```\n\n")
        if changed:
            f.write(f"**Diff** ({changed} changed lines):\n\n```diff\n{diff_text[:2000]}\n```\n\n")
        f.write("---\n")


def prune_old_corrections(max_age_days=90) -> None:
    if not CORRECTIONS.exists():
        return
    cutoff = dt.date.today() - dt.timedelta(days=max_age_days)
    text = CORRECTIONS.read_text()
    sections = re.split(r"(\n## (\d{4}-\d{2}-\d{2}) —[^\n]*\n)", text)
    if len(sections) < 4:
        return
    head = sections[0]
    new_parts = [head]
    i = 1
    while i < len(sections) - 1:
        header_full, header_date = sections[i], sections[i + 1]
        body = sections[i + 2] if i + 2 < len(sections) else ""
        try: d = dt.date.fromisoformat(header_date)
        except: d = dt.date.today()
        if d >= cutoff:
            new_parts.append(header_full + body)
        i += 3
    CORRECTIONS.write_text("".join(new_parts))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-age-days", type=int, default=90)
    args = ap.parse_args()

    if not SENT_LOG.exists():
        print("[learn] no sent-log yet")
        return 0

    records = []
    with open(SENT_LOG) as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try: records.append(json.loads(line))
            except: continue

    pending = [r for r in records if not r.get("checked")]
    print(f"[learn] {len(pending)} unchecked / {len(records)} total")

    updated = 0
    for record in pending:
        if not record.get("owned"):
            record["checked"] = True
            record["status"] = "skipped-not-owned"
            continue
        # Age check — give up after 30 days of no detected change
        try:
            run_ts = dt.datetime.strptime(record["ts"][:8], "%Y%m%d")
            age_days = (dt.datetime.now() - run_ts).days
        except Exception:
            age_days = 0

        any_change = False
        for snap in record.get("page_snapshots", [])[:MAX_PAGES_PER_RUN]:
            url = snap["url"]
            old = snap.get("text_snippet", "")
            new = fetch_text(url)
            if new is None:
                continue
            diff_text, changed = diff_summary(old, new)
            if changed >= 3:  # higher threshold than email — pages naturally have small diffs
                append_correction(record, url, old, new, diff_text, changed)
                print(f"[learn] page edit detected: {url} ({changed} changed lines)")
                updated += 1
                any_change = True

        if any_change:
            record["checked"] = True
            record["status"] = "edited"
        elif age_days > 30:
            record["checked"] = True
            record["status"] = "no-edit-30d"
        # else: leave unchecked, re-poll tomorrow

    with open(SENT_LOG, "w") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    prune_old_corrections(args.max_age_days)
    print(f"[learn] {updated} new corrections appended")
    return 0


if __name__ == "__main__":
    sys.exit(main())
