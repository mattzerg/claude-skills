#!/usr/bin/env python3
"""signoff_sheet_gen.py — regenerate the batch signoff sheet from live data.

Reads (READ-ONLY):
  - MattZerg/Tasks/decisions_pending.md   (generator-owned; NEVER written here)
  - zpub index (Growth/publishing/_meta/index.json) for blockers/targets/types

Writes:
  - MattZerg/Tasks/signoff-sheet-<YYYY-MM-DD>.md
    Same shape as the hand-built 2026-06-11 sheet: 3-line counts header
    (recommend-ship / recommend-hold / recommend-archive), then per-item rows
    item | age | recommendation | one-line rationale.
  - Never overwrites an existing same-day sheet: appends -r2 / -r3 / ... .

Verdict heuristics + item knowledge ported from signoff-sheet-2026-06-11.md:
  - zpub items: dq_lib.recommend() (past-target -> ship; launches/blockers ->
    hold one week pre-target; near-target unblocked -> ship; no target ->
    hold w/ assign-or-archive).
  - gtm-hub "Schedule/publish: X" shadowing a zpub item -> ARCHIVE (duplicate
    tracker noise; zero content lost). "Five products, one identity" aliases
    to the Zstack Bundle launch.
  - mining: first composite proposal -> SHIP (cheap yes, report-only);
    duplicate re-surfacings -> ARCHIVE.
  - cadence "run now" defaults -> SHIP.
  - ARCHIVE is only ever recommended for duplicate tracker rows, never for
    content. Deletion is never recommended anywhere.

Usage:
  signoff_sheet_gen.py [--date YYYY-MM-DD] [--dry-run]
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dq_lib as dq  # noqa: E402

ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|(.+)\|\s*$")

# Item knowledge from the 2026-06-11 hand-built sheet: gtm-hub titles that
# shadow a zpub item under a different name.
ALIASES = {
    "five products, one identity": "zstack bundle launch",
}


def parse_decisions_md(path: Path):
    """Parse the generator-owned pending-decisions table. Returns row dicts."""
    rows = []
    if not path.exists():
        raise FileNotFoundError("decisions_pending.md not found: %s" % path)
    for line in path.read_text().splitlines():
        m = ROW_RE.match(line)
        if not m:
            continue
        cells = [c.strip() for c in m.group(2).split("|")]
        if len(cells) < 6 or cells[0].lower() == "source":
            continue
        rows.append({
            "n": int(m.group(1)),
            "source": cells[0].strip("`"),
            "age": cells[1],
            "class": cells[2].strip("`"),
            "item": cells[3],
            "default": cells[4].strip("`"),
            "deadline": cells[5] if cells[5] != "—" else None,
        })
    return rows


def find_entry(entries, item_line):
    """Match a zpub one-liner back to its index entry by title prefix."""
    title = item_line.split(" • ")[0].strip().rstrip("…").strip()
    tl = title.casefold()
    for e in entries:
        et = (e.get("title") or "").casefold()
        if not et:
            continue
        if et == tl or et.startswith(tl) or tl.startswith(et):
            return e
    return None


def fmt_rec(verdict, revisit=None, note=None):
    label = verdict.upper()
    out = "**%s**" % label
    if verdict == "hold" and revisit:
        out += " — revisit %s" % revisit.isoformat()
    if note:
        out += " — %s" % note
    return out


def recommend_rows(rows, entries):
    """Attach (verdict, rec_cell, rationale) to each parsed row."""
    t = dq.today()
    zpub_items = [(r, r["item"].casefold()) for r in rows
                  if r["source"] == "zpub"]
    seen_mining = []
    out = []
    for r in rows:
        src, item = r["source"], r["item"]
        low = item.casefold()
        verdict, rec, why = None, None, None

        if src == "zpub" or src == "zpub-gateage":
            e = find_entry(entries, item)
            if e is not None:
                v, why, revisit = dq.recommend(e, 0.0)
                verdict, rec = v, fmt_rec(v, revisit)
            else:
                verdict = "hold"
                rec = fmt_rec("hold", t + timedelta(days=7))
                why = ("couldn't match to a zpub index entry — verify the "
                       "item still exists, then decide")

        elif src == "gtm-hub":
            m = re.match(r"schedule/publish:\s*(.+)", low)
            if m:
                name = ALIASES.get(m.group(1).strip(), m.group(1).strip())
                dup = next((zr for zr, zl in zpub_items if name in zl), None)
                if dup:
                    verdict = "archive"
                    rec = fmt_rec("archive")
                    why = ("duplicate of zpub row #%d — tracker noise; "
                           "resolves when the zpub item ships. Zero content "
                           "lost." % dup["n"])
            if verdict is None and "decide by" in low:
                dm = re.search(r"decide by (\d{4}-\d{2}-\d{2})", low)
                rv = dq.parse_dt(dm.group(1)).date() if dm else t + timedelta(days=3)
                verdict = "hold"
                rec = fmt_rec("hold", rv)
                why = ("verdict date is %s — decide with the data in hand; "
                       "don't extend by inertia" % rv.isoformat())
            if verdict is None and ("content target" in low
                                    or "imagery check" in low):
                prod = next((zr for zr, zl in zpub_items
                             if any(tok in zl for tok in low.split()
                                    if tok.startswith("zerg"))), None)
                if prod and prod["deadline"]:
                    pd = dq.parse_dt(prod["deadline"])
                    rv = (pd.date() - timedelta(days=14)) if pd else t + timedelta(days=7)
                    rv = max(rv, t + timedelta(days=1))
                    verdict = "hold"
                    rec = fmt_rec("hold", rv)
                    why = ("don't double-track — zpub row #%d holds the "
                           "canonical target (%s); reconcile to one date"
                           % (prod["n"], prod["deadline"]))
                else:
                    verdict = "hold"
                    rec = fmt_rec("hold", t + timedelta(days=7))
                    why = "no canonical zpub date found — reconcile before acting"

        elif src == "mining":
            mm = re.search(r"`([^`]+)`", item)
            name = (mm.group(1) if mm else item).casefold()
            name = re.sub(r"^review draft:\s*", "", name)
            if any(name == s or name in s or s in name for s in seen_mining):
                verdict = "archive"
                rec = fmt_rec("archive")
                why = "same proposal surfaced twice — dedupe the queue"
            else:
                seen_mining.append(name)
                verdict = "ship"
                rec = fmt_rec("ship", note="approve draft")
                why = ("zero external risk — output is a report Matt then "
                       "reviews. Cheap yes.")

        elif src == "cadence":
            verdict = "ship"
            rec = fmt_rec("ship", note="run now")
            why = ("default is already 'run now'; autonomous, zero external "
                   "surface")

        if verdict is None:
            verdict = "hold"
            rec = fmt_rec("hold", t + timedelta(days=7))
            why = "unrecognized source '%s' — review at the batch session" % src
        out.append((r, verdict, rec, why))
    return out


def render(sheet_date, recs, n_pending):
    counts = {"ship": 0, "hold": 0, "archive": 0}
    for _, v, _, _ in recs:
        counts[v] = counts.get(v, 0) + 1
    lines = []
    lines.append("# Batch signoff sheet — %s" % sheet_date.isoformat())
    lines.append("")
    lines.append("Auto-generated by `signoff_sheet_gen.py` from "
                 "`decisions_pending.md` (%d pending) + zpub index. Each row "
                 "has a default — fast yes/no against it." % n_pending)
    lines.append("")
    lines.append("- recommend-ship: %d" % counts["ship"])
    lines.append("- recommend-hold: %d" % counts["hold"])
    lines.append("- recommend-archive: %d" % counts["archive"])
    lines.append("")
    lines.append("| # | Item | Age | Recommendation | Rationale |")
    lines.append("|---|---|---|---|---|")
    for r, v, rec, why in recs:
        lines.append("| %d | %s | %s | %s | %s |"
                     % (r["n"], r["item"], r["age"], rec, why))
    lines.append("")
    lines.append("## Session mechanics")
    lines.append("")
    lines.append("- Run top-to-bottom; archives are duplicate-tracker noise "
                 "and should take seconds.")
    lines.append("- Every HOLD carries a revisit date — if a hold is "
                 "disputed, the fallback is archive with a revisit, never "
                 "open-ended pending. Nothing is deleted.")
    lines.append("")
    return "\n".join(lines)


def target_path(sheet_date):
    base = dq.TASKS_DIR / ("signoff-sheet-%s.md" % sheet_date.isoformat())
    if not base.exists():
        return base
    n = 2
    while True:
        cand = dq.TASKS_DIR / ("signoff-sheet-%s-r%d.md"
                               % (sheet_date.isoformat(), n))
        if not cand.exists():
            return cand
        n += 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Regenerate the batch signoff sheet from "
                    "decisions_pending.md (read-only) + zpub index. Never "
                    "overwrites an existing same-day sheet (-rN suffix).")
    ap.add_argument("--date", default=None,
                    help="sheet date YYYY-MM-DD (default: today)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the sheet; write nothing")
    args = ap.parse_args()

    sheet_date = (date.fromisoformat(args.date) if args.date else dq.today())

    try:
        rows = parse_decisions_md(dq.DECISIONS_MD)
        entries = dq.load_index_entries()
    except Exception as e:
        print("ERROR: %s" % e, file=sys.stderr)
        return 1
    if not rows:
        print("ERROR: parsed 0 rows from %s — format change?"
              % dq.DECISIONS_MD, file=sys.stderr)
        return 1

    recs = recommend_rows(rows, entries)
    content = render(sheet_date, recs, len(rows))

    if args.dry_run:
        print(content)
        print("DRY-RUN: would write %d rows to %s"
              % (len(recs), target_path(sheet_date)), file=sys.stderr)
        return 0

    out = target_path(sheet_date)
    out.write_text(content)
    print("wrote %d rows -> %s" % (len(recs), out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
