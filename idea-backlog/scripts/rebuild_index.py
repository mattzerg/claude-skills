#!/usr/bin/python3
"""rebuild_index: regenerate Ideas/_meta/index.json.

Small lookup file consumed by the in-session auto-suggest behavior. Re-run
every few hours via cron OR after any non-trivial triage session.

Format: list of small dicts, one per idea (excluding _archive/ by default):
  {
    "id": "...",
    "title": "...",
    "category": "...",
    "subcategory": "...",
    "tags": [...],
    "status": "...",
    "conviction": "...",
    "path": "Ideas/<cat>/<slug>.md"   # vault-relative
  }
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "_lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from frontmatter import read_file  # noqa: E402
from idea_io import iter_all_ideas, save_index  # noqa: E402
from usage import log_event  # noqa: E402
from vault_paths import IDEAS_ROOT, VAULT_ROOT  # noqa: E402


INDEX_META_FIELDS = (
    "effort",
    "time_estimate",
    "cost_estimate",
    "created",
    "last_touched",
    "sources",
    "task_link",
    "depth",
    "viability",
    "scored_at",
    "product",
    "idea_type",
    "horizon",
    "actionability",
    "label_schema",
    "personal_lane",
    "personal_priority",
    "portfolio_company",
    "generalizable",
    "feedback_type",
    "audience",
    "feedback_status",
    "next_artifact",
    "reason",
)


def excerpt(body: str, limit: int = 220) -> str:
    """Compact the Markdown body for lightweight search/autocomplete indexes."""
    text = " ".join((body or "").split())
    return text[:limit]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-archive", action="store_true")
    args = ap.parse_args()

    rows: list[dict] = []
    for p in iter_all_ideas(include_inbox=True, include_archive=args.include_archive):
        try:
            meta, body = read_file(p)
        except Exception:
            continue
        if IDEAS_ROOT in p.parents:
            rel = str(p.relative_to(IDEAS_ROOT))
        elif VAULT_ROOT in p.parents:
            rel = str(p.relative_to(VAULT_ROOT))
        else:
            rel = str(p)
        row = {
            "id": meta.get("id"),
            "title": meta.get("title"),
            "path": rel,
            "category": meta.get("category"),
            "subcategory": meta.get("subcategory"),
            "tags": meta.get("tags") or [],
            "status": meta.get("status"),
            "conviction": meta.get("conviction"),
        }
        for key in INDEX_META_FIELDS:
            row[key] = meta.get(key)
        row["excerpt"] = excerpt(body)
        rows.append(row)

    save_index(rows)
    print(f"index rebuilt: {len(rows)} ideas")
    print(f"  by status:")
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r.get("status") or "unknown"] = by_status.get(r.get("status") or "unknown", 0) + 1
    for k, v in sorted(by_status.items()):
        print(f"    {k}: {v}")
    log_event("rebuild_index", source="rebuild_index.py", count=len(rows), by_status=by_status)
    return 0


if __name__ == "__main__":
    sys.exit(main())
