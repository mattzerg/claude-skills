#!/usr/bin/env python3
"""gate_age_scan.py — flag zpub entries whose gates have been pending too long.

For every zpub entry (Growth/publishing/_meta/index.json) with at least one
pending gate (signoff/pr_gate/send_gate/... = pending|needed|blocked|failed,
plus the date_confirmed pseudo-gate when a publish_target exists unconfirmed)
whose wait-age exceeds --max-age-days, emit ONE decision-queue record into
~/.claude/state/decisions_pending.jsonl.

  - Stable key:  gateage:<pub-id>:<primary-gate>
  - One record per ENTRY (keyed on the highest-precedence pending gate),
    not one per gate — no queue flooding.
  - Recommended default derives from the 2026-06-11 signoff-sheet heuristics
    (ship / hold-to-date; archive is offered but never recommended for real
    content; deletion is never an option).
  - Idempotent: skips keys already present (undecided) in the intake jsonl
    AND keys already decided in decisions_log.jsonl.
  - NOTHING ships or posts. Output is decision-queue records only.
  - Never touches MattZerg/Tasks/decisions_pending.md (generator-owned).

Age basis (documented choice): wait_age = max(days past publish_target,
days since last touch), last touch = most recent of frontmatter updated_at
and file mtime. See dq_lib.py docstring for the full rationale.

Usage:
  gate_age_scan.py [--max-age-days N] [--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dq_lib as dq  # noqa: E402


def build_record(entry, gate, pend, age, basis):
    verdict, rationale, revisit = dq.recommend(entry, age)
    pub_id = entry.get("id") or "unknown"
    title = entry.get("title") or pub_id
    # For ship-recommended items the hold option still needs a sane date:
    # one week out, so "hold" is a real alternative rather than "hold to today".
    from datetime import timedelta
    hold_date = (revisit.isoformat() if revisit
                 else (dq.today() + timedelta(days=7)).isoformat())
    hold_choice = "hold to %s" % hold_date
    suggested = hold_choice if verdict == "hold" else verdict

    gate_label = gate.replace("_", " ")
    context = ("%s has waited %d days for %s — ship, hold to %s, or archive?"
               % (title, int(age), gate_label, hold_date))

    tgt = dq.parse_dt(entry.get("publish_target"))
    deadline = tgt.date().isoformat() if tgt else None

    if age > 28:
        priority = 90
    elif age > 21:
        priority = 80
    else:
        priority = 65

    return {
        "id": "gateage:%s:%s" % (pub_id, gate),
        "source": "zpub-gateage",
        "entity_path": entry.get("_path", ""),
        "entity_id": pub_id,
        "age_days": round(age, 4),
        "age_human": dq.age_human(age),
        "autonomy_class": "content_publish",
        "autonomy_verdict": "needs_matt",
        "verdict_source": "gate_age_scan",
        "why": ("Gate '%s' pending past the staleness threshold; forcing an "
                "explicit ship/hold/archive call instead of silent drift."
                % gate),
        "context_one_line": context,
        "choices": ["ship", hold_choice, "archive", "details"],
        "suggested_default": suggested,
        "deadline": deadline,
        "priority": priority,
        "raw": {
            "gate": gate,
            "pending_gates": pend,
            "age_basis": basis,
            "status": entry.get("status"),
            "type": entry.get("type"),
            "blockers": entry.get("blockers") or [],
            "recommendation": verdict,
            "rationale": rationale,
            "refs": {"pub_id": pub_id, "path": entry.get("_path", "")},
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Emit decision-queue records for zpub entries with stale "
                    "pending gates. Never ships/posts; never recommends "
                    "deletion; never touches decisions_pending.md.")
    ap.add_argument("--max-age-days", type=float, default=14.0,
                    help="staleness threshold in days (default: 14)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print would-be records; write nothing")
    args = ap.parse_args()

    try:
        entries = dq.load_index_entries()
    except Exception as e:
        print("ERROR: cannot load zpub index: %s" % e, file=sys.stderr)
        return 1

    try:
        existing = dq.pending_ids()
        decided = dq.decided_ids()
    except Exception as e:
        print("ERROR: cannot read decision-queue state: %s" % e,
              file=sys.stderr)
        return 1

    new_records, skipped_dup, skipped_decided = [], 0, 0
    for entry in entries:
        status = (entry.get("status") or "").lower()
        if status in dq.TERMINAL_STATUSES:
            continue
        pend = dq.pending_gates(entry)
        # Exclude entries whose ONLY pending pseudo-gate is date_confirmed and
        # which have no real gates at all (prelaunch packs etc. stay quiet).
        real_pend = [g for g in pend if g != "date_confirmed"]
        if not real_pend:
            continue
        age, basis = dq.entry_wait_age(entry)
        if age <= args.max_age_days:
            continue
        gate = dq.primary_gate(real_pend)
        rec = build_record(entry, gate, real_pend, age, basis)
        if rec["id"] in decided:
            skipped_decided += 1
            continue
        if rec["id"] in existing:
            skipped_dup += 1
            continue
        new_records.append(rec)

    label = "DRY-RUN would emit" if args.dry_run else "emitting"
    print("%s %d record(s); skipped %d already-pending, %d already-decided "
          "(threshold %.0fd)"
          % (label, len(new_records), skipped_dup, skipped_decided,
             args.max_age_days))
    for rec in new_records:
        print("  %-58s %4s  default=%-22s %s"
              % (rec["id"], rec["age_human"], rec["suggested_default"],
                 rec["raw"]["rationale"][:80]))

    written = dq.append_records(new_records, dry_run=args.dry_run)
    if not args.dry_run:
        print("appended %d record(s) to %s" % (written, dq.PENDING_JSONL))
    return 0


if __name__ == "__main__":
    sys.exit(main())
