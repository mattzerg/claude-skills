#!/usr/bin/python3
"""recall: search ideas + Tasks/inbox.md for a topic.

Ranking: keyword overlap on title/tags/body + status/conviction boost. No
embeddings on this path — fast, deterministic, good enough for top-10. The
embedding-based recall is reserved for `extract`/`dedupe`.

Usage:
    recall.py "zergwallet receipt"
    recall.py "ai agents marketplace" --limit 20 --include-archive
    recall.py --category content "thesis"
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "_lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from frontmatter import read_file  # noqa: E402
from idea_io import iter_all_ideas  # noqa: E402
from usage import log_event  # noqa: E402
from vault_paths import TASKS_INBOX, VAULT_ROOT  # noqa: E402


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Recall ideas + tasks matching a topic")
    ap.add_argument("query", help="search text")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--category", default=None)
    ap.add_argument("--include-archive", action="store_true")
    ap.add_argument("--no-tasks", action="store_true", help="Skip Tasks/inbox.md scan")
    return ap.parse_args()


def _tokens(text: str) -> set[str]:
    return {t.lower() for t in re.findall(r"\w+", text or "") if len(t) > 2}


def _score(query_tokens: set[str], text: str, tags: list[str], status: str, conviction: str) -> int:
    text_tokens = _tokens(text) | {t.lower() for t in tags or []}
    overlap = len(query_tokens & text_tokens)
    if overlap == 0:
        return 0
    score = overlap * 10
    if status == "active":
        score += 3
    if conviction == "high":
        score += 2
    return score


def search_ideas(query: str, *, limit: int, category: str | None, include_archive: bool) -> list[tuple[int, dict, Path]]:
    qtok = _tokens(query)
    results: list[tuple[int, dict, Path]] = []
    for p in iter_all_ideas(include_inbox=True, include_archive=include_archive):
        try:
            meta, body = read_file(p)
        except Exception:
            continue
        if category and meta.get("category") != category:
            continue
        haystack = " ".join([meta.get("title") or "", body, meta.get("subcategory") or ""])
        score = _score(qtok, haystack, meta.get("tags") or [], meta.get("status") or "", meta.get("conviction") or "")
        if score:
            results.append((score, meta, p))
    results.sort(key=lambda r: r[0], reverse=True)
    return results[:limit]


def search_tasks(query: str, *, limit: int = 10) -> list[str]:
    """Return matching lines from Tasks/inbox.md (case-insensitive substring)."""
    if not TASKS_INBOX.exists():
        return []
    qtok = _tokens(query)
    if not qtok:
        return []
    matches: list[tuple[int, str]] = []
    bucket = ""
    for line in TASKS_INBOX.read_text().splitlines():
        s = line.strip()
        if s.startswith("## "):
            bucket = s[3:]
            continue
        if s.startswith("### "):
            bucket = bucket.split(" — ")[0] + " — " + s[4:]
            continue
        if not s.startswith("|") or set(s) <= set("|- "):
            continue
        line_tokens = _tokens(line)
        overlap = len(qtok & line_tokens)
        if overlap:
            matches.append((overlap, f"[{bucket}] {line.strip()}"))
    matches.sort(key=lambda x: x[0], reverse=True)
    return [m for _, m in matches[:limit]]


def main() -> int:
    args = parse_args()
    print(f"# recall: {args.query!r}\n")

    idea_hits = search_ideas(
        args.query,
        limit=args.limit,
        category=args.category,
        include_archive=args.include_archive,
    )
    print(f"## ideas ({len(idea_hits)})")
    if not idea_hits:
        print("  (no matches)")
    for score, meta, p in idea_hits:
        rel = p.relative_to(VAULT_ROOT) if VAULT_ROOT in p.parents else p
        tags = ",".join(meta.get("tags") or [])
        print(
            f"  [{score:3d}] {meta.get('title','?')!r}"
            f"  cat={meta.get('category','?')}  status={meta.get('status','?')}"
            f"  conv={meta.get('conviction','?')}"
            f"  tags=[{tags}]"
        )
        print(f"        → {rel}")

    task_hits: list[str] = []
    if not args.no_tasks:
        task_hits = search_tasks(args.query)
        print(f"\n## tasks/inbox.md ({len(task_hits)})")
        if not task_hits:
            print("  (no matches)")
        for line in task_hits:
            print(f"  {line}")

    log_event(
        "recall",
        source="recall.py",
        query=args.query,
        idea_hits=len(idea_hits),
        task_hits=len(task_hits),
        category=args.category,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
