#!/usr/bin/python3
"""promote: raw → active, with optional category move.

Used by triage to lift a candidate out of `_inbox/` into a real category folder.
Also usable on its own to flip an existing idea's status.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "_lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from frontmatter import read_file, write_file  # noqa: E402
from idea_io import find_by_id, find_by_partial, today_iso  # noqa: E402
from usage import log_event  # noqa: E402
from vault_paths import INBOX_DIR, category_dir, CATEGORIES, VAULT_ROOT  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ident", help="idea id or partial slug")
    ap.add_argument("--category", default=None, choices=CATEGORIES)
    ap.add_argument("--status", default="active", choices=("raw", "active", "shelved", "shipped"))
    args = ap.parse_args()

    p = find_by_id(args.ident) or (find_by_partial(args.ident)[:1] or [None])[0]
    if p is None:
        print(f"not found: {args.ident}", file=sys.stderr)
        return 2

    meta, body = read_file(p)
    target_cat = args.category or meta.get("category") or "research"
    if target_cat not in CATEGORIES:
        print(f"invalid category: {target_cat}", file=sys.stderr)
        return 2

    meta["category"] = target_cat
    meta["status"] = args.status
    meta["last_touched"] = today_iso()

    in_inbox = INBOX_DIR in p.parents
    if in_inbox or p.parent != category_dir(target_cat):
        new_path = category_dir(target_cat) / p.name
        n = 2
        while new_path.exists():
            new_path = category_dir(target_cat) / f"{p.stem}-{n}.md"
            n += 1
        new_path.parent.mkdir(parents=True, exist_ok=True)
        write_file(new_path, meta, body)
        p.unlink()
        p = new_path

    if not in_inbox:
        write_file(p, meta, body)

    rel = p.relative_to(VAULT_ROOT)
    log_event(
        "promote",
        source="promote.py",
        id=meta.get("id"),
        category=target_cat,
        status=meta["status"],
        from_inbox=in_inbox,
    )
    print(f"promoted: {rel}  (status={meta['status']}, category={target_cat})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
