#!/usr/bin/python3
"""to-task: promote an idea → new row in Tasks/inbox.md.

Appends to the chosen bucket's table. Updates the idea's frontmatter:
  - status: active (if it was raw)
  - task_link: "[[Tasks/inbox]]#<bucket>"
  - last_touched: today

Default bucket is "To Do". Other choices: "Should Do", "Reminders / Alerts /
Opportunities". For ideas going back to "Relevant Ideas", just leave them in
the backlog — that section is what we're replacing.

Usage:
    to_task.py idea-2026-05-09-zergwallet-receipt-ocr
    to_task.py "zergwallet-receipt" --bucket "Should Do" --domain Zerg --why "now"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "_lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

import inbox_md  # noqa: E402
from frontmatter import read_file, write_file  # noqa: E402
from idea_io import find_by_id, find_by_partial, today_iso  # noqa: E402
from usage import log_event  # noqa: E402
from vault_paths import VAULT_ROOT  # noqa: E402

DEFAULT_BUCKETS = ("To Do", "Should Do", "Reminders / Alerts / Opportunities")


def _next_row_num(rows: list[inbox_md.Row]) -> str:
    nums: list[int] = []
    for r in rows:
        if r.cells and r.cells[0].strip().isdigit():
            nums.append(int(r.cells[0].strip()))
    return str(max(nums) + 1) if nums else "1"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ident", help="idea id or partial slug")
    ap.add_argument("--bucket", default="To Do", choices=DEFAULT_BUCKETS)
    ap.add_argument("--domain", default=None, help="3rd column for To Do/Should Do tables")
    ap.add_argument("--why", default=None, help="4th column ('Why now')")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    p = find_by_id(args.ident) or (find_by_partial(args.ident)[:1] or [None])[0]
    if p is None:
        print(f"idea not found: {args.ident!r}", file=sys.stderr)
        return 2

    meta, body = read_file(p)
    title = meta.get("title") or p.stem
    domain = args.domain or meta.get("subcategory") or meta.get("category") or ""
    why = args.why or "promoted from idea backlog"

    # Build link cell. We do not strikethrough on this side — the idea remains
    # active and just gains a task_link.
    link = f"[[Ideas/{p.parent.name}/{p.stem}]]"
    item_cell = f"{title} → {link}"

    sections = inbox_md.parse()
    target = inbox_md.find_section(sections, args.bucket)
    if target is None or not target.has_table():
        print(f"bucket section not found: {args.bucket!r}", file=sys.stderr)
        return 2

    row_num = _next_row_num(target.rows)
    new_cells = [row_num, item_cell, domain, why]
    # Truncate / pad to header width
    if len(new_cells) < len(target.header):
        new_cells += [""] * (len(target.header) - len(new_cells))
    elif len(new_cells) > len(target.header):
        new_cells = new_cells[: len(target.header)]

    if args.dry_run:
        print(f"DRY RUN — would append row to {args.bucket!r}:")
        print(inbox_md.Row(cells=new_cells).text)
        return 0

    target.rows.append(inbox_md.Row(cells=new_cells))
    inbox_md.write(sections)

    if meta.get("status") == "raw":
        meta["status"] = "active"
    meta["task_link"] = f"[[Tasks/inbox]]#{args.bucket}"
    meta["last_touched"] = today_iso()
    write_file(p, meta, body)

    rel = p.relative_to(VAULT_ROOT)
    log_event(
        "promote_to_task",
        source="to_task.py",
        id=meta.get("id"),
        category=meta.get("category"),
        bucket=args.bucket,
    )
    print(f"promoted: {rel} → Tasks/inbox.md ## {args.bucket}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
