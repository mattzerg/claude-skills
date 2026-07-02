#!/usr/bin/env python3
"""Build _meta/decisions.json from current index.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

from lib.entities import META_DIR, read_growth_file, write_growth_file  # noqa: E402
from lib.rules import derive  # noqa: E402


def build_decisions(index_path: Path | None = None) -> list[dict]:
    """Read the latest index.json content via staging→iCloud→mirror cascade
    so this works under launchd TCC. If caller passes an explicit
    `index_path`, honor it (used by tests / explicit reruns)."""
    if index_path is not None:
        if not index_path.exists():
            return []
        text = index_path.read_text(encoding="utf-8")
    else:
        text = read_growth_file("_meta/index.json")
        if not text:
            return []
    payload = json.loads(text)
    rows = payload.get("entities", [])
    return [d.to_dict() for d in derive(rows)]


def write_decisions(decisions: list[dict]) -> Path:
    payload = {
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "count": len(decisions),
        "decisions": decisions,
    }
    content = json.dumps(payload, indent=2, default=str) + "\n"
    return write_growth_file("_meta/decisions.json", content)


def main() -> int:
    decisions = build_decisions()
    path = write_decisions(decisions)
    print(f"wrote {path} — {len(decisions)} decisions")
    for d in decisions[:10]:
        print(f"  [{d['priority']:>3}] {d['rule']:<32} {d['message']}")
    if len(decisions) > 10:
        print(f"  ... +{len(decisions) - 10} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
