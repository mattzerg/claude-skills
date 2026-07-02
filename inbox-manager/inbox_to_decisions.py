#!/usr/bin/env python3
"""inbox-manager Phase-1 PREP — decision-queue 'inbox' source adapter (PREVIEW).

NON-ACTIVATING. Reads today's items-<date>.jsonl and produces DecisionItem-shaped
records matching decision-queue's schema (aggregate.py DecisionItem), but writes
them to a PREVIEW file — NOT into ~/.claude/state/decisions_pending.jsonl. This
lets us see exactly what cards Phase 1 would inject without touching the live
queue (which is already 149 deep). Wiring in later = one source entry in
decision-queue/tools/aggregate.py that calls build_inbox_cards().

Batching rule (plan §1 archive handling / §3 don't-flood):
  - Bulk low-risk cleanup (KILL/RECEIPT) → ONE rolled-up batch card.
  - Only uncertain / medium+ risk items (HUMAN_IN, scam, PROJECT) → individual cards.

Output: ~/.claude/state/inbox/decision_preview-<date>.jsonl
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

STATE = Path.home() / ".claude/state/inbox"


def _card(**kw) -> dict:
    """DecisionItem-shaped dict (mirrors decision-queue aggregate.py fields)."""
    base = {
        "id": "", "source": "inbox", "entity_path": "", "entity_id": "",
        "age_days": 0.0, "age_human": "", "autonomy_class": "", "autonomy_verdict": "needs_matt",
        "verdict_source": "class:inbox", "why": "", "context_one_line": "",
        "choices": [], "suggested_default": "details", "deadline": None,
        "priority": 60, "raw": {},
    }
    base.update(kw)
    return base


def build_inbox_cards(records: list[dict]) -> list[dict]:
    """records (items-<date>.jsonl) → list of DecisionItem-shaped cards."""
    cards: list[dict] = []
    archive_batch: list[dict] = []

    for r in records:
        bucket = r["bucket"]
        oneline = f"{r['sender_email']}: {r['subject']}"[:140]
        common = dict(entity_id=r["id"], age_days=float(r["days_since_last_message"]),
                      age_human=f"{r['days_since_last_message']}d", context_one_line=oneline,
                      raw={"account": r["account"], "bucket": bucket, "tier": r.get("tier"),
                           "scam": r["scam"], "recommended_action": r["recommended_action"]})

        if r["scam"]["label"] in ("PHISH", "SUSPICIOUS"):
            cards.append(_card(
                id=f"inbox:scam:{r['account']}:{r['id']}", autonomy_class="inbox_scam",
                why=f"{r['scam']['label']} score {r['scam']['score']}", priority=85,
                choices=["block/report", "not scam", "details"], **common))
        elif bucket == "HUMAN_IN":
            pr = 90 if r.get("tier") == "A" else 75 if r.get("tier") == "B" else 65
            cards.append(_card(
                id=f"inbox:reply:{r['account']}:{r['id']}", autonomy_class="inbox_reply",
                why=r["rationale"], priority=pr,
                choices=["draft reply", "archive", "ignore", "details"], **common))
        elif bucket == "PROJECT":
            cards.append(_card(
                id=f"inbox:action:{r['account']}:{r['id']}", autonomy_class="inbox_action",
                why=r["rationale"], priority=70,
                choices=["do it", "defer-3d", "ignore", "details"], **common))
        elif bucket in ("KILL", "RECEIPT"):
            archive_batch.append(r)

    # ONE batch-archive rollup card (never individual cards for bulk cleanup)
    if archive_batch:
        by_acct: dict[str, int] = {}
        for r in archive_batch:
            by_acct[r["account"]] = by_acct.get(r["account"], 0) + 1
        summary = ", ".join(f"{n} in {a}" for a, n in by_acct.items())
        cards.append(_card(
            id=f"inbox:archive_batch:{dt.date.today().isoformat()}",
            autonomy_class="inbox_archive_batch",
            why="Bulk low-risk cleanup (newsletters/promos/receipts). Reversible; humans excluded.",
            priority=40, context_one_line=f"Approve {len(archive_batch)} archives ({summary})",
            choices=["approve all", "review each", "skip"],
            raw={"count": len(archive_batch), "by_account": by_acct,
                 "ids": [{"id": r["id"], "account": r["account"]} for r in archive_batch]}))
    return cards


def main() -> int:
    today = dt.date.today().isoformat()
    items_path = STATE / f"items-{today}.jsonl"
    if not items_path.exists():
        print(f"No items file for today ({items_path}). Run inbox_scan.py first.")
        return 1
    records = [json.loads(l) for l in items_path.read_text().splitlines() if l.strip()]
    cards = build_inbox_cards(records)

    preview = STATE / f"decision_preview-{today}.jsonl"
    preview.write_text("\n".join(json.dumps(c) for c in cards) + ("\n" if cards else ""))

    indiv = [c for c in cards if c["autonomy_class"] != "inbox_archive_batch"]
    batch = [c for c in cards if c["autonomy_class"] == "inbox_archive_batch"]
    print(f"PREVIEW ONLY — wrote {len(cards)} cards → {preview}")
    print(f"  {len(indiv)} individual (scam/reply/action) + {len(batch)} batch-archive card")
    print("  NOT injected into decisions_pending.jsonl (Phase 1 wires this into aggregate.py).")
    for c in sorted(indiv, key=lambda c: -c["priority"])[:8]:
        print(f"    p{c['priority']} [{c['autonomy_class']}] {c['context_one_line'][:70]}")
    if batch:
        print(f"    p{batch[0]['priority']} [inbox_archive_batch] {batch[0]['context_one_line'][:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
