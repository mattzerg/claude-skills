#!/usr/bin/env python3
"""corpus_search — one query across slack_corpus + gh_corpus.

Phase 6.C — combiner over the two backfills built in Phase 6.A and 6.B.
Single CLI so "what did Idan say about X in the last month" can be answered
in one command without remembering which corpus has what.

Usage
-----
  corpus_search.py TERM [--user idan|matt|andre] [--since YYYY-MM-DD]
  corpus_search.py TERM --only slack
  corpus_search.py TERM --only gh

Author shortcuts
----------------
  --user idan      → slack U04R0EJACMR + gh idanbeck
  --user matt      → slack U0AFSSPNB1N + gh mattzerg + matteisn
  --user andre     → slack U071RCAG691 + gh ARicardoFranco (best-guess)
  --user <raw>     → exact-match against both indexes (try first as Slack ID, then GH login)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

HOME = Path.home()
SLACK_INDEX = HOME / ".claude/state/slack_corpus/_index.jsonl"
GH_INDEX = HOME / ".claude/state/gh_corpus/_index.jsonl"

USER_MAP = {
    "idan":   {"slack": ["U04R0EJACMR"], "gh": ["idanbeck"]},
    "matt":   {"slack": ["U0AFSSPNB1N"], "gh": ["mattzerg", "matteisn"]},
    "andre":  {"slack": ["U071RCAG691"], "gh": ["ARicardoFranco", "andre"]},
    "michael":{"slack": ["U09NWDY22ES"], "gh": ["michael"]},
    "alex":   {"slack": ["U09JMF6HNJ0"], "gh": []},
}


def _read_jsonl(path: Path):
    if not path.exists():
        return
    for line in path.read_text(errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def _slack_ts_dt(ts) -> dt.datetime | None:
    try:
        return dt.datetime.fromtimestamp(float(ts))
    except (TypeError, ValueError):
        return None


def _gh_ts_dt(ts) -> dt.datetime | None:
    if not ts:
        return None
    try:
        return dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def search_slack(term: str, users: list[str], since: dt.datetime | None) -> list[dict]:
    out = []
    tlow = term.lower()
    for r in _read_jsonl(SLACK_INDEX):
        snippet = r.get("snippet", "") or ""
        if tlow and tlow not in snippet.lower():
            continue
        if users and r.get("user_id") not in users:
            continue
        if since:
            tm = _slack_ts_dt(r.get("ts"))
            if not tm or tm < since:
                continue
        out.append({**r, "_source": "slack", "_when": _slack_ts_dt(r.get("ts"))})
    return out


def search_gh(term: str, users: list[str], since: dt.datetime | None) -> list[dict]:
    out = []
    tlow = term.lower()
    for r in _read_jsonl(GH_INDEX):
        snippet = r.get("snippet", "") or ""
        if tlow and tlow not in snippet.lower():
            continue
        if users and r.get("author") not in users:
            continue
        if since:
            tm = _gh_ts_dt(r.get("ts"))
            if not tm or tm < since:
                continue
        out.append({**r, "_source": "gh", "_when": _gh_ts_dt(r.get("ts"))})
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("term", help="search term (case-insensitive substring)")
    p.add_argument("--user", help="shortcut: idan|matt|andre|michael|alex OR raw ID")
    p.add_argument("--since", help="YYYY-MM-DD")
    p.add_argument("--only", choices=["slack", "gh"], help="restrict to one source")
    p.add_argument("--limit", type=int, default=50)
    args = p.parse_args()

    users_slack: list[str] = []
    users_gh: list[str] = []
    if args.user:
        if args.user in USER_MAP:
            users_slack = USER_MAP[args.user]["slack"]
            users_gh = USER_MAP[args.user]["gh"]
        else:
            users_slack = [args.user]
            users_gh = [args.user]

    since = None
    if args.since:
        try:
            since = dt.datetime.fromisoformat(args.since)
        except ValueError:
            sys.stderr.write(f"bad --since: {args.since}\n")
            return 1

    rows = []
    if args.only != "gh":
        rows += search_slack(args.term, users_slack, since)
    if args.only != "slack":
        rows += search_gh(args.term, users_gh, since)

    # Sort newest first
    rows.sort(key=lambda r: r.get("_when") or dt.datetime.min, reverse=True)
    rows = rows[: args.limit]

    for r in rows:
        when = (r["_when"].strftime("%Y-%m-%d %H:%M") if r.get("_when") else "?")
        if r["_source"] == "slack":
            who = r.get("user_name") or r.get("user_id") or "?"
            print(f"{when}  SLACK #{r.get('channel'):20}  {who:14}  {r.get('snippet')}")
        else:
            state = f"[{r.get('state')}]" if r.get("state") else ""
            print(f"{when}  GH    {r.get('repo'):24} #{r.get('pr')}  {r.get('author'):14} {state}  {r.get('snippet')}")
    print(f"\n[corpus_search] {len(rows)} hit(s) across slack+gh", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
