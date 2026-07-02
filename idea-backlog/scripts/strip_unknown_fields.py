#!/usr/bin/python3
"""strip_unknown_fields: remove frontmatter fields that are 'unknown' across all idea files.

The seed sweep defaults `effort`, `time_estimate`, `cost_estimate` to `unknown`.
That's visual noise on every file. Strip them when set to 'unknown' (case-insensitive).
Triage / capture / promote can re-add them later when known.

Usage:
    strip_unknown_fields.py [--dry-run] [--fields effort,time_estimate,cost_estimate]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "_lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from frontmatter import read_file, write_file  # noqa: E402
from idea_io import iter_all_ideas  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--fields", default="effort,time_estimate,cost_estimate",
                    help="comma-separated field names to strip when value is 'unknown'")
    args = ap.parse_args()

    fields = [f.strip() for f in args.fields.split(",") if f.strip()]
    walked = 0
    touched = 0

    for p in iter_all_ideas(include_inbox=True, include_archive=True):
        try:
            meta, body = read_file(p)
        except Exception:
            continue
        walked += 1
        changed = False
        for f in fields:
            v = meta.get(f)
            if isinstance(v, str) and v.strip().lower() == "unknown":
                del meta[f]
                changed = True
        if changed:
            touched += 1
            if not args.dry_run:
                write_file(p, meta, body)

    print(f"walked: {walked}")
    print(f"{'would touch' if args.dry_run else 'touched'}: {touched}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
