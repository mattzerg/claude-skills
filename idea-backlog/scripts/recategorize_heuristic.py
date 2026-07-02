#!/usr/bin/python3
"""recategorize_heuristic: rule-based category reassignment using source paths
and title keywords. No LLM. Free.

Maps each idea to one of the 7-axis categories:
  zerg-product, zerg-content, zerg-tooling,
  personal-venture, personal-life, shopping, research

Resolution order (first match wins):
  1. SOURCE_PATH_RULES — strong signal from where the idea was extracted
  2. TITLE_KEYWORD_RULES — patterns in the title
  3. SUBCATEGORY_RULES — if subcategory matches a known product → zerg-*
  4. FALLBACK — keep existing category, mapped through CATEGORY_LEGACY_ALIASES

Usage:
    recategorize_heuristic.py [--dry-run] [--include-archive]
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

from frontmatter import read_file, write_file  # noqa: E402
from idea_io import iter_all_ideas  # noqa: E402
from usage import log_event  # noqa: E402
from vault_paths import (  # noqa: E402
    ARCHIVE_DIR,
    CATEGORIES,
    CATEGORY_LEGACY_ALIASES,
    INBOX_DIR,
    category_dir,
)

# Rule 1: source path → category
# Order matters; first match wins.
SOURCE_PATH_RULES: list[tuple[re.Pattern, str]] = [
    # Clearly personal-venture sources (Matt's idea catalogs)
    (re.compile(r"Apple Notes/notes/crackpot-venture-ideas"), "personal-venture"),
    (re.compile(r"Apple Notes/notes/dadfinances-ideas"), "personal-venture"),
    (re.compile(r"Apple Notes/notes/business-ideas"), "personal-venture"),
    # Personal-life sources
    (re.compile(r"Apple Notes/sierra/", re.IGNORECASE), "personal-life"),
    (re.compile(r"Apple Notes/notes/sierra"), "personal-life"),
    # Research sources
    (re.compile(r"Apple Notes/notes/thought-experiments-ideas"), "research"),
    (re.compile(r"Apple Notes/touch-surgery/"), "research"),
    # Zerg-content sources
    (re.compile(r"^Marketing/"), "zerg-content"),
    (re.compile(r"^Writing/"), "zerg-content"),
    (re.compile(r"^Landing/"), "zerg-content"),
    # Zerg-product sources
    (re.compile(r"^Projects/Zerg-(Production|Development)/"), "zerg-product"),
    (re.compile(r"^Consulting/"), "zerg-product"),
    (re.compile(r"^Roadmap/"), "zerg-product"),
    (re.compile(r"^Zerg/"), "zerg-product"),
    # Research sources
    (re.compile(r"^Research/"), "research"),
    # Reading / shopping-adjacent
    (re.compile(r"^Reading/"), "personal-life"),
    # Apple Notes b2b → mostly Zerg b2b
    (re.compile(r"Apple Notes/notes/b2b-"), "zerg-product"),
    # Apple Notes weekly-calls → personal-life
    (re.compile(r"Apple Notes/weekly-calls/"), "personal-life"),
    # MatthewZerg/ subdir = personal experimental
    (re.compile(r"MatthewZerg/"), "personal-venture"),
]

# Rule 2: title keywords → category
TITLE_KEYWORD_RULES: list[tuple[re.Pattern, str]] = [
    # Personal-venture: clearly Matt's potential side businesses
    (re.compile(r"\b(bagel|electrician|slumlord|landlord|distressed.*real.?estate|basement.*studio|food.?business|hobby.?business|side.?hustle)\b", re.IGNORECASE), "personal-venture"),
    (re.compile(r"\b(detroit.+(real|rent|prop|house))\b", re.IGNORECASE), "personal-venture"),
    (re.compile(r"\b(personal.?(real.?estate|finance|venture)|matt['']?s\s+(business|side|venture))\b", re.IGNORECASE), "personal-venture"),
    (re.compile(r"\b(buyout|stock.?token.+matt)\b", re.IGNORECASE), "personal-venture"),
    # Shopping
    (re.compile(r"^(buy|gift|book|watch|read|listen)\s+", re.IGNORECASE), "shopping"),
    (re.compile(r"\b(gift\s+ideas|shopping\s+list|wishlist|to.?(buy|read|watch|listen))\b", re.IGNORECASE), "shopping"),
    # Personal-life: travel, food, fitness, family
    (re.compile(r"\b(travel|trip|vacation|itinerary|cdmx|berlin|tokyo|food\s+plan|recipe.?(week|plan)|workout|fitness|hobby|family\s+trip|date\s+night)\b", re.IGNORECASE), "personal-life"),
    # Research
    (re.compile(r"\b(thought\s+experiment|research\s+paper|what.?if\s+|essay|hypothesis)\b", re.IGNORECASE), "research"),
    # Zerg-content
    (re.compile(r"\b(blog\s+post|launch\s+(announcement|post)|thread|tweetstorm|case\s+study|thesis\s+post)\b", re.IGNORECASE), "zerg-content"),
    # Zerg-tooling
    (re.compile(r"\b(skill\s+(for|to)|automation\s+for|cron\s+job|script\s+to)\b", re.IGNORECASE), "zerg-tooling"),
    # Zerg-product (Zerg-prefixed product names)
    (re.compile(r"\b(zergboard|zergwallet|zergmail|zergchat|zergcal|zergmeeting|zergsend|zergstack|zergalytics|zergai|zerg\s+solutions)\b", re.IGNORECASE), "zerg-product"),
]

# Rule 3: subcategory → category prefix
SUBCATEGORY_TO_CATEGORY: dict[str, str] = {
    "zergboard": "zerg-product",
    "zergwallet": "zerg-product",
    "zergmail": "zerg-product",
    "zergchat": "zerg-product",
    "zergcal": "zerg-product",
    "zergmeeting": "zerg-product",
    "zergsend": "zerg-product",
    "zergstack": "zerg-product",
    "zstack": "zerg-product",
    "zergalytics": "zerg-product",
    "zergai": "zerg-product",
    "zerg": "zerg-product",
    "solutions": "zerg-product",
    "pseo": "zerg-content",
    "blog": "zerg-content",
    "launch": "zerg-content",
    "distribution": "zerg-content",
    "sales-enablement": "zerg-content",
    "marketing": "zerg-content",
    "real-estate": "personal-venture",
    "personal-business": "personal-venture",
    "small-business": "personal-venture",
    "lifeos": "personal-life",
    "hobbies": "personal-life",
    "health": "personal-life",
    "food-business": "personal-venture",
    "skill-building": "personal-life",
    "services": "personal-venture",
    "knowledge-economy": "research",
    "llm-evals": "research",
    "cro-experiments": "research",
    "growth": "zerg-content",
}


def first_source_path(meta: dict) -> str:
    paths = meta.get("sources") or []
    if not paths:
        return ""
    p = str(paths[0])
    # Sources stored as "[[Path/To/Note]]" or "[[Path/To/Note.md]]"
    p = p.strip("[]")
    return p


def classify(meta: dict) -> tuple[str, str]:
    """Returns (new_category, reason).

    Order: title keyword > source path > subcategory > legacy-alias fallback.
    Rationale: title tells you what KIND of idea; source tells you WHO it's
    for. Title wins so a 'skill' stays zerg-tooling even when filed under
    Marketing/.
    """
    title = (meta.get("title") or "").strip()
    subcat = (meta.get("subcategory") or "").strip().lower()
    src = first_source_path(meta)

    # 1. title keywords (highest priority — KIND of idea)
    for rx, cat in TITLE_KEYWORD_RULES:
        if rx.search(title):
            return cat, f"title~{rx.pattern[:30]}"

    # 2. source path (WHO it's for / WHERE it came from)
    for rx, cat in SOURCE_PATH_RULES:
        if rx.search(src):
            return cat, f"source~{rx.pattern[:30]}"

    # 3. subcategory rule
    if subcat in SUBCATEGORY_TO_CATEGORY:
        return SUBCATEGORY_TO_CATEGORY[subcat], f"subcat={subcat}"

    # 4. fallback to legacy alias
    cur = (meta.get("category") or "").strip()
    if cur in CATEGORY_LEGACY_ALIASES:
        return CATEGORY_LEGACY_ALIASES[cur], f"legacy-alias({cur})"
    if cur in CATEGORIES:
        return cur, "no-change"
    return "research", "no-rule-fallback"


def move_file(p: Path, new_cat: str, in_inbox: bool, in_archive: bool) -> Path:
    if in_archive:
        new_path = ARCHIVE_DIR / new_cat / p.name
    elif in_inbox:
        new_path = INBOX_DIR / new_cat / p.name
    else:
        new_path = category_dir(new_cat) / p.name
    new_path.parent.mkdir(parents=True, exist_ok=True)
    if new_path == p:
        return p
    n = 2
    while new_path.exists():
        new_path = new_path.parent / f"{p.stem}-{n}.md"
        n += 1
    p.rename(new_path)
    return new_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--include-archive", action="store_true")
    ap.add_argument("--show-reasons", action="store_true")
    args = ap.parse_args()

    transitions: Counter = Counter()
    reason_counts: Counter = Counter()
    walked = 0
    changed = 0

    for p in iter_all_ideas(include_inbox=True, include_archive=args.include_archive):
        try:
            meta, body = read_file(p)
        except Exception:
            continue
        walked += 1
        old_cat = meta.get("category")
        new_cat, reason = classify(meta)
        if new_cat == old_cat:
            continue
        transitions[(old_cat, new_cat)] += 1
        reason_counts[reason] += 1
        if not args.dry_run:
            meta["category"] = new_cat
            in_inbox = INBOX_DIR in p.parents
            in_archive = ARCHIVE_DIR in p.parents
            write_file(p, meta, body)
            move_file(p, new_cat, in_inbox, in_archive)
        changed += 1

    print(f"walked: {walked}")
    print(f"{'would change' if args.dry_run else 'changed'}: {changed}")
    print()
    print("Top transitions (count: from → to):")
    for (a, b), n in transitions.most_common(20):
        print(f"  {n:>4}  {a or '?'}  →  {b}")
    if args.show_reasons:
        print()
        print("Reason breakdown:")
        for r, n in reason_counts.most_common(15):
            print(f"  {n:>4}  {r}")
    if not args.dry_run:
        log_event("recategorize_heuristic_run", source="recategorize_heuristic.py",
                  walked=walked, changed=changed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
