#!/usr/bin/env python3
"""
rank.py — interactive prioritization of top-N gaps.

Presents the top gaps from the table_stakes + differentiator_parity buckets,
asks the user to tag strategic fit (1–5) and rough cost (S/M/L), computes
freq × fit ÷ cost, sorts, and writes back to state.

Two modes:
  - Interactive (default): TTY prompts for each gap.
  - Batch: --tags file.json with {feature: {fit: N, cost: "S|M|L"}} mapping.

Usage:
    python3 rank.py <category> [--top 10] [--tags tags.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lib import state, config as cfg

COST_WEIGHT = {"S": 1, "M": 3, "L": 8}


def gaps_to_rank(matrix: list[dict], top: int) -> list[dict]:
    """Pull table_stakes first (sorted by frequency desc), then differentiator_parity until we hit `top`."""
    ts = sorted(
        [m for m in matrix if m.get("bucket") == "table_stakes"],
        key=lambda m: m.get("frequency", 0),
        reverse=True,
    )
    dp = sorted(
        [m for m in matrix if m.get("bucket") == "differentiator_parity"],
        key=lambda m: m.get("frequency", 0),
        reverse=True,
    )
    return (ts + dp)[:top]


def prompt_int(label: str, default: int, lo: int, hi: int) -> int:
    while True:
        raw = input(f"    {label} [{lo}-{hi}, default {default}]: ").strip()
        if not raw:
            return default
        try:
            n = int(raw)
            if lo <= n <= hi:
                return n
        except ValueError:
            pass
        print(f"      enter an integer {lo}-{hi}")


def prompt_choice(label: str, default: str, choices: list[str]) -> str:
    while True:
        raw = input(f"    {label} [{'/'.join(choices)}, default {default}]: ").strip().upper()
        if not raw:
            return default
        if raw in choices:
            return raw
        print(f"      pick one of: {', '.join(choices)}")


def main():
    parser = argparse.ArgumentParser(description="Rank gaps by freq × fit ÷ cost")
    parser.add_argument("category")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--tags", help="JSON file with pre-supplied {feature: {fit, cost}}")
    parser.add_argument("--default-fit", type=int, default=cfg.batch_default_fit())
    parser.add_argument("--default-cost", choices=["S", "M", "L"], default=cfg.batch_default_cost())
    args = parser.parse_args()

    s = state.load(args.category)
    matrix = s.get("matrix", [])
    if not matrix:
        print("Error: no matrix in state. Run compare.py first.", file=sys.stderr)
        sys.exit(1)

    gaps = gaps_to_rank(matrix, args.top)
    if not gaps:
        print("[rank] no gaps to rank (no table_stakes or differentiator_parity).")
        state.update(args.category, rankings=[])
        return

    pre_tags = {}
    if args.tags:
        pre_tags = json.loads(Path(args.tags).read_text())

    print(f"\n[rank] Tagging top {len(gaps)} gaps. Score = frequency × fit ÷ cost-weight.")
    print(f"       fit: 1 (don't bother) … 5 (must have). cost: S=1 / M=3 / L=8.\n")

    rankings = []
    for i, g in enumerate(gaps, 1):
        feature = g["feature"]
        freq = g.get("frequency", 0)
        bucket = g.get("bucket", "?")
        evidence = g.get("evidence", "")

        print(f"  {i}. [{bucket}] {feature}  (frequency: {freq})")
        if evidence:
            print(f"       {evidence}")

        if feature in pre_tags:
            fit = int(pre_tags[feature].get("fit", args.default_fit))
            cost = pre_tags[feature].get("cost", args.default_cost).upper()
            print(f"     (pre-tagged: fit={fit}, cost={cost})")
        elif sys.stdin.isatty():
            fit = prompt_int("strategic fit", args.default_fit, 1, 5)
            cost = prompt_choice("build cost", args.default_cost, ["S", "M", "L"])
        else:
            fit = args.default_fit
            cost = args.default_cost

        score = freq * fit / COST_WEIGHT[cost]
        rankings.append(
            {
                "feature": feature,
                "bucket": bucket,
                "frequency": freq,
                "fit": fit,
                "cost": cost,
                "score": round(score, 2),
                "evidence": evidence,
            }
        )

    rankings.sort(key=lambda r: r["score"], reverse=True)
    state.update(args.category, rankings=rankings)

    print("\n[rank] Final order (highest score first):\n")
    for i, r in enumerate(rankings, 1):
        print(f"  {i:2d}. {r['score']:>5.2f}  [{r['bucket']:<22s}] {r['feature']}  (freq={r['frequency']}, fit={r['fit']}, cost={r['cost']})")


if __name__ == "__main__":
    main()
