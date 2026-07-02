#!/usr/bin/python3
"""log_suggest: hand-log an auto-surface event from a Claude session.

When the auto-surface behavioral rule (`feedback_idea_backlog_surfacing.md`)
fires — i.e. Claude detects a topic match and surfaces 1-3 ideas inline —
Claude calls this script to record it. That gives us a measurable signal of
how often the system actually fires in practice.

Usage:
    log_suggest.py "<topic>" --count 3 [--ideas <id1>,<id2>] [--session-id <id>]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "_lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from usage import log_event  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("topic")
    ap.add_argument("--count", type=int, default=0, help="ideas surfaced")
    ap.add_argument("--ideas", default="", help="comma-separated ids surfaced")
    ap.add_argument("--session-id", default=None, help="optional session identifier for dedupe")
    args = ap.parse_args()

    ids = [x.strip() for x in args.ideas.split(",") if x.strip()]
    log_event(
        "auto_suggest_fire",
        source="log_suggest.py",
        topic=args.topic,
        count=args.count or len(ids),
        ids=ids,
        session_id=args.session_id,
    )
    print(f"logged auto-suggest: topic={args.topic!r} count={args.count or len(ids)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
