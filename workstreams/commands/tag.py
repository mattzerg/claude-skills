#!/usr/bin/env python3
"""Show what an item would be assigned to.

Usage:
  tag.py <inbox-line-fragment>            # find inbox row, show ws assignment
  tag.py PR <repo>#<num>                  # show ws assignment for a PR by id
  tag.py session <pid>                    # show ws assignment for a session

This is a READ-ONLY classifier. Use `/workstreams edit` to actually change
selectors in the manifest if the assignment is wrong. The point of tag is to
debug WHICH workstream catches WHICH item.
"""
from __future__ import annotations

import sys
from pathlib import Path


WORKSTREAMS_DIR = Path.home() / ".claude" / "workstreams"


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: tag.py <inbox-fragment | PR repo#num | session pid>", file=sys.stderr)
        return 1
    sys.path.insert(0, str(WORKSTREAMS_DIR.parent))
    from workstreams import manifest as m, sources, assigner

    mf = m.load()

    kind = argv[0].lower()
    if kind == "pr":
        if len(argv) < 2:
            print("usage: tag.py PR <repo>#<num>", file=sys.stderr)
            return 1
        target = argv[1]
        prs = sources.fetch_open_prs()
        match = next((p for p in prs if p.id == target or target in p.id), None)
        if not match:
            print(f"PR not found: {target}", file=sys.stderr)
            return 2
        return _explain(match, mf, assigner)

    if kind == "session":
        if len(argv) < 2:
            print("usage: tag.py session <pid>", file=sys.stderr)
            return 1
        pid = argv[1]
        sessions = sources.list_sessions()
        match = next((s for s in sessions if s.id == f"session:{pid}"), None)
        if not match:
            print(f"session not found: pid={pid}", file=sys.stderr)
            return 2
        return _explain(match, mf, assigner)

    # Default: search inbox by fragment.
    fragment = " ".join(argv).lower()
    items = sources.parse_inbox(mf.inbox_path)
    matches = [it for it in items if fragment in it.title.lower()]
    if not matches:
        print(f"no inbox row contains: {fragment!r}", file=sys.stderr)
        return 2
    if len(matches) > 1:
        print(f"{len(matches)} matches for {fragment!r}:")
        for it in matches:
            print(f"  - [{it.extras.get('bucket','?')}] {it.title}")
        return 1
    return _explain(matches[0], mf, assigner)


def _explain(item, mf, assigner) -> int:
    print(f"item: [{item.kind}] {item.title}")
    extras = {k: v for k, v in item.extras.items() if k not in {"_error"}}
    if extras:
        for k, v in extras.items():
            print(f"  {k}: {v}")
    print()
    scores = []
    for ws in mf.workstreams:
        if ws.catchall:
            continue
        s = assigner.score(item, ws)
        if s > 0:
            scores.append((s, ws.id))
    if not scores:
        print(f"→ assigned to CATCHALL ({mf.catchall().id})")
        return 0
    scores.sort(reverse=True)
    print("scores:")
    for s, wid in scores:
        marker = "  ← winner" if (s, wid) == scores[0] else ""
        print(f"  {wid:<32} {s}{marker}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
