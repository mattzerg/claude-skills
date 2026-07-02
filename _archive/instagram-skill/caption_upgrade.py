#!/usr/bin/env python3
"""
caption_upgrade.py — rewrite placeholder captions in queue items using the 6 caption patterns.

Auto-generates only the data-grounded patterns (A index-card, F knowing-aside).
B (one-sharp-line) / C (year+venue+vibe) / E (reframe) require human or LLM judgment —
flagged in queue notes as "promote to pattern B/E for hand-written sharpness."

Reads YAML frontmatter, regenerates caption, runs caption_lint, writes back.
Idempotent: --force overrides existing captions; default skips items that already pass lint.

Usage:
    caption_upgrade.py                          # upgrade all drafted items
    caption_upgrade.py --force                  # overwrite all (incl. passing)
    caption_upgrade.py --file path/to/item.md   # one file
    caption_upgrade.py --dry-run                # print proposed changes, don't write
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

VAULT = Path.home() / "Obsidian/Zerg"
QUEUE_DIR = VAULT / "MattZerg/Projects/detroit-hub/queue"
SKILL_DIR = Path.home() / ".claude/skills/instagram-skill"
LINT = SKILL_DIR / "caption_lint.py"


# Pattern picker — for upcoming events (story/feed), A and F are the data-grounded options.
# Weighted; "auto-generable" patterns only. Hand-written promotions are flagged in notes.
PATTERN_WEIGHTS_BY_SURFACE = {
    "story":   [("F", 0.55), ("A", 0.35), ("F_short", 0.10)],
    "feed":    [("A", 0.55), ("F", 0.35), ("A_carousel", 0.10)],
    "reel":    [("F", 0.50), ("A", 0.40), ("F_short", 0.10)],
    "default": [("A", 0.60), ("F", 0.40)],
}


def pick_pattern(surface: str, seed: int) -> str:
    """Deterministic pattern pick based on (surface, slug-hash-seed)."""
    import random
    rng = random.Random(seed)
    options = PATTERN_WEIGHTS_BY_SURFACE.get(surface, PATTERN_WEIGHTS_BY_SURFACE["default"])
    labels, weights = zip(*options)
    return rng.choices(labels, weights=weights, k=1)[0]


# ---------------------------------------------------------------------------
# Date framing
# ---------------------------------------------------------------------------

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def humanize_date(iso_str: str, today: date | None = None) -> str:
    """2026-05-19 → 'Tonight' / 'This Thursday' / 'May 24'."""
    today = today or date.today()
    try:
        d = datetime.strptime(iso_str[:10], "%Y-%m-%d").date()
    except Exception:
        return iso_str
    delta = (d - today).days
    if delta == 0:
        return "Tonight"
    if delta == 1:
        return "Tomorrow"
    if 2 <= delta <= 6:
        return f"This {DAY_NAMES[d.weekday()]}{'sday' if d.weekday() == 1 else 'urday' if d.weekday() == 5 else 'day' if d.weekday() in {0, 2, 3} else 'day' if d.weekday() == 4 else 'day'}"
    return f"{MONTH_NAMES[d.month - 1]} {d.day}"


# Simplified — the above is fragile; just use full day name for 2-6 days out
def humanize_date_v2(iso_str: str, today: date | None = None) -> str:
    today = today or date.today()
    try:
        d = datetime.strptime(iso_str[:10], "%Y-%m-%d").date()
    except Exception:
        return iso_str
    delta = (d - today).days
    if delta == 0:
        return "Tonight"
    if delta == 1:
        return "Tomorrow"
    full_day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    if 2 <= delta <= 6:
        return f"This {full_day_names[d.weekday()]}"
    if 7 <= delta <= 13:
        return f"Next {full_day_names[d.weekday()]}"
    return f"{MONTH_NAMES[d.month - 1]} {d.day}"


# ---------------------------------------------------------------------------
# Frontmatter parser (minimal — these queue files have a known shape)
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str) -> tuple[dict, str, str]:
    """Returns (fm_dict, fm_raw, body)."""
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not m:
        return {}, "", text
    fm_raw = m.group(1)
    body = m.group(2)
    fm: dict = {}
    current_key = None
    for line in fm_raw.split("\n"):
        if not line.strip():
            continue
        if line[0] not in " -" and ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
            current_key = k.strip()
        elif line.startswith("  -") and current_key == "source":
            # list under source — preserve raw, don't reparse
            fm.setdefault("_source_raw", []).append(line)
        elif line.startswith("  ") and current_key == "caption":
            fm["caption"] = (fm.get("caption", "") + "\n" + line.strip()).strip()
        elif line.startswith("  ") and current_key == "notes":
            fm["notes"] = (fm.get("notes", "") + "\n" + line.strip()).strip()
    return fm, fm_raw, body


# ---------------------------------------------------------------------------
# Source extractor — pull venue + URL from the body (sourcing_pipeline writes them there)
# ---------------------------------------------------------------------------

def extract_from_body(body: str) -> dict:
    out = {}
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("Source:"):
            out["source"] = s.split(":", 1)[1].strip()
        elif s.startswith("Raw date:"):
            out["raw_date"] = s.split(":", 1)[1].strip()
        elif s.startswith("Venue:"):
            out["venue"] = s.split(":", 1)[1].strip()
        elif s.startswith("URL:"):
            out["url"] = s.split(":", 1)[1].strip()
    return out


# ---------------------------------------------------------------------------
# Caption generators per pattern
# ---------------------------------------------------------------------------

def gen_pattern_a(title: str, venue: str, scheduled_iso: str) -> str:
    """A — Index-card: <title> · <venue> · <human date>"""
    d = humanize_date_v2(scheduled_iso)
    parts = [title, venue, d]
    return " · ".join(p for p in parts if p)


def gen_pattern_a_carousel(title: str, venue: str, scheduled_iso: str, genre: str) -> str:
    """A variant for feed carousel — title on its own line, then context."""
    d = humanize_date_v2(scheduled_iso)
    out = [title]
    ctx_line_parts = [venue, d]
    if genre:
        ctx_line_parts.append(genre)
    out.append(" · ".join(p for p in ctx_line_parts if p))
    return "\n".join(out)


def gen_pattern_f(title: str, venue: str, scheduled_iso: str) -> str:
    """F — Knowing aside, story-friendly: <human date> at <venue>. <title>."""
    d = humanize_date_v2(scheduled_iso)
    venue_short = venue.replace(" (Detroit)", "").replace(" (Hamtramck)", "")
    if d == "Tonight":
        opener = f"Tonight at {venue_short}"
    elif d == "Tomorrow":
        opener = f"Tomorrow at {venue_short}"
    else:
        opener = f"{d} at {venue_short}"
    return f"{opener}.\n{title}"


def gen_pattern_f_short(title: str, scheduled_iso: str) -> str:
    """F — minimum-viable story caption — just the headline + day."""
    d = humanize_date_v2(scheduled_iso)
    return f"{d}.\n{title}"


def generate_caption(pattern: str, title: str, venue: str, scheduled_iso: str, genre: str = "") -> str:
    if pattern == "A":
        return gen_pattern_a(title, venue, scheduled_iso)
    if pattern == "A_carousel":
        return gen_pattern_a_carousel(title, venue, scheduled_iso, genre)
    if pattern == "F":
        return gen_pattern_f(title, venue, scheduled_iso)
    if pattern == "F_short":
        return gen_pattern_f_short(title, scheduled_iso)
    # fallback
    return gen_pattern_a(title, venue, scheduled_iso)


# ---------------------------------------------------------------------------
# Lint helper — call the existing caption_lint.py
# ---------------------------------------------------------------------------

def lint_caption(caption: str) -> dict:
    r = subprocess.run(
        ["/usr/bin/python3", str(LINT), "--text", caption, "--quiet"],
        capture_output=True, text=True,
    )
    try:
        return json.loads(r.stdout)
    except Exception:
        return {"ok": False, "score": 0, "error": "lint_parse_failed"}


# ---------------------------------------------------------------------------
# Frontmatter rewrite
# ---------------------------------------------------------------------------

def rewrite_item(path: Path, force: bool = False, dry_run: bool = False) -> dict:
    text = path.read_text()
    fm, fm_raw, body = parse_frontmatter(text)
    if not fm:
        return {"path": str(path), "skipped": "no frontmatter"}

    state = fm.get("state", "")
    if state != "drafted" and not force:
        return {"path": str(path), "skipped": f"state={state}"}

    # Source the actual data from the body (sourcing_pipeline wrote it there)
    body_data = extract_from_body(body)
    venue = body_data.get("venue") or fm.get("venue", "")
    # Title: derive from filename (slug minus date prefix) or body header
    # Use the H1 from body as title source if present
    h1 = re.search(r"^# \d{4}-\d{2}-\d{2} — (.+)$", body, re.MULTILINE)
    title = h1.group(1).strip() if h1 else fm.get("slug", path.stem)

    # Clean 19hz convention: titles often duplicate venue as trailing "(Venue In City)" paren
    # e.g., "Crunk Witch ... (Corktown Tavern In Detroit)" → strip the paren
    m_in = re.search(r"\s*\([^)]*\bIn\b[^)]*\)\s*$", title)
    if m_in:
        title = title[:m_in.start()].strip()
    # Also strip standalone city parens
    m_city = re.search(
        r"\s*\((Detroit|Hamtramck|Ann Arbor|Ferndale|Royal Oak|Pontiac|Dearborn)\)\s*$",
        title, re.IGNORECASE,
    )
    if m_city:
        title = title[:m_city.start()].strip()

    scheduled = fm.get("scheduled", "")

    # Read genre from body (raw_date / Source: lines don't include it — sourcing_pipeline only puts it in raw events)
    genre = ""  # not in the body output today; placeholder for v2 enrichment

    # Determine pattern
    surface = fm.get("surface", "story")
    seed = abs(hash(path.stem)) % (2**31)
    pattern = pick_pattern(surface, seed)

    new_caption = generate_caption(pattern, title, venue, scheduled, genre)
    # Append source-credit line
    if body_data.get("source") == "19hz":
        new_caption = new_caption + "\n— via 19hz"
    elif body_data.get("source"):
        new_caption = new_caption + f"\n— via {body_data['source']}"

    lint_result = lint_caption(new_caption)

    # Try a second pattern if lint fails
    if not lint_result.get("ok"):
        fallback = "A" if pattern.startswith("F") else "F"
        new_caption_v2 = generate_caption(fallback, title, venue, scheduled, genre)
        new_caption_v2 += "\n— via 19hz" if body_data.get("source") == "19hz" else ""
        lint_v2 = lint_caption(new_caption_v2)
        if lint_v2.get("ok"):
            pattern = fallback
            new_caption = new_caption_v2
            lint_result = lint_v2

    # Build the new frontmatter — surgical replace of `caption:` block and `caption_lint:` block
    # Indent caption body as 2-space yaml block scalar
    indented = "\n".join("  " + line for line in new_caption.split("\n"))
    new_fm = fm_raw

    # Replace pattern line
    if re.search(r"^pattern:.*$", new_fm, re.MULTILINE):
        new_fm = re.sub(r"^pattern:.*$", f"pattern: {pattern}", new_fm, count=1, flags=re.MULTILINE)
    else:
        new_fm += f"\npattern: {pattern}"

    # Replace the caption block (caption: | ... up to next top-level key)
    cap_re = re.compile(r"^caption:\s*\|?[^\n]*\n((?:  [^\n]*\n)*)", re.MULTILINE)
    cap_replace = f"caption: |\n{indented}\n"
    if cap_re.search(new_fm):
        new_fm = cap_re.sub(cap_replace, new_fm, count=1)
    else:
        new_fm += "\n" + cap_replace.rstrip()

    # Replace caption_lint block
    lint_yaml = (
        f"caption_lint:\n"
        f"  ok: {str(lint_result.get('ok', False)).lower()}\n"
        f"  score: {lint_result.get('score', 0)}\n"
        f"  threshold: {lint_result.get('threshold', 70)}\n"
        f"  ran: {datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}\n"
    )
    cl_re = re.compile(r"^caption_lint:[^\n]*\n((?:  [^\n]*\n)*)", re.MULTILINE)
    if cl_re.search(new_fm):
        new_fm = cl_re.sub(lint_yaml, new_fm, count=1)
    else:
        new_fm += "\n" + lint_yaml

    final_text = f"---\n{new_fm.rstrip()}\n---\n{body}"

    result = {
        "path": str(path),
        "pattern": pattern,
        "lint_ok": lint_result.get("ok"),
        "lint_score": lint_result.get("score"),
        "caption_preview": new_caption[:120],
    }

    if dry_run:
        result["dry_run"] = True
    else:
        path.write_text(final_text)
        result["written"] = True

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--file", type=Path, help="Single file mode")
    p.add_argument("--force", action="store_true", help="Rewrite even if not in 'drafted' state")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, default=0, help="Process at most N files (0 = all)")
    args = p.parse_args()

    if args.file:
        files = [args.file]
    else:
        files = sorted(QUEUE_DIR.glob("*.md"))
        files = [f for f in files if not f.name.startswith("_")]

    if args.limit:
        files = files[:args.limit]

    results = []
    written = 0
    passing = 0
    failing = 0
    skipped = 0
    for f in files:
        r = rewrite_item(f, force=args.force, dry_run=args.dry_run)
        results.append(r)
        if r.get("skipped"):
            skipped += 1
        if r.get("written"):
            written += 1
        if r.get("lint_ok") is True:
            passing += 1
        elif r.get("lint_ok") is False:
            failing += 1

    summary = {
        "ok": True,
        "total": len(files),
        "written": written,
        "skipped": skipped,
        "lint_passing": passing,
        "lint_failing": failing,
        "dry_run": args.dry_run,
        "samples": results[:5],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
