#!/usr/bin/env python3
"""
cards.py — propose Zergboard cards for top-N ranked gaps + drift items.

ALWAYS confirms with the user before creating cards (per skill design).

Usage:
    python3 cards.py <category> [--top 5] [--board UUID|name] [--lane Pipeline] [--dry-run] [--yes]

Without --yes, the script prints proposed cards as JSON and exits with code 0
without creating anything. The orchestrator (or user) re-runs with --yes and
optional --pick "1,3,5" to confirm a subset.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from lib import state, vault, config as cfg

ZB_SCRIPT = Path.home() / ".claude" / "skills" / "zergboard-skill" / "zergboard_skill.py"

# Default fallback boards (per plan)
MARKETING_BOARD = "7bf7ab2a-ac70-4b29-85bf-74a6db6a0760"
WEBSITE_BOARD = "8ef863c1-765f-493e-8622-2e65b4d2ca61"

# Lane prefix per gap bucket / drift
LANE_BY_BUCKET = {
    "table_stakes": "[Pipeline]",
    "differentiator_parity": "[Pipeline]",
    "whitespace": "[Pipeline]",
    "we_have_they_dont": "[Brand & Site]",
    "drift": "[Brand & Site]",
}


def card_for_ranked_gap(r: dict, category: str, product: str) -> dict:
    lane = LANE_BY_BUCKET.get(r["bucket"], "[Pipeline]")
    title = f"{lane} [{product}] Close gap: {r['feature']}"
    desc = (
        f"Source: competitive-review-skill ({category})\n\n"
        f"Bucket: {r['bucket']}\n"
        f"Frequency across competitors: {r['frequency']}\n"
        f"Strategic fit (1-5): {r['fit']}\n"
        f"Estimated cost: {r['cost']}\n"
        f"Score (freq × fit ÷ cost): {r['score']}\n\n"
        f"Evidence: {r.get('evidence','')}\n\n"
        f"See: MattZerg/Competitive/{vault.slugify(category)}/gaps.md"
    )
    priority = "high" if r["bucket"] == "table_stakes" and r["score"] >= 1.5 else "medium"
    return {"title": title, "description": desc, "priority": priority, "kind": "gap", "key": r["feature"]}


def card_for_drift(d: dict, category: str, product: str) -> dict:
    lane = LANE_BY_BUCKET["drift"]
    title = f"{lane} [{product}] Resolve drift: {d['feature']}"
    desc = (
        f"Source: competitive-review-skill ({category}) — spec/site drift\n\n"
        f"Spec says: {d.get('spec_says','?')}\n"
        f"Live site says: {d.get('live_says','?')}\n"
        f"Note: {d.get('note','')}\n\n"
        f"Action: either update the spec or surface the feature on the live site.\n"
        f"See: MattZerg/Competitive/{vault.slugify(category)}/drift.md"
    )
    return {"title": title, "description": desc, "priority": "medium", "kind": "drift", "key": d["feature"]}


def propose(s: dict, category: str, product: str, top: int) -> list[dict]:
    rankings = s.get("rankings", [])
    # L-cost cap: drop L-cost gaps before slicing top_n (per stage_2_ranking)
    if cfg.l_cost_cap_hard():
        rankings = [r for r in rankings if str(r.get("cost", "M")).upper() != "L"]
    rankings = rankings[:top]
    drift = s.get("drift", [])
    cards = [card_for_ranked_gap(r, category, product) for r in rankings]
    cards.extend(card_for_drift(d, category, product) for d in drift)
    return cards


def create_card(card: dict, board: str) -> dict:
    cmd = [
        "python3", str(ZB_SCRIPT), "create", board,
        "--title", card["title"],
        "--description", card["description"],
        "--priority", card.get("priority", "medium"),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        return {"error": result.stderr.strip() or result.stdout.strip(), "card": card}
    try:
        return json.loads(result.stdout)
    except Exception:
        return {"raw": result.stdout, "card": card}


def main():
    parser = argparse.ArgumentParser(description="Propose + (optionally) create Zergboard cards")
    parser.add_argument("category")
    parser.add_argument("--top", type=int, default=5, help="Top-N ranked gaps to propose")
    parser.add_argument("--board", default=MARKETING_BOARD, help="Board UUID or name (default: Marketing)")
    parser.add_argument("--yes", action="store_true", help="Actually create cards (without this, dry-run only)")
    parser.add_argument("--pick", help="Comma-separated 1-indexed list of cards to create (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Print proposed cards and exit (default behavior without --yes)")
    parser.add_argument("--override-pause", action="store_true", help="Override stage_5_delivery.card_creation_mode == PAUSED_revisit_later")
    args = parser.parse_args()

    if cfg.card_creation_paused() and not args.override_pause:
        print(
            "[cards] card_creation_mode is PAUSED_revisit_later in config.json — exiting without proposals.\n"
            "        Pass --override-pause to bypass, or update config.json to resume.",
            file=sys.stderr,
        )
        sys.exit(0)

    s = state.load(args.category)
    product = s.get("product") or "?"
    if not s.get("rankings"):
        print("Error: no rankings in state. Run rank.py first.", file=sys.stderr)
        sys.exit(1)

    cards = propose(s, args.category, product, args.top)
    if args.pick:
        idx = {int(i.strip()) - 1 for i in args.pick.split(",") if i.strip()}
        cards = [c for i, c in enumerate(cards) if i in idx]

    print(f"\n[cards] {len(cards)} proposed for board {args.board}:\n")
    for i, c in enumerate(cards, 1):
        print(f"  {i:2d}. ({c['kind']}, {c.get('priority','?')}) {c['title']}")

    if not args.yes or args.dry_run:
        print("\n[cards] dry run — no cards created.")
        print("       Re-run with --yes (and optional --pick 1,3,5) to confirm.")
        state.update(args.category, proposed_cards=cards)
        return

    created = []
    for c in cards:
        print(f"\n[cards] creating: {c['title']}")
        result = create_card(c, args.board)
        created.append({"proposal": c, "result": result})
        if "error" in result:
            print(f"  ❌ {result['error']}", file=sys.stderr)
        else:
            card_obj = result.get("card", {})
            print(f"  ✓ {card_obj.get('external_id','?')} created")

    state.update(args.category, created_cards=created)
    print(f"\n[cards] {len(created)} card creation attempts. See state for full results.")


if __name__ == "__main__":
    main()
