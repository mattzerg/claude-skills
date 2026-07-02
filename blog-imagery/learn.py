#!/usr/bin/env python3
"""blog-imagery — learning loop.

For each generated asset (logged to sent-log.jsonl), check whether the asset
has been replaced (different sha256) since generation. If yes, that's a
"regenerated post-imagery" signal — Matt either regenerated with a different
prompt or hand-edited the SVG. Captured in corrections.md so frequency-by-
label tells which asset kinds (hero / body-1 / linkedin-share / etc.) need
the most iteration, and frequency-by-provider tells which generation paths
need rework most often.

Designed to run daily 6:15am alongside graphic-layout/learn.py.

Usage:
    python3 ~/.claude/skills/blog-imagery/learn.py [--max-age-days 90]
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
    """Avoid double-recording — index by (asset_path, ts)."""
    if not CORRECTIONS.exists():
        return set()
    text = CORRECTIONS.read_text()
    return set(re.findall(r"asset_id: `([^`]+)`", text))


def init_corrections() -> None:
    if CORRECTIONS.exists():
        return
    CORRECTIONS.write_text(
        "# Recent corrections (blog-imagery)\n\n"
        "When a generated asset gets replaced after generation (different "
        "sha256), the original output didn't ship as-is. Each entry below "
        "captures one such event. Frequency-by-label and frequency-by-"
        "provider feed `learned_patterns.md` via the central `promote.py`.\n\n"
        "Older corrections age out (>90 days).\n\n---\n\n"
    )


def append_correction(record: dict, new_sha: str) -> None:
    init_corrections()
    today = dt.date.today().isoformat()
    asset_id = f"{record['asset_path']}@{record['ts']}"
    with open(CORRECTIONS, "a") as f:
        f.write(f"## {today} — {record['slug']} / {record['label']} regenerated\n\n")
        f.write(f"- asset_id: `{asset_id}`\n")
        f.write(f"- asset_path: `{record['asset_path']}`\n")
        f.write(f"- aspect: `{record['aspect']}`\n")
        f.write(f"- provider: `{record['provider']}`\n")
        f.write(f"- ts_generated: `{record['ts']}`\n")
        f.write(f"- sha_before: `{record['asset_sha256'][:12]}`\n")
        f.write(f"- sha_after:  `{new_sha[:12]}`\n")
        f.write("\n---\n\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-age-days", type=int, default=90)
    args = ap.parse_args()

    cutoff = dt.datetime.now() - dt.timedelta(days=args.max_age_days)
    logged = load_logged_corrections()
    new_count = 0
    by_label = Counter()
    by_provider = Counter()

    for record in parse_log():
        ts = dt.datetime.fromisoformat(record["ts"])
        if ts < cutoff:
            continue
        asset_id = f"{record['asset_path']}@{record['ts']}"
        if asset_id in logged:
            continue
        asset = Path(record["asset_path"])
        if not asset.exists():
            continue
        new_sha = sha256_file(asset)
        if new_sha == record["asset_sha256"]:
            continue  # same bytes
        append_correction(record, new_sha)
        by_label[record["label"]] += 1
        by_provider[record["provider"]] += 1
        new_count += 1

    if new_count:
        print(f"[blog-imagery learn] +{new_count} corrections")
        for label, n in by_label.most_common():
            print(f"  label={label}: {n}")
        for provider, n in by_provider.most_common():
            print(f"  provider={provider}: {n}")
    else:
        print("[blog-imagery learn] no new corrections")
    return 0


if __name__ == "__main__":
    sys.exit(main())
