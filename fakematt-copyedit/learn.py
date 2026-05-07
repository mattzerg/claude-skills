#!/usr/bin/env python3
"""Fake Matt copyedit — learning loop.

For each logged review, check whether Matt has edited the input draft since
the review timestamp. If yes, diff the snapshot vs current state and append
material edits to corrections.md. Same architecture as fakematt-email/learn.py
but the "sent body" is "the prose Matt actually kept after seeing the review."

Designed to run daily 6am alongside the email skill's learn.py.

Usage:
    python3 ~/.claude/skills/fakematt-copyedit/learn.py [--max-age-days 90]
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import json
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).parent
SENT_LOG = SKILL_DIR / "sent-log.jsonl"
CORRECTIONS = SKILL_DIR / "corrections.md"


def diff_summary(generated: str, sent: str) -> tuple[str, int]:
    g = [l.rstrip() for l in generated.splitlines()]
    s = [l.rstrip() for l in sent.splitlines()]
    diff = list(difflib.unified_diff(g, s, lineterm="", n=2))
    changed = sum(1 for l in diff if l.startswith(("+", "-")) and not l.startswith(("+++", "---")) and l[1:].strip())
    return "\n".join(diff), changed


def append_correction(record, current_content, diff_text, changed) -> None:
    if not CORRECTIONS.exists():
        CORRECTIONS.write_text(
            "# Recent corrections (copyedit)\n\n"
            "When Matt edits a draft after seeing a copyedit review, the diff is "
            "captured here. The next prompt sees this. Patterns that recur ≥3× "
            "across distinct drafts get auto-promoted to learned_patterns.md.\n\n"
            "Older corrections age out (>90 days).\n\n---\n\n"
        )
    today = dt.date.today().isoformat()
    with open(CORRECTIONS, "a") as f:
        # Use the input filename as a "recipient" stand-in so promote.py treats each
        # draft as a distinct correspondent for threshold counting.
        recipient_proxy = Path(record["input_path"]).stem
        f.write(f"\n## {today} — to {recipient_proxy}\n\n")
        f.write(f"**Original draft:**\n\n```\n{record['input_content_at_review'][:3000]}\n```\n\n")
        f.write(f"**What Matt sent:**\n\n```\n{current_content[:3000]}\n```\n\n")
        if changed:
            f.write(f"**Diff** ({changed} changed lines):\n\n```diff\n{diff_text[:3000]}\n```\n\n")
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
        input_path = Path(record["input_path"])
        if not input_path.exists():
            record["checked"] = True
            record["status"] = "input-deleted"
            continue
        try:
            current = input_path.read_text()
        except Exception:
            continue
        original = record.get("input_content_at_review", "")
        if not original or current == original:
            # No change yet — leave as unchecked so we re-poll tomorrow,
            # unless it's been > 30 days (then give up).
            try:
                review_ts = dt.datetime.strptime(record["ts"][:8], "%Y%m%d")
                age_days = (dt.datetime.now() - review_ts).days
                if age_days > 30:
                    record["checked"] = True
                    record["status"] = "no-edit-30d"
            except Exception:
                pass
            continue
        # We have an edit
        diff_text, changed = diff_summary(original, current)
        if changed >= 2:
            append_correction(record, current, diff_text, changed)
            print(f"[learn] correction: {input_path.name} ({changed} changed lines)")
            updated += 1
        else:
            print(f"[learn] no material edit: {input_path.name}")
        record["checked"] = True
        record["status"] = "edited"
        record["edit_distance"] = changed

    with open(SENT_LOG, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    prune_old_corrections(args.max_age_days)
    print(f"[learn] {updated} new corrections appended")
    return 0


if __name__ == "__main__":
    sys.exit(main())
