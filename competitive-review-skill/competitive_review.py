#!/usr/bin/env python3
"""
competitive_review.py — orchestrator that walks the full skill flow with confirmation gates.

Usage:
    python3 competitive_review.py <category> --product <ZergProduct> [seed1.com ...] \\
        [--n 10] [--top 10] [--phase discover|scan|compare|rank|report|cards|all]

Default --phase=all walks: discover → STOP → scan → compare → rank → report → STOP → cards
Stops are enforced by NOT running the next phase; just print the suggested next command.

For non-interactive use (e.g. orchestrated by a parent Claude session), pass:
  --phase discover                 (then user/parent confirms candidates)
  --phase scan-and-build           (scan → compare → rank → report; rank uses defaults if non-TTY)
  --phase cards --top 5 --yes      (creates cards after confirmation)
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent
PY = sys.executable


def run(script: str, *args: str) -> int:
    cmd = [PY, str(SKILL / script), *args]
    print(f"\n$ {' '.join(cmd)}\n", file=sys.stderr)
    return subprocess.run(cmd).returncode


def main():
    p = argparse.ArgumentParser(description="Competitive review orchestrator")
    p.add_argument("category")
    p.add_argument("seeds", nargs="*")
    p.add_argument("--product", required=True)
    p.add_argument("--n", type=int, default=10)
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--card-top", type=int, default=5)
    p.add_argument(
        "--phase",
        default="discover",
        choices=["discover", "scan", "compare", "rank", "report", "cards", "hunt", "scan-and-build", "all"],
    )
    p.add_argument("--yes", action="store_true", help="For cards phase: actually create")
    p.add_argument("--pick", help="For cards phase: subset to create, e.g. '1,3,5'")
    p.add_argument("--board", help="For cards phase: board UUID or name")
    args = p.parse_args()

    phase = args.phase
    cat = args.category

    if phase in ("discover", "all"):
        rc = run("discover.py", cat, *args.seeds, "--product", args.product, "--n", str(args.n))
        if rc != 0:
            sys.exit(rc)
        if phase == "discover":
            print("\n=== STOP ===")
            print("Review the candidate list above. To proceed, run:")
            print(f"  python3 {SKILL/'competitive_review.py'} {cat} --product {args.product} --phase scan-and-build")
            return

    if phase in ("scan", "scan-and-build", "all"):
        rc = run("scan.py", cat, "--all")
        if rc != 0:
            sys.exit(rc)

    if phase in ("compare", "scan-and-build", "all"):
        rc = run("compare.py", cat, "--product", args.product)
        if rc != 0:
            sys.exit(rc)

    if phase in ("rank", "scan-and-build", "all"):
        rc = run("rank.py", cat, "--top", str(args.top))
        if rc != 0:
            sys.exit(rc)

    if phase in ("hunt", "scan-and-build", "all"):
        # Hunt is non-fatal: if it errors, the rest of the pipeline still runs
        rc = run("hunt.py", cat, "--product", args.product)
        if rc != 0:
            print(f"  [warn] hunt.py failed rc={rc}, continuing...", file=sys.stderr)

    if phase in ("report", "scan-and-build", "all"):
        rc = run("report.py", cat, "--product", args.product)
        if rc != 0:
            sys.exit(rc)
        print("\n=== STOP ===")
        print("Review the report. To propose Zergboard cards, run:")
        print(f"  python3 {SKILL/'competitive_review.py'} {cat} --product {args.product} --phase cards --card-top {args.card_top}")
        if phase != "all":
            return

    if phase == "cards" or (phase == "all" and args.yes):
        card_args = [cat, "--top", str(args.card_top)]
        if args.board:
            card_args += ["--board", args.board]
        if args.yes:
            card_args.append("--yes")
        if args.pick:
            card_args += ["--pick", args.pick]
        rc = run("cards.py", *card_args)
        if rc != 0:
            sys.exit(rc)


if __name__ == "__main__":
    main()
