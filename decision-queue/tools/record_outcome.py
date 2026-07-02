#!/usr/bin/env python3
"""record_outcome.py — append an outcome row to a previously-logged decision.

Closes the loop on whether `auto`-class upgrades are justified. A decision
logged at time T can have its outcome recorded later as:
  - outcome=succeeded   (the shipped/published thing landed cleanly)
  - outcome=regret      (Matt regretted the answer; should have asked)
  - outcome=neutral     (no signal either way; usually for defers that lapsed)

The mining-to-composite pipeline (P1.4) reads both the decision_log entries
AND the outcome rows to compute "Matt always says yes AND it always succeeds"
- ONLY then does it propose an `auto` upgrade. Without outcome data, an 8/8
"yes" pattern could be wrong-but-Matt-was-busy.

Usage:
  record_outcome.py <decision_id> <outcome> [--note "free text"]
  record_outcome.py zpub:pub-2026-05-demo-loop succeeded --note "shipped 6/3, no rollback"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = Path.home() / ".claude/state"
LOG = STATE_DIR / "decisions_log.jsonl"
OUTCOMES = STATE_DIR / "decisions_outcomes.jsonl"

VALID = {"succeeded", "regret", "neutral"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def find_decision(decision_id: str) -> dict | None:
    if not LOG.exists():
        return None
    last = None
    with LOG.open() as fh:
        for line in fh:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("id") == decision_id:
                last = r
    return last


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("decision_id")
    ap.add_argument("outcome", choices=sorted(VALID))
    ap.add_argument("--note")
    args = ap.parse_args()

    decision = find_decision(args.decision_id)
    if not decision:
        print(json.dumps({"err": f"no decision found with id {args.decision_id}"}))
        return 1

    row = {
        "ts": _now_iso(),
        "decision_id": args.decision_id,
        "decision_ts": decision.get("ts"),
        "outcome": args.outcome,
        "note": args.note,
        "decision_answer": decision.get("answer"),
        "autonomy_class": decision.get("autonomy_class"),
        "source": decision.get("source"),
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with OUTCOMES.open("a") as fh:
        fh.write(json.dumps(row, default=str) + "\n")
    print(json.dumps({"ok": True, "logged": row["ts"], "outcomes_file": str(OUTCOMES)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
