#!/usr/bin/python3
"""capture: fast-write a new idea file.

Usage:
    capture.py "<text>" [--category product] [--subcategory zergwallet] \\
        [--tags a,b,c] [--why "..."] [--conviction medium] [--effort m] \\
        [--time-estimate 2w] [--cost-estimate $200] [--source "[[some/note]]"]

Defaults: category=research (catch-all), conviction=medium, status=active.

If `<text>` looks like "<title> :: <one-line idea body>", split on `::`.
Otherwise the full text is the title and body is empty (you fill it later).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "_lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from idea_io import default_meta, default_body, write_new_idea  # noqa: E402
from usage import log_event  # noqa: E402


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Capture a new idea")
    ap.add_argument("text", help="Title or 'title :: body'")
    ap.add_argument("--category", default="research", choices=("zerg-product", "zerg-content", "zerg-tooling", "personal-venture", "personal-life", "shopping", "research"))
    ap.add_argument("--subcategory", default=None)
    ap.add_argument("--tags", default="", help="comma-separated")
    ap.add_argument("--why", default="", help="Why interesting (2-4 sentences)")
    ap.add_argument("--conviction", default="medium", choices=("low", "medium", "high"))
    ap.add_argument("--effort", default="unknown")
    ap.add_argument("--time-estimate", dest="time_estimate", default="unknown")
    ap.add_argument("--cost-estimate", dest="cost_estimate", default="unknown")
    ap.add_argument("--source", action="append", default=[], help="vault link, repeatable")
    ap.add_argument("--status", default="active", choices=("raw", "active", "shelved"))
    ap.add_argument("--no-open", action="store_true", default=True)
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    text = args.text.strip()
    if "::" in text:
        title, _, idea_body = text.partition("::")
        title, idea_body = title.strip(), idea_body.strip()
    else:
        title, idea_body = text, ""

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    meta = default_meta(
        title=title,
        category=args.category,
        subcategory=args.subcategory,
        tags=tags,
        status=args.status,
        sources=args.source or [],
    )
    meta["conviction"] = args.conviction
    meta["effort"] = args.effort
    meta["time_estimate"] = args.time_estimate
    meta["cost_estimate"] = args.cost_estimate
    body = default_body(idea=idea_body, why=args.why)

    path = write_new_idea(meta, body, in_inbox=False)
    rel = path.relative_to(path.parents[2])  # MattZerg/Ideas/<cat>/<slug>.md
    log_event(
        "capture",
        source="capture.py",
        id=meta["id"],
        category=meta["category"],
        conviction=meta["conviction"],
        tags=tags,
        has_body=bool(idea_body),
    )
    print(f"captured: {path}")
    print(f"  id={meta['id']}")
    print(f"  vault: {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
