#!/usr/bin/env python3
"""graphic-layout — learning loop.

For each logged review (sent-log.jsonl), check whether the source asset has
been re-rendered (different sha256) since the review timestamp. If yes, that
counts as a "review-prompted edit" and lands in corrections.md.

Different signal shape than fakematt-email's text-substitution loop: the
"correction" here is "Matt re-rendered the asset after seeing the review,"
which means the review's findings were load-bearing. Over time, frequency
counts per `target_kind` show which graphic types need the most iteration.

Designed to run daily 6:15am alongside the FM voice loops.

Usage:
    python3 ~/.claude/skills/graphic-layout/learn.py [--max-age-days 90]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

SKILL_DIR = Path(__file__).parent
SENT_LOG = SKILL_DIR / "sent-log.jsonl"
CORRECTIONS = SKILL_DIR / "corrections.md"


def sha256_file(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_log() -> list[dict]:
    if not SENT_LOG.exists():
        return []
    out = []
    for line in SENT_LOG.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def load_logged_corrections() -> set[str]:
    """Avoid double-recording — index by review_path."""
    if not CORRECTIONS.exists():
        return set()
    # Matches the markdown-list format `- review_path: \`<path>\``
    return set(re.findall(r"review_path: `([^`]+)`", CORRECTIONS.read_text()))


def init_corrections() -> None:
    if CORRECTIONS.exists():
        return
    CORRECTIONS.write_text(
        "# Recent corrections (graphic-layout)\n\n"
        "When the source asset gets re-rendered after a review (different "
        "sha256), the review's findings were load-bearing. Each entry below "
        "captures one such event. Patterns that recur across distinct assets "
        "feed `learned_patterns.md` via the central `promote.py`.\n\n"
        "Older corrections age out (>90 days).\n\n---\n\n"
    )


def append_correction(record: dict, new_sha: str) -> None:
    init_corrections()
    today = dt.date.today().isoformat()
    with open(CORRECTIONS, "a") as f:
        f.write(f"## {today} — {record['target_kind']} re-rendered after review\n\n")
        f.write(f"- source_path: `{record['source_path']}`\n")
        f.write(f"- review_path: `{record['review_path']}`\n")
        f.write(f"- canvas: `{record['source_size'][0]}×{record['source_size'][1]}`\n")
        f.write(f"- ts_reviewed: `{record['ts']}`\n")
        f.write(f"- sha_before: `{record['source_sha256'][:12]}`\n")
        f.write(f"- sha_after:  `{new_sha[:12]}`\n")
        f.write("\n---\n\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-age-days", type=int, default=90)
    args = ap.parse_args()

    cutoff = dt.datetime.now() - dt.timedelta(days=args.max_age_days)
    logged = load_logged_corrections()
    new_count = 0
    summary = Counter()

    for record in parse_log():
        ts = dt.datetime.fromisoformat(record["ts"])
        if ts < cutoff:
            continue
        if record["review_path"] in logged:
            continue
        source = Path(record["source_path"])
        if not source.exists():
            continue
        new_sha = sha256_file(source)
        if new_sha == record["source_sha256"]:
            continue  # no re-render yet
        append_correction(record, new_sha)
        summary[record["target_kind"]] += 1
        new_count += 1

    if new_count:
        print(f"[graphic-layout learn] +{new_count} corrections")
        for kind, n in summary.most_common():
            print(f"  {kind}: {n}")
    else:
        print("[graphic-layout learn] no new corrections")
    return 0


if __name__ == "__main__":
    sys.exit(main())
