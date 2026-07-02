#!/usr/bin/python3
"""kill: move an idea to _archive/ with status=killed and an optional reason."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "_lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from frontmatter import read_file, write_file  # noqa: E402
from idea_io import find_by_id, find_by_partial, today_iso  # noqa: E402
from usage import log_event  # noqa: E402
from vault_paths import ARCHIVE_DIR, VAULT_ROOT  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ident", help="idea id or partial slug")
    ap.add_argument("reason", nargs="?", default="", help="why killed")
    ap.add_argument("--status", default="killed", choices=("killed", "shelved", "shipped"))
    args = ap.parse_args()

    p = find_by_id(args.ident) or (find_by_partial(args.ident)[:1] or [None])[0]
    if p is None:
        print(f"not found: {args.ident}", file=sys.stderr)
        return 2

    meta, body = read_file(p)
    meta["status"] = args.status
    meta["last_touched"] = today_iso()
    if args.reason:
        meta["reason"] = args.reason

    sub = (meta.get("category") or "uncategorized")
    new_path = ARCHIVE_DIR / sub / p.name
    new_path.parent.mkdir(parents=True, exist_ok=True)
    n = 2
    while new_path.exists():
        new_path = ARCHIVE_DIR / sub / f"{p.stem}-{n}.md"
        n += 1
    write_file(new_path, meta, body)
    p.unlink()

    rel = new_path.relative_to(VAULT_ROOT)
    log_event(
        "kill",
        source="kill.py",
        id=meta.get("id"),
        category=meta.get("category"),
        status=meta["status"],
        reason=args.reason or None,
    )
    print(f"archived: {rel}  (status={meta['status']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
