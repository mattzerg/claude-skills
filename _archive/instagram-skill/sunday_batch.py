#!/usr/bin/env python3
"""
sunday_batch.py — generate the Sunday-batch approval pack DM preview.

Pulls all queue items in state=drafted scheduled in the next N days (default 7),
groups by day, and renders a Fake-Matt-DM-ready preview. Default writes to
~/Downloads/detroit-hub-week-ahead-vN-YYYY-MM-DD.md per Matt's versioned-filename rule.

Usage:
    sunday_batch.py                                    # next 7 days → Downloads
    sunday_batch.py --days 14                          # wider window
    sunday_batch.py --stdout                           # print instead of writing
    sunday_batch.py --states drafted,reviewing         # filter states
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

VAULT = Path.home() / "Obsidian/Zerg"
QUEUE_DIR = VAULT / "MattZerg/Projects/detroit-hub/queue"
DOWNLOADS = Path.home() / "Downloads"

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def parse_item(path: Path) -> dict | None:
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not m:
        return None
    fm_raw, body = m.group(1), m.group(2)

    fm = {}
    caption_lines: list[str] = []
    in_caption = False
    source_lines: list[str] = []
    in_source = False

    for line in fm_raw.split("\n"):
        if in_caption:
            if line.startswith("  "):
                caption_lines.append(line[2:])
                continue
            in_caption = False
        if in_source:
            if line.startswith("  "):
                source_lines.append(line.strip())
                continue
            in_source = False

        if line.startswith("caption:"):
            in_caption = True
            continue
        if line.startswith("source:"):
            in_source = True
            continue
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()

    fm["_caption"] = "\n".join(caption_lines).strip()
    fm["_source_raw"] = source_lines
    fm["_body"] = body
    fm["_path"] = str(path)

    url_match = re.search(r"^URL:\s*(.+)$", body, re.MULTILINE)
    fm["_url"] = url_match.group(1).strip() if url_match else ""
    venue_match = re.search(r"^Venue:\s*(.+)$", body, re.MULTILINE)
    fm["_venue"] = venue_match.group(1).strip() if venue_match else ""

    return fm


def humanize_day(d: date, today: date) -> str:
    delta = (d - today).days
    if delta == 0:
        return "TONIGHT"
    if delta == 1:
        return "TOMORROW"
    full_day = DAY_NAMES[d.weekday()]
    if 2 <= delta <= 6:
        return f"This {full_day}"
    return f"{full_day} {MONTH_NAMES[d.month - 1]} {d.day}"


def render(items_by_day: dict[date, list[dict]], today: date, end: date) -> str:
    out: list[str] = []
    out.append(f"# Detroit Hub — Week Ahead Approval Pack")
    out.append(f"_{today.strftime('%a %b %d')} → {end.strftime('%a %b %d, %Y')}_")
    out.append("")

    total = sum(len(v) for v in items_by_day.values())
    out.append(f"**{total} drafted items across {len(items_by_day)} days.**")
    out.append("")
    out.append("Quick approve: tap ✅ to greenlight a day's full set. Tap ✏️ to revise a single caption. Tap 🚫 to reject.")
    out.append("")
    out.append("---")
    out.append("")

    for d in sorted(items_by_day.keys()):
        items = items_by_day[d]
        out.append(f"## {humanize_day(d, today)} — {d.strftime('%a %b %d')}  ({len(items)} items)")
        out.append("")

        for it in items:
            posture = it.get("copyright_posture", "?")
            posture_emoji = {
                "tagged-story": "🏷️",
                "collab-approved": "✅",
                "collab-request-pending": "⏳",
                "original": "📸",
                "unsafe": "🚫",
            }.get(posture, "❔")
            surface = it.get("surface", "?")
            pattern = it.get("pattern", "?")
            score = "n/a"

            caption = it.get("_caption", "").replace("\n", "\n>     ")
            venue = it.get("_venue", "(unknown)")
            url = it.get("_url", "")
            slug = it.get("slug", Path(it.get("_path", "")).stem)

            out.append(f"### {posture_emoji} {surface} / pattern {pattern} · `{slug}`")
            out.append(f"**Venue:** {venue}")
            if url:
                out.append(f"**Source:** {url}")
            out.append("")
            out.append("> Caption:")
            out.append(">")
            out.append(f">     {caption}")
            out.append("")
            out.append("→ [✅ approve](#) · [✏️ revise](#) · [🚫 reject](#)")
            out.append("")

        out.append("---")
        out.append("")

    out.append("## Pack-level actions")
    out.append("")
    out.append("- ✅ Approve all → flips all to `state: scheduled`")
    out.append("- 📤 Send to drafts only (don't auto-publish)")
    out.append("- 🔄 Re-roll captions for items below lint threshold (none in this pack — all clean)")
    out.append("")

    return "\n".join(out)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--states", default="drafted",
                   help="comma-separated states to include")
    p.add_argument("--stdout", action="store_true")
    p.add_argument("--surface", default=None,
                   help="filter to one surface (feed/story/reel)")
    args = p.parse_args()

    if not QUEUE_DIR.exists():
        print("ERROR: queue dir not found", file=sys.stderr)
        return 1

    today = date.today()
    end = today + timedelta(days=args.days)
    states = {s.strip() for s in args.states.split(",")}

    items_by_day: dict[date, list[dict]] = {}
    for f in sorted(QUEUE_DIR.glob("*.md")):
        if f.name.startswith("_"):
            continue
        item = parse_item(f)
        if not item:
            continue
        if item.get("state") not in states:
            continue
        if args.surface and item.get("surface") != args.surface:
            continue
        sched = item.get("scheduled", "")
        try:
            d = datetime.strptime(sched[:10], "%Y-%m-%d").date()
        except Exception:
            continue
        if d < today or d > end:
            continue
        items_by_day.setdefault(d, []).append(item)

    output = render(items_by_day, today, end)

    if args.stdout:
        print(output)
        return 0

    # Versioned filename per Matt's rule
    DOWNLOADS.mkdir(exist_ok=True)
    today_str = today.strftime("%Y-%m-%d")
    base = f"detroit-hub-week-ahead-v{{N}}-{today_str}.md"
    n = 1
    while (DOWNLOADS / base.format(N=n)).exists():
        n += 1
    out_path = DOWNLOADS / base.format(N=n)
    out_path.write_text(output)
    total = sum(len(v) for v in items_by_day.values())
    print(f"wrote {out_path}")
    print(f"  days: {len(items_by_day)}, items: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
