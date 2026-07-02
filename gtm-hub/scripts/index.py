#!/usr/bin/env python3
"""Build _meta/index.json — flat cross-entity index for fast queries."""
from __future__ import annotations

import json
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

from lib.entities import GROWTH_DIR, load_all, write_growth_file  # noqa: E402
from lib.schema import envelope_view  # noqa: E402
from lib.derived import annotate_index  # noqa: E402


def build_index() -> list[dict]:
    base = [envelope_view(e) for e in load_all()]
    return annotate_index(base)


def write_index(rows: list[dict]) -> Path:
    payload = {
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "root": str(GROWTH_DIR),
        "count": len(rows),
        "entities": rows,
    }
    content = json.dumps(payload, indent=2, default=str) + "\n"
    return write_growth_file("_meta/index.json", content)


def main() -> int:
    rows = build_index()
    path = write_index(rows)
    by_type: dict[str, int] = {}
    for r in rows:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1
    print(f"wrote {path} — {len(rows)} entities")
    for t, n in sorted(by_type.items()):
        print(f"  {t}: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
