#!/usr/bin/python3
"""from-task: demote a Tasks/inbox.md row → idea file.

Replaces the row's primary cell (Item / Idea) with a strikethrough + vault
link to the new idea file. Other cells preserved. The new idea inherits:
  - title from Item/Idea cell
  - sources: ["[[Tasks/inbox]]"]
  - status: active (it was on the radar already, not a raw sweep extract)
  - subcategory from h3 if present, else h2

Usage:
    from_task.py "Brand pillars to test"
    from_task.py 23 --category content
    from_task.py "Vampire attack"  --category product --tags zerg,vampire-attack
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "_lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

import inbox_md  # noqa: E402
from idea_io import default_meta, default_body, write_new_idea  # noqa: E402
from usage import log_event  # noqa: E402
from vault_paths import VAULT_ROOT  # noqa: E402

CATEGORY_HINTS = {
    "Zerg — product / consumer": "zerg-product",
    "Zerg — GTM / marketing": "zerg-content",
    "Zerg — strategy": "research",
    "Personal / network / consumer-product": "personal-life",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("needle", help="row # or substring of Item/Idea cell")
    ap.add_argument("--category", default=None, choices=("zerg-product", "zerg-content", "zerg-tooling", "personal-venture", "personal-life", "shopping", "research"))
    ap.add_argument("--subcategory", default=None)
    ap.add_argument("--tags", default="")
    ap.add_argument("--why", default="")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    sections = inbox_md.parse()
    hit = inbox_md.find_row_anywhere(sections, args.needle)
    if hit is None:
        print(f"row not found: {args.needle!r}", file=sys.stderr)
        return 2

    section, row_idx = hit
    row = section.rows[row_idx]
    if not row.cells:
        print("empty row?", file=sys.stderr)
        return 2

    # The "title" cell is column 1 (index 1) for tables that lead with #.
    # If the first cell is purely numeric, the title is column 1; else column 0.
    if row.cells[0].strip().isdigit() and len(row.cells) > 1:
        title_col = 1
    else:
        title_col = 0
    title = row.cells[title_col].strip()

    bucket_label = section.h2 + (f" — {section.h3}" if section.h3 else "")
    inferred_cat = (
        args.category
        or CATEGORY_HINTS.get(bucket_label)
        or (CATEGORY_HINTS.get(section.h3) if section.h3 else None)
        or ("zerg-product" if section.h3 and "product" in section.h3.lower() else None)
        or ("zerg-content" if section.h3 and any(k in section.h3.lower() for k in ("gtm", "marketing", "content")) else None)
        or ("personal-life" if section.h3 and "personal" in section.h3.lower() else None)
        or "research"
    )
    inferred_sub = args.subcategory or (section.h3 or section.h2)

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    meta = default_meta(
        title=title,
        category=inferred_cat,
        subcategory=inferred_sub,
        tags=tags,
        status="active",
        sources=["[[Tasks/inbox]]"],
    )
    body_extra = ""
    if len(row.cells) > 2:
        notes = " | ".join(c for c in row.cells[title_col + 1 :] if c.strip())
        if notes:
            body_extra = f"\n\n## Note from inbox.md\n> {notes}"
    body = default_body(idea=title, why=args.why) + body_extra

    if args.dry_run:
        print(f"DRY RUN — would create idea: {meta['id']}")
        print(f"  title: {title}")
        print(f"  category: {inferred_cat}  sub: {inferred_sub}")
        print(f"  bucket: {bucket_label}")
        return 0

    path = write_new_idea(meta, body, in_inbox=False)
    rel = path.relative_to(VAULT_ROOT)

    # Replace the title cell with strikethrough + link to new idea.
    link = f"[[Ideas/{path.parent.name}/{path.stem}]]"
    row.cells[title_col] = f"~~{title}~~ → {link}"
    inbox_md.write(sections)

    log_event(
        "demote_from_task",
        source="from_task.py",
        id=meta["id"],
        category=inferred_cat,
        bucket=bucket_label,
    )
    print(f"demoted: {bucket_label} row → {rel}")
    print(f"  inbox.md row updated to point at the idea")
    return 0


if __name__ == "__main__":
    sys.exit(main())
