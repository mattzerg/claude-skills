#!/usr/bin/python3
"""normalize_subcategories: collapse subcategory synonyms + canonicalize formatting.

Cheap rule-based pass. No LLM. Makes the existing free-form subcategories
queryable as a controlled vocabulary.

Aliases:
  zergstack         → zstack          (memory: ZergStack in prose, zstack in fs)
  zerg-solutions    → solutions
  llm evaluation    → llm-evals
  health & cooking  → health
  food business     → personal-business

Formatting rules:
  - lowercase
  - spaces → hyphens
  - em-dash → hyphen
  - strip whitespace
  - drop leading 'zerg-' / 'zerg' if it's tautological with a category prefix
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "_lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from frontmatter import read_file, write_file  # noqa: E402
from idea_io import iter_all_ideas  # noqa: E402

ALIASES = {
    "zergstack": "zstack",
    "zerg stack": "zstack",
    "zerg-solutions": "solutions",
    "zerg solutions": "solutions",
    "consulting": "solutions",
    "llm evaluation": "llm-evals",
    "llm-evaluation": "llm-evals",
    "llm-eval": "llm-evals",
    "health-&-cooking": "health",
    "health-and-cooking": "health",
    "food-business": "personal-business",
    "small-business": "personal-business",
    "lifeos": "lifeos",  # keep as-is
    "skill-building": "skill-building",
    "real-estate": "real-estate",
    "knowledge-economy": "knowledge-economy",
}


def normalize(s: str | None) -> str | None:
    if not s:
        return s
    out = s.strip().lower()
    out = out.replace("—", "-").replace("–", "-")
    out = out.replace(" / ", "-").replace("/", "-")
    out = out.replace(" & ", "-and-").replace("&", "-and-")
    out = "-".join(out.split())
    out = out.strip("-")
    if out in ALIASES:
        out = ALIASES[out]
    # strip leading "zerg-" if remainder is meaningful (avoid empty)
    if out.startswith("zerg-") and len(out) > len("zerg-"):
        rest = out[len("zerg-"):]
        # Don't strip zerg- when the rest is a known product (zergboard, zergwallet etc.)
        # because those slugs INCLUDE zerg as part of the product name
        if rest in ("strategy", "marketing", "gtm", "product", "consumer"):
            out = rest
    return out or None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    walked = 0
    touched = 0
    changes: dict[tuple[str, str], int] = {}

    for p in iter_all_ideas(include_inbox=True, include_archive=True):
        try:
            meta, body = read_file(p)
        except Exception:
            continue
        walked += 1
        sub = meta.get("subcategory")
        new_sub = normalize(sub)
        if new_sub != sub:
            changes[(sub or "(none)", new_sub or "(none)")] = changes.get((sub or "(none)", new_sub or "(none)"), 0) + 1
            if not args.dry_run:
                meta["subcategory"] = new_sub
                write_file(p, meta, body)
            touched += 1

    print(f"walked: {walked}")
    print(f"{'would touch' if args.dry_run else 'touched'}: {touched}")
    if changes:
        print("\nTransitions (count: from → to):")
        for (a, b), n in sorted(changes.items(), key=lambda x: -x[1]):
            print(f"  {n:>4}  {a!r}  →  {b!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
