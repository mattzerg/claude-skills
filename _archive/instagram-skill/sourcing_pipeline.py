#!/usr/bin/env python3
"""
sourcing_pipeline.py — Detroit hub event scraper.

Pulls events from canonical Detroit-music sources (RA, 19hz, Metro Times), normalizes them,
and emits candidate queue items.

v0 scope: RA Detroit + 19hz Detroit (both unauth-scrapable).
v1: + venue IGs via instagram-skill session.
v2: + Metro Times community + Eventbrite Detroit.

Usage:
    python3 sourcing_pipeline.py                          # scrape + print JSON to stdout
    python3 sourcing_pipeline.py --write-queue            # also write queue items
    python3 sourcing_pipeline.py --source ra              # one source only
    python3 sourcing_pipeline.py --days 7                 # next N days (default 14)

Output:
    JSON to stdout: {ok: bool, sources: {name: {ok, count, events}}, items: [...]}
    Optional: queue items at MattZerg/Projects/detroit-hub/queue/<date>-<slug>.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

VAULT = Path.home() / "Obsidian/Zerg"
QUEUE_DIR = VAULT / "MattZerg/Projects/detroit-hub/queue"
LOG_DIR = Path.home() / ".claude/skills/instagram-skill/logs"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/130.0.0.0 Safari/537.36"
)

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def fetch(url: str, timeout: int = 20) -> str:
    """GET with UA — returns text body or raises."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


# ---------------------------------------------------------------------------
# 19hz.info Detroit — regex parser (malformed <td>s in source HTML, html.parser
# trips on the unclosed second cell. Regex handles the consistent structure.)
#
# Actual row shape:
#   <tr>
#     <td>DATE <br />(TIME)</td>
#     <td><a href='LINK'>TITLE</a> @ VENUE          ← unclosed </td>
#       <td>GENRE</td>
#       <td>AGE</td>
#       <td>PRICE</td>
#       <td>TICKETS/IG LINK</td>
#       <td><div class='shrink'>YYYY/MM/DD</div></td>
#   </tr>
# ---------------------------------------------------------------------------

ROW_RE = re.compile(
    r"<tr>\s*<td>(?P<date>[^<]*(?:<br\s*/?>[^<]*)?)</td>\s*"
    r"<td>(?P<title_block>.*?)<td>(?P<genre>[^<]*)</td>\s*"
    r"<td>(?P<age>[^<]*)</td>\s*"
    r"<td>(?P<price>[^<]*)</td>\s*"
    r"<td>(?P<ticket_block>.*?)</td>\s*"
    r"<td><div class='shrink'>(?P<sort_date>\d{4}/\d{2}/\d{2})</div></td>\s*"
    r"</tr>",
    re.DOTALL,
)

TITLE_RE = re.compile(r"<a[^>]*href=['\"](?P<url>[^'\"]+)['\"][^>]*>(?P<title>[^<]+)</a>(?P<rest>.*)", re.DOTALL)


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s).strip()


def _parse_title_block(block: str) -> tuple[str, str, str]:
    """Returns (title, venue, event_url)."""
    m = TITLE_RE.search(block)
    if m:
        title = m.group("title").strip()
        url = m.group("url").strip()
        rest = _strip_tags(m.group("rest"))
        # Common format: "TITLE</a> @ VENUE (City)"
        venue = ""
        if rest.lstrip().startswith("@"):
            venue = rest.lstrip()[1:].strip()
        else:
            venue = rest.strip()
        return title, venue, url
    # No anchor — title is the raw text up to '@'
    raw = _strip_tags(block)
    if "@" in raw:
        t, v = raw.split("@", 1)
        return t.strip(), v.strip(), ""
    return raw.strip(), "", ""


def scrape_19hz_detroit() -> dict:
    url = "https://19hz.info/eventlisting_Detroit.php"
    try:
        html = fetch(url)
    except Exception as e:
        return {"ok": False, "error": str(e), "events": []}

    events: list[dict] = []
    for m in ROW_RE.finditer(html):
        title, venue, event_url = _parse_title_block(m.group("title_block"))
        if not title:
            continue
        date_raw = re.sub(r"<br\s*/?>", " ", m.group("date")).strip()
        sort_date = m.group("sort_date").replace("/", "-")  # YYYY-MM-DD
        events.append({
            "date_raw": date_raw,
            "date_iso_hint": sort_date,
            "title": title,
            "venue": venue,
            "genre": m.group("genre").strip(),
            "age": m.group("age").strip(),
            "price": m.group("price").strip(),
            "url": event_url,
            "source": "19hz",
            "source_url": url,
        })

    return {"ok": True, "count": len(events), "events": events}


# ---------------------------------------------------------------------------
# RA Detroit — RA serves a hydrated SPA. The HTML contains JSON-LD events.
# ---------------------------------------------------------------------------

def scrape_ra_detroit() -> dict:
    """RA blocks plain urllib (403). TODO: route through firecrawl-scrape skill or playwright
    session. Until then, return graceful empty + note. 19hz covers the same underground beat
    and currently gives ~180 in-window events on its own."""
    url = "https://ra.co/events/us/detroit"
    try:
        html = fetch(url)
    except urllib.error.HTTPError as e:
        if e.code == 403:
            return {
                "ok": True,  # not a hard failure — graceful degrade
                "count": 0,
                "events": [],
                "skipped": True,
                "skip_reason": f"RA returned {e.code} to unauth scrape — needs firecrawl-scrape or playwright session",
                "todo": "switch to firecrawl-scrape skill or use logged-in playwright session",
            }
        return {"ok": False, "error": f"HTTP {e.code}", "events": []}
    except Exception as e:
        return {"ok": False, "error": str(e), "events": []}

    events: list[dict] = []

    # Strategy 1: JSON-LD Event objects (`@type":"Event"` blocks in <script type="application/ld+json">)
    for m in re.finditer(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL,
    ):
        try:
            data = json.loads(m.group(1))
        except Exception:
            continue
        # Could be dict or list
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if isinstance(node, dict) and node.get("@type") == "Event":
                events.append({
                    "date_raw": node.get("startDate", ""),
                    "title": node.get("name", ""),
                    "venue": (node.get("location") or {}).get("name", "") if isinstance(node.get("location"), dict) else "",
                    "url": node.get("url", ""),
                    "source": "ra",
                    "source_url": url,
                })

    # Strategy 2: __NEXT_DATA__ fallback if JSON-LD is empty
    if not events:
        m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
        if m:
            try:
                nd = json.loads(m.group(1))
                # Path varies; just bag any event-shaped object we find
                def walk(obj):
                    if isinstance(obj, dict):
                        if obj.get("__typename") == "Event" or ("title" in obj and "venue" in obj and "date" in obj):
                            yield obj
                        for v in obj.values():
                            yield from walk(v)
                    elif isinstance(obj, list):
                        for v in obj:
                            yield from walk(v)
                for ev in walk(nd):
                    events.append({
                        "date_raw": ev.get("date", ""),
                        "title": ev.get("title", ""),
                        "venue": (ev.get("venue") or {}).get("name", "") if isinstance(ev.get("venue"), dict) else (ev.get("venue") or ""),
                        "url": ev.get("contentUrl", "") or ev.get("url", ""),
                        "source": "ra",
                        "source_url": url,
                    })
            except Exception:
                pass

    # Dedupe by (title, date)
    seen = set()
    dedup = []
    for ev in events:
        key = (ev["title"], ev["date_raw"])
        if key in seen:
            continue
        seen.add(key)
        dedup.append(ev)

    return {"ok": True, "count": len(dedup), "events": dedup}


# ---------------------------------------------------------------------------
# Normalizer — best-effort date parse
# ---------------------------------------------------------------------------

def normalize(ev: dict) -> dict:
    """Add an ISO date if we can derive one. Leave raw if not."""
    # Prefer explicit hint from source (e.g., 19hz sort_date)
    if ev.get("date_iso_hint"):
        return {**ev, "date_iso": ev["date_iso_hint"]}
    raw = ev.get("date_raw", "") or ""
    iso = None
    # ISO-8601 already?
    if re.match(r"\d{4}-\d{2}-\d{2}", raw):
        iso = raw[:10]
    else:
        # 19hz format e.g. "Sat: May 24" or "Fri May 24 (10:00PM)"
        m = re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2})", raw)
        if m:
            month_str, day_str = m.group(1), m.group(2)
            try:
                month = datetime.strptime(month_str[:3], "%b").month
                year = datetime.now().year
                # If month already passed this year by > 1, assume next year
                today = datetime.now()
                tentative = datetime(year, month, int(day_str))
                if tentative < today - timedelta(days=14):
                    tentative = datetime(year + 1, month, int(day_str))
                iso = tentative.strftime("%Y-%m-%d")
            except Exception:
                pass

    return {**ev, "date_iso": iso}


def slugify(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", s.lower()).strip()
    s = re.sub(r"[\s_-]+", "-", s)
    return s[:60].strip("-")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--account", default="matteisn")
    p.add_argument("--source", choices=["ra", "19hz", "all"], default="all")
    p.add_argument("--write-queue", action="store_true",
                   help="Also write queue items (skipped by default for safety)")
    p.add_argument("--days", type=int, default=14, help="Filter to events within next N days")
    p.add_argument("--out", type=Path, default=None, help="Write JSON to file (default: stdout)")
    args = p.parse_args()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = LOG_DIR / f"sourcing-{datetime.now().strftime('%Y%m%d')}.log"
    log_handle = log.open("a")
    log_handle.write(f"\n=== run {datetime.now().isoformat()} ===\n")

    result = {"ok": True, "ran_at": datetime.now(timezone.utc).isoformat(),
              "sources": {}, "items": []}

    if args.source in ("19hz", "all"):
        r = scrape_19hz_detroit()
        result["sources"]["19hz"] = r
        log_handle.write(f"19hz: ok={r['ok']} count={r.get('count', 0)}\n")

    if args.source in ("ra", "all"):
        r = scrape_ra_detroit()
        result["sources"]["ra"] = r
        log_handle.write(f"ra: ok={r['ok']} count={r.get('count', 0)}\n")

    # Merge + normalize + filter by date window
    horizon = datetime.now() + timedelta(days=args.days)
    today_d = datetime.now().date()
    all_events = []
    for src_name, src_data in result["sources"].items():
        for ev in src_data.get("events", []):
            n = normalize(ev)
            if n.get("date_iso"):
                try:
                    d = datetime.strptime(n["date_iso"], "%Y-%m-%d").date()
                    if d < today_d or d > horizon.date():
                        continue
                except Exception:
                    pass
            all_events.append(n)

    result["items"] = all_events
    result["item_count"] = len(all_events)
    log_handle.write(f"merged items in window: {len(all_events)}\n")

    if args.write_queue:
        QUEUE_DIR.mkdir(parents=True, exist_ok=True)
        written = 0
        for ev in all_events:
            if not ev.get("date_iso"):
                continue
            slug = f"{ev['date_iso']}-{slugify(ev.get('title', 'event'))}"
            path = QUEUE_DIR / f"{slug}.md"
            if path.exists():
                continue
            fm = [
                "---",
                f"slug: {slug}",
                f"scheduled: {ev['date_iso']}T11:00-04:00",
                "surface: story",
                "format: story",
                "pattern: F",
                "copyright_posture: tagged-story",
                "state: drafted",
                "source:",
                f"  - venue: {ev.get('venue', '')}",
                f"    url: {ev.get('url') or ev.get('source_url', '')}",
                f"    asset: ''",
                "caption: |",
                f"  {ev.get('title', '').strip()}",
                f"  {ev.get('venue', '').strip()}",
                "  📸 source TBD",
                "caption_lint:",
                "  ran: null",
                "notes:",
                f"  - auto-scraped from {ev.get('source')} on {datetime.now().date()}",
                "---",
                "",
                f"# {ev['date_iso']} — {ev.get('title', 'Event')}",
                "",
                f"Source: {ev.get('source')}",
                f"Raw date: {ev.get('date_raw', '')}",
                f"Venue: {ev.get('venue', '')}",
                f"URL: {ev.get('url') or ev.get('source_url', '')}",
                "",
            ]
            path.write_text("\n".join(fm))
            written += 1
        result["queue_written"] = written
        log_handle.write(f"queue written: {written}\n")

    log_handle.close()

    out_json = json.dumps(result, indent=2, default=str)
    if args.out:
        args.out.write_text(out_json)
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        print(out_json)

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
