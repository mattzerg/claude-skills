#!/usr/bin/env python3
"""Schema drift + stale-entity audit. Exit code 0 if clean, 1 if errors."""
from __future__ import annotations

import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS_DIR))

from lib.entities import load_all  # noqa: E402
from lib.schema import validate  # noqa: E402


def main() -> int:
    entities = load_all()
    all_errors = []
    for e in entities:
        errs = validate(e)
        all_errors.extend(errs)

    print(f"audited {len(entities)} entities")
    if not all_errors:
        print("✓ clean")
        return 0

    by_file: dict[str, list[str]] = {}
    for err in all_errors:
        by_file.setdefault(err.file, []).append(f"  {err.field}: {err.message}")
    for f, msgs in sorted(by_file.items()):
        print(f"✗ {f}")
        for m in msgs:
            print(m)
    print(f"\n{len(all_errors)} error(s) across {len(by_file)} file(s)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
