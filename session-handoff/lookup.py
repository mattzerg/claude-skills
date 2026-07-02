#!/usr/bin/python3
"""session-handoff lookup — "what have other sessions touched recently"

Reads ~/.claude/state/session_handoff.jsonl (written by the session_handoff_capture
Stop hook) and answers cross-session queries:

  lookup.py <slug-or-keyword>      — show every session-fragment that touched the term
  lookup.py --recent [HOURS]       — list every session fragment in window (default 24h)
  lookup.py --approvals            — list every approval/lock that fired in last 7d
  lookup.py --canonical            — list every "canonical-declared" event in last 7d

Output is plain text grouped by session, with a "before you regenerate X, check the
last canonical declaration" warning at the bottom when applicable.

Used by /triage and by future "regenerate"-shaped verbs to fail-soft if a sibling
session already declared something canonical.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

INDEX = Path.home() / ".claude/state/session_handoff.jsonl"


def _load(window_hours: int | None = None) -> list[dict]:
    if not INDEX.exists():
        return []
    cutoff = None
    if window_hours is not None:
        cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=window_hours)
    rows: list[dict] = []
    try:
        with INDEX.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if cutoff:
                    try:
                        ts = dt.datetime.fromisoformat(r["ts"].replace("Z", "+00:00"))
                        if ts < cutoff:
                            continue
                    except Exception:
                        continue
                rows.append(r)
    except OSError:
        return []
    return rows


def _matches(record: dict, term: str) -> list[tuple[str, str]]:
    """Return [(field, value), …] where the term appears."""
    t = term.lower()
    hits: list[tuple[str, str]] = []
    for k in ("pub_slugs", "dashed_slugs", "branches", "approvals", "vault_paths", "zerg_paths", "claude_paths"):
        for v in record.get(k, []) or []:
            if t in v.lower():
                hits.append((k, v))
    return hits


def _short_ts(iso: str) -> str:
    try:
        d = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return d.astimezone().strftime("%a %H:%M")
    except Exception:
        return iso[:16]


def cmd_search(term: str, window_hours: int) -> int:
    rows = _load(window_hours)
    matches: list[tuple[dict, list[tuple[str, str]]]] = []
    for r in rows:
        hits = _matches(r, term)
        if hits:
            matches.append((r, hits))

    if not matches:
        print(f"no sessions in last {window_hours}h touched '{term}'")
        return 0

    print(f"# session-handoff: '{term}' — {len(matches)} session(s) in last {window_hours}h")
    print()
    canonical_seen = False
    for r, hits in matches:
        sid = (r.get("session_id") or "?")[:8]
        print(f"## {_short_ts(r['ts'])}  session={sid}  cwd={r.get('cwd','')[:60]}")
        for field, val in hits[:10]:
            print(f"   [{field}] {val}")
        if r.get("canonical_declared"):
            canonical_seen = True
            print("   ⚠ this session DECLARED something canonical")
        if r.get("approvals"):
            print(f"   ✓ {len(r['approvals'])} approval/lock action(s) fired")
        print()
    if canonical_seen:
        print("⚠ BEFORE regenerating '%s': a sibling session declared canonical state." % term)
        print("  Read that session's outputs FIRST. See feedback_hero_cross_session_approval_awareness.md.")
    return 0


def cmd_recent(window_hours: int) -> int:
    rows = _load(window_hours)
    if not rows:
        print(f"no sessions in last {window_hours}h")
        return 0
    print(f"# session-handoff: {len(rows)} session(s) in last {window_hours}h")
    print()
    for r in rows[-20:]:
        sid = (r.get("session_id") or "?")[:8]
        bits = []
        if r.get("pub_slugs"):
            bits.append(f"pub:{len(r['pub_slugs'])}")
        if r.get("dashed_slugs"):
            bits.append(f"slugs:{len(r['dashed_slugs'])}")
        if r.get("branches"):
            bits.append(f"br:{len(r['branches'])}")
        if r.get("approvals"):
            bits.append(f"approve:{len(r['approvals'])}")
        if r.get("canonical_declared"):
            bits.append("CANONICAL")
        print(f"{_short_ts(r['ts'])}  {sid}  {' '.join(bits)}")
    return 0


def cmd_approvals(window_hours: int) -> int:
    rows = _load(window_hours)
    found = [r for r in rows if r.get("approvals")]
    if not found:
        print(f"no approvals/locks fired in last {window_hours}h")
        return 0
    print(f"# session-handoff: {sum(len(r['approvals']) for r in found)} approval/lock action(s)")
    for r in found:
        sid = (r.get("session_id") or "?")[:8]
        print(f"\n{_short_ts(r['ts'])}  session={sid}")
        for a in r["approvals"]:
            print(f"  {a}")
    return 0


def cmd_canonical(window_hours: int) -> int:
    rows = _load(window_hours)
    found = [r for r in rows if r.get("canonical_declared")]
    if not found:
        print(f"no canonical declarations in last {window_hours}h")
        return 0
    print(f"# session-handoff: {len(found)} canonical-declaration event(s) in last {window_hours}h")
    for r in found:
        sid = (r.get("session_id") or "?")[:8]
        print(f"\n{_short_ts(r['ts'])}  session={sid}")
        for k in ("pub_slugs", "dashed_slugs", "branches", "vault_paths"):
            for v in r.get(k, [])[:5]:
                print(f"  [{k}] {v}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("term", nargs="?", help="slug or keyword to search")
    parser.add_argument("--recent", action="store_true")
    parser.add_argument("--approvals", action="store_true")
    parser.add_argument("--canonical", action="store_true")
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--days", type=int, default=None)
    args = parser.parse_args()

    window = args.hours
    if args.days:
        window = args.days * 24

    if args.recent:
        return cmd_recent(window)
    if args.approvals:
        return cmd_approvals(max(window, 24 * 7))
    if args.canonical:
        return cmd_canonical(max(window, 24 * 7))
    if not args.term:
        parser.print_help()
        return 1
    return cmd_search(args.term, window)


if __name__ == "__main__":
    sys.exit(main())
