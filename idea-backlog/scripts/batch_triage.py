#!/usr/bin/python3
"""batch_triage: programmatic triage operations against `_inbox/`.

Two opt-in ops with explicit gating:

  --promote-multi-source N   : promote any inbox idea whose `sources:` has
                                ≥N entries (recurring across notes = high
                                signal). Sets conviction=high, status=active.
  --shelve-derivative         : shelve inbox items whose ALL source paths fall
                                under derivative directories (review outputs,
                                fakematt-copyedit interview/review files).
                                Status=shelved, archived.

Always print a dry-run summary first; pass `--commit` to actually move files.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_LIB = Path(__file__).resolve().parent / "_lib"
if str(_LIB) not in sys.path:
    sys.path.insert(0, str(_LIB))

from frontmatter import read_file, update_field  # noqa: E402
from vault_paths import INBOX_DIR  # noqa: E402

SCRIPTS_DIR = Path(__file__).resolve().parent

DERIVATIVE_PATTERNS = (
    "Writing/exports/",
    "/_reviews/",
    "fakematt-copyedit/",
)

CURATED_IDEA_FILES = (
    "Notes/Apple Notes/notes/business-ideas",
    "Notes/Apple Notes/notes/crackpot-venture-ideas",
    "Notes/Apple Notes/notes/core-ideas",
    "Notes/Apple Notes/notes/base-ideas",
    "Notes/Apple Notes/notes/dadfinances-ideas",
    "Notes/Apple Notes/notes/thought-experiments-ideas",
    "Notes/Apple Notes/notes/b2b-referral-ideas",
)


def all_inbox_files() -> list[Path]:
    if not INBOX_DIR.exists():
        return []
    return sorted(INBOX_DIR.rglob("*.md"))


def is_pure_derivative(meta: dict) -> bool:
    paths = meta.get("sources") or []
    if not paths:
        return False
    return all(any(s in p for s in DERIVATIVE_PATTERNS) for p in paths)


def has_n_sources(meta: dict, n: int) -> bool:
    return len(meta.get("sources") or []) >= n


def from_curated_ideas_file(meta: dict) -> bool:
    paths = meta.get("sources") or []
    return any(any(c in p for c in CURATED_IDEA_FILES) for p in paths)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--promote-multi-source", type=int, default=0, metavar="N",
                    help="promote any inbox item with >=N sources (set conviction=high)")
    ap.add_argument("--shelve-derivative", action="store_true",
                    help="shelve items whose ALL sources are derivative (review outputs)")
    ap.add_argument("--promote-curated-ideas-files", action="store_true",
                    help="promote items sourced from Matt's already-curated *-ideas.md files (medium conviction)")
    ap.add_argument("--apply-scores", action="store_true",
                    help="apply depth/viability scoring filter: kill if depth=1 & viability<=2; promote-high if both>=4; promote-med if both>=3")
    ap.add_argument("--apply-scores-pass2", action="store_true",
                    help="second pass: kill v=1 OR (d=1 AND v=2); promote conviction=low when v>=4 (any d); catch any d>=3/v>=3 stragglers as medium")
    ap.add_argument("--apply-scores-pass3", action="store_true",
                    help="strictest cull: kill v<=2 OR d=1 (regardless of other axis). Leaves only d>=2,v>=3 in inbox.")
    ap.add_argument("--commit", action="store_true",
                    help="actually run the actions; default is dry-run")
    args = ap.parse_args()

    files = all_inbox_files()
    if not files:
        print("inbox empty.")
        return 0

    promote_targets: list[tuple[Path, dict, str]] = []  # (path, meta, conviction)
    shelve_targets: list[tuple[Path, dict]] = []
    kill_targets: list[tuple[Path, dict, str]] = []  # (path, meta, reason)

    for p in files:
        try:
            meta, _ = read_file(p)
        except Exception:
            continue
        if args.promote_multi_source and has_n_sources(meta, args.promote_multi_source):
            promote_targets.append((p, meta, "high"))
        elif args.promote_curated_ideas_files and from_curated_ideas_file(meta):
            promote_targets.append((p, meta, "medium"))
        elif args.apply_scores and meta.get("depth") is not None and meta.get("viability") is not None:
            d, v = int(meta["depth"]), int(meta["viability"])
            if d == 1 and v <= 2:
                kill_targets.append((p, meta, f"low-quality (depth={d}, viability={v})"))
            elif d >= 4 and v >= 4:
                promote_targets.append((p, meta, "high"))
            elif d >= 3 and v >= 3:
                promote_targets.append((p, meta, "medium"))
        elif args.apply_scores_pass2 and meta.get("depth") is not None and meta.get("viability") is not None:
            d, v = int(meta["depth"]), int(meta["viability"])
            if v == 1 or (d == 1 and v == 2):
                kill_targets.append((p, meta, f"pass2-noise (depth={d}, viability={v})"))
            elif v >= 4:
                # high-viability undeveloped — promote at low conviction
                promote_targets.append((p, meta, "low"))
            elif d >= 3 and v >= 3:
                # straggler that pass1 missed (e.g., scored after pass1)
                promote_targets.append((p, meta, "medium"))
        elif args.apply_scores_pass3 and meta.get("depth") is not None and meta.get("viability") is not None:
            d, v = int(meta["depth"]), int(meta["viability"])
            if v <= 2 or d == 1:
                kill_targets.append((p, meta, f"pass3-strict (depth={d}, viability={v})"))
        if args.shelve_derivative and is_pure_derivative(meta):
            shelve_targets.append((p, meta))

    print(f"inbox: {len(files)} items")
    if args.promote_multi_source or args.promote_curated_ideas_files or args.apply_scores or args.apply_scores_pass2 or args.apply_scores_pass3:
        print(f"would promote: {len(promote_targets)}")
    if args.apply_scores or args.apply_scores_pass2 or args.apply_scores_pass3:
        print(f"would kill:    {len(kill_targets)} (low-quality scores)")
    if args.shelve_derivative:
        print(f"would shelve:  {len(shelve_targets)} (pure derivative)")

    if not args.commit:
        print("\n--- promote sample ---")
        for p, meta, conv in promote_targets[:8]:
            d = meta.get("depth"); v = meta.get("viability")
            score_tag = f" d={d} v={v}" if d is not None else ""
            print(f"  [{conv}{score_tag}] {meta.get('title','?')[:60]}")
        if kill_targets:
            print("\n--- kill sample ---")
            for p, meta, reason in kill_targets[:8]:
                print(f"  [{reason}] {meta.get('title','?')[:60]}")
        if shelve_targets:
            print("\n--- shelve sample ---")
            for p, meta in shelve_targets[:8]:
                print(f"  {meta.get('title','?')[:60]}")
        print("\n(dry-run; pass --commit to apply)")
        return 0

    promoted = 0
    for p, meta, conv in promote_targets:
        update_field(p, conviction=conv)
        r = subprocess.run(
            ["/usr/bin/python3", str(SCRIPTS_DIR / "promote.py"), p.stem],
            check=False,
            capture_output=True,
        )
        if r.returncode == 0:
            promoted += 1

    killed = 0
    for p, meta, reason in kill_targets:
        r = subprocess.run(
            ["/usr/bin/python3", str(SCRIPTS_DIR / "kill.py"), p.stem, reason],
            check=False,
            capture_output=True,
        )
        if r.returncode == 0:
            killed += 1

    shelved = 0
    for p, meta in shelve_targets:
        r = subprocess.run(
            ["/usr/bin/python3", str(SCRIPTS_DIR / "kill.py"), p.stem,
             "pure derivative source (review/interview output)", "--status", "shelved"],
            check=False,
            capture_output=True,
        )
        if r.returncode == 0:
            shelved += 1

    print(f"\npromoted: {promoted}")
    print(f"killed:   {killed}")
    print(f"shelved:  {shelved}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
