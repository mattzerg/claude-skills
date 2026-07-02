#!/usr/bin/python3
"""touch: bump last_touched on an idea (kills the 90-day idle flag)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "_lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from frontmatter import update_field  # noqa: E402
from idea_io import find_by_id, find_by_partial, today_iso  # noqa: E402
from usage import log_event  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ident", help="idea id or partial slug")
    args = ap.parse_args()

    p = find_by_id(args.ident) or (find_by_partial(args.ident)[:1] or [None])[0]
    if p is None:
        print(f"not found: {args.ident}", file=sys.stderr)
        return 2
    update_field(p, last_touched=today_iso())
    log_event("touch", source="touch.py", id=p.stem)
    print(f"touched {p.name} → {today_iso()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
