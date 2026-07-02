#!/usr/bin/python3
"""dedupe: cluster near-duplicate raw extracts.

Stage 2 of the seed sweep. Reads raw_extracts.jsonl, clusters items whose
(title + one_line) Jaccard overlap exceeds the threshold, and writes
clusters.jsonl with one row per cluster.

Each cluster row:
  {
    "members": [<raw_extract>, ...],
    "title": "<canonical title — most-frequent or longest>",
    "category": "<most-frequent>",
    "subcategory": "<most-frequent>",
    "tags": [<union of member tags>],
    "one_line": "<from canonical>",
    "why_interesting": "<longest among members>",
    "source_excerpts": [<excerpts>, ...],
    "source_paths": [<unique paths>, ...]
  }

Pure-Python: no embeddings deps. Token-level Jaccard with stopword strip is
plenty for 1000-row clustering.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "_lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from usage import log_event  # noqa: E402
from vault_paths import workdir  # noqa: E402

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "for", "to", "of", "in", "on", "at",
    "by", "with", "from", "as", "is", "are", "was", "were", "be", "been", "being",
    "this", "that", "these", "those", "it", "its", "our", "their", "his", "her",
    "you", "your", "we", "i", "my", "me", "they", "them", "if", "then", "than",
    "so", "do", "does", "did", "will", "would", "should", "could", "may", "might",
    "have", "has", "had", "not", "no", "yes", "up", "down", "out", "into", "via",
    "about", "what", "when", "where", "why", "how", "who",
}


def tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"\w+", (text or "").lower()) if len(t) > 2 and t not in STOPWORDS}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def cluster(rows: list[dict], threshold: float) -> list[list[int]]:
    n = len(rows)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    sigs = [tokens((r.get("title") or "") + " " + (r.get("one_line") or "")) for r in rows]
    for i in range(n):
        for j in range(i + 1, n):
            if jaccard(sigs[i], sigs[j]) >= threshold:
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def collapse(members: list[dict]) -> dict:
    cats = [m.get("category") for m in members if m.get("category")]
    subs = [m.get("subcategory") for m in members if m.get("subcategory")]
    tags: list[str] = []
    for m in members:
        for t in (m.get("tags") or []):
            if t and t not in tags:
                tags.append(t)
    cat = Counter(cats).most_common(1)[0][0] if cats else "research"
    sub = Counter(subs).most_common(1)[0][0] if subs else None

    # canonical title: most-frequent; tie-break = longest
    title_counts = Counter(m.get("title") for m in members if m.get("title"))
    if title_counts:
        max_count = max(title_counts.values())
        candidates = [t for t, c in title_counts.items() if c == max_count]
        title = max(candidates, key=len)
    else:
        title = "(untitled)"

    one_lines = [m.get("one_line") for m in members if m.get("one_line")]
    one_line = max(one_lines, key=len) if one_lines else ""
    whys = [m.get("why_interesting") for m in members if m.get("why_interesting")]
    why = max(whys, key=len) if whys else ""

    excerpts = []
    seen = set()
    for m in members:
        ex = (m.get("source_excerpt") or "").strip()
        if ex and ex not in seen:
            seen.add(ex)
            excerpts.append(ex)

    paths = []
    for m in members:
        sp = m.get("source_path")
        if sp and sp not in paths:
            paths.append(sp)

    cross_categories = sorted({c for c in cats if c and c != cat})

    return {
        "title": title,
        "category": cat,
        "subcategory": sub,
        "tags": tags + cross_categories,
        "one_line": one_line,
        "why_interesting": why,
        "source_excerpts": excerpts,
        "source_paths": paths,
        "member_count": len(members),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=0.55, help="Jaccard threshold (token overlap)")
    ap.add_argument("--input", default=None, help="override raw_extracts.jsonl path")
    ap.add_argument("--output", default=None, help="override clusters.jsonl path")
    args = ap.parse_args()

    wd = workdir()
    in_path = Path(args.input) if args.input else wd / "raw_extracts.jsonl"
    out_path = Path(args.output) if args.output else wd / "clusters.jsonl"

    if not in_path.exists():
        print(f"no raw extracts at {in_path} — run extract.py first", file=sys.stderr)
        return 2

    rows = [json.loads(line) for line in in_path.read_text().splitlines() if line.strip()]
    print(f"loaded {len(rows)} raw extracts")

    if not rows:
        print("nothing to cluster.")
        return 0

    groups = cluster(rows, args.threshold)
    groups.sort(key=lambda g: -len(g))

    with out_path.open("w") as fh:
        for g in groups:
            members = [rows[i] for i in g]
            collapsed = collapse(members)
            collapsed["members"] = members
            fh.write(json.dumps(collapsed, ensure_ascii=False) + "\n")

    print(f"clustered → {len(groups)} distinct ideas (threshold={args.threshold})")
    print(f"  largest cluster: {len(groups[0])} members" if groups else "")
    print(f"  singletons: {sum(1 for g in groups if len(g) == 1)}")
    print(f"output: {out_path}")
    print("next: write_inbox.py")
    log_event(
        "dedupe_run",
        source="dedupe.py",
        raw_count=len(rows),
        cluster_count=len(groups),
        threshold=args.threshold,
        singletons=sum(1 for g in groups if len(g) == 1),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
