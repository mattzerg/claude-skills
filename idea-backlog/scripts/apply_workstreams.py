#!/usr/bin/python3
"""apply_workstreams: tag each idea with its workstream id using selectors
from ~/.config/zerg/workstreams.yaml.

Adds `workstream:` field to frontmatter. Doesn't move files (workstream
taxonomy is still in flux; tagging is safer than relocating).

Selector evaluation order (first match wins):
  1. Source path matches any `vault_folders` entry
  2. Tags / subcategory intersect with workstream id-shaped tokens
  3. Title regex match against `inbox_text_regex`
  4. Current `category` matches workstream's `idea_categories` whitelist
  5. Catchall workstream (`catchall: true`) — `other` workstream

Usage:
    apply_workstreams.py [--dry-run] [--include-archive]
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "_lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

try:
    import yaml
except ImportError:
    print("PyYAML not installed", file=sys.stderr)
    sys.exit(2)

from frontmatter import read_file, write_file  # noqa: E402
from idea_io import iter_all_ideas  # noqa: E402
from usage import log_event  # noqa: E402

MANIFEST = Path.home() / ".config" / "zerg" / "workstreams.yaml"


def load_workstreams() -> list[dict]:
    data = yaml.safe_load(MANIFEST.read_text())
    return data.get("workstreams") or []


def first_source(meta: dict) -> str:
    src = (meta.get("sources") or [""])[0]
    return src.strip("[]")


def assign(meta: dict, ws_list: list[dict]) -> tuple[str | None, str]:
    """Return (workstream_id, reason)."""
    src = first_source(meta)
    title = (meta.get("title") or "").lower()
    subcat = (meta.get("subcategory") or "").lower()
    tags = [t.lower() for t in (meta.get("tags") or [])]
    cat = (meta.get("category") or "").lower()

    # Map new 7-axis category names back to the old ones the workstreams reference
    legacy_cat = {
        "zerg-product": "product",
        "zerg-content": "content",
        "zerg-tooling": "tooling",
        "personal-life": "personal",
        "personal-venture": "personal",
        "shopping": "personal",
        "research": "research",
    }.get(cat, cat)

    # 1. vault_folders (most specific — actual file path match)
    for ws in ws_list:
        sel = ws.get("selectors") or {}
        for vf in sel.get("vault_folders") or []:
            if vf in src:
                return ws["id"], f"vault_folder={vf}"

    # 2. subcategory / tag direct match against well-known product keywords
    PRODUCT_TO_WS = {
        "zergboard": "zerg-zergboard",
        "zergwallet": "zerg-other",
        "zergmail": "zerg-other",
        "zergchat": "zerg-other",
        "zergcal": "zerg-other",
        "zergmeeting": "zerg-other",
        "zergsend": "zerg-other",
        "zergstack": "zerg-other",
        "zstack": "zerg-other",
        "zergalytics": "zerg-other",
        "zergai": "zerg-other",
        "solutions": "zerg-websites",
        "4727": "personal-4727",
        "real-estate": "personal-4727",
    }
    for keyword, ws_id in PRODUCT_TO_WS.items():
        if keyword == subcat or keyword in tags:
            return ws_id, f"subcat/tag={keyword}"

    # 3. title regex
    for ws in ws_list:
        sel = ws.get("selectors") or {}
        rx = sel.get("inbox_text_regex")
        if rx:
            try:
                if re.search(rx, title):
                    return ws["id"], f"title~{rx[:30]}"
            except re.error:
                pass

    # 4. legacy idea_categories
    for ws in ws_list:
        sel = ws.get("selectors") or {}
        if legacy_cat in (sel.get("idea_categories") or []):
            return ws["id"], f"legacy-cat={legacy_cat}"

    # 5. catchall
    for ws in ws_list:
        if ws.get("catchall"):
            return ws["id"], "catchall"

    return None, "unmatched"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--include-archive", action="store_true")
    args = ap.parse_args()

    ws_list = load_workstreams()
    print(f"workstreams loaded: {len(ws_list)}")

    by_ws: Counter = Counter()
    by_reason: Counter = Counter()
    walked = changed = 0

    for p in iter_all_ideas(include_inbox=True, include_archive=args.include_archive):
        try:
            meta, body = read_file(p)
        except Exception:
            continue
        walked += 1
        ws_id, reason = assign(meta, ws_list)
        by_ws[ws_id or "(unmatched)"] += 1
        by_reason[reason] += 1
        if ws_id and meta.get("workstream") != ws_id:
            if not args.dry_run:
                meta["workstream"] = ws_id
                write_file(p, meta, body)
            changed += 1

    print(f"\nwalked: {walked}")
    print(f"{'would tag' if args.dry_run else 'tagged'}: {changed}")
    print()
    print("Distribution by workstream:")
    for ws, n in by_ws.most_common():
        print(f"  {n:>4}  {ws}")
    print()
    print("Reason breakdown:")
    for r, n in by_reason.most_common(10):
        print(f"  {n:>4}  {r}")

    if not args.dry_run:
        log_event("apply_workstreams", source="apply_workstreams.py", walked=walked, changed=changed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
