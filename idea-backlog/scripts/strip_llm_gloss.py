#!/usr/bin/python3
"""strip_llm_gloss: remove the `## Why interesting` section from idea files.

The LLM-generated `## Why interesting` puts words in Matt's mouth and was
called out as "doesn't make sense" (memory: feedback_idea_backlog_revisit).
This script walks every idea file in the vault and removes that section,
keeping only what Matt actually wrote (the verbatim source excerpts) plus
the structural sections (`## Idea`, `## Open questions`, `## Source excerpt`).

The raw_extracts.jsonl still has the gloss if we ever want it back.

Usage:
    strip_llm_gloss.py [--dry-run] [--keep-non-empty]

  --keep-non-empty : only strip when the section is empty/short; preserve
                     longer sections (in case they contain user edits).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "_lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from frontmatter import read_file, write_file  # noqa: E402
from idea_io import iter_all_ideas  # noqa: E402

SECTION_RE = re.compile(r"\n##\s+Why interesting\s*\n(.*?)(?=\n## |\Z)", re.DOTALL)


def strip_section(body: str) -> tuple[str, str]:
    """Remove `## Why interesting` block. Returns (new_body, removed_text)."""
    m = SECTION_RE.search(body)
    if not m:
        return body, ""
    removed = m.group(1).strip()
    new = body[: m.start()] + body[m.end():]
    # Collapse triple+ newlines from removal
    new = re.sub(r"\n{3,}", "\n\n", new).strip() + "\n"
    return new, removed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep-non-empty", action="store_true",
                    help="only strip if section is empty/short (likely default placeholder)")
    args = ap.parse_args()

    walked = 0
    stripped = 0
    skipped_user_content = 0

    for p in iter_all_ideas(include_inbox=True, include_archive=True):
        try:
            meta, body = read_file(p)
        except Exception:
            continue
        walked += 1
        new_body, removed = strip_section(body)
        if not removed:
            continue
        # Heuristic: if --keep-non-empty and removed text is >300 chars,
        # likely user-written content, leave alone.
        if args.keep_non_empty and len(removed) > 300:
            skipped_user_content += 1
            continue
        if args.dry_run:
            stripped += 1
            continue
        write_file(p, meta, new_body)
        stripped += 1

    print(f"walked: {walked} idea files")
    if args.keep_non_empty:
        print(f"  skipped (looked user-written, >300 chars): {skipped_user_content}")
    if args.dry_run:
        print(f"would strip: {stripped}")
        print("(dry-run)")
    else:
        print(f"stripped: {stripped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
