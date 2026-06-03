"""Feedback-driven ranking penalties for aitr.

Reads `wrong-model-picked` corrections from llm-feedback's JSON mirror, joins
them to the original routing decisions via `aitr_decision_id`, and produces a
penalties map the ranker subtracts from composite scores.

Penalty shape:
  key:   (caller, task_kind, model_id)
  value: negative float, bounded

Rules:
  - Each correction contributes -0.10 to the decision's exact (caller, task_kind, model).
  - Penalties decay linearly to zero over 60 days from the correction date.
  - Total penalty per key is capped at -0.30 (so 3+ corrections saturate).
  - Corrections without a resolvable decision_id are skipped (no global penalties —
    too blunt).

Pure functions take explicit paths + `now` so tests don't touch the real ledger.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

DEFAULT_DECISIONS_LOG = Path.home() / ".local" / "state" / "zerg" / "aitr" / "decisions.log"
DEFAULT_FEEDBACK_MIRROR_DIRS = [
    Path("/Users/mattheweisner/Library/Mobile Documents/iCloud~md~obsidian/Documents/Zerg/MattZerg/.llm-feedback"),
    Path.home() / ".zerg-vault-mirror" / "MattZerg" / ".llm-feedback",
]

PENALTY_PER_CORRECTION = -0.10
PENALTY_CAP = -0.30
DECAY_DAYS = 60.0

PenaltyKey = Tuple[str, str, str]  # (caller, task_kind, model_id)


def _parse_ts(value: str) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def load_decisions(decisions_log: Path) -> Dict[str, dict]:
    """Index decisions.log by decision_id. Malformed lines skipped."""
    out: Dict[str, dict] = {}
    if not decisions_log.exists():
        return out
    with decisions_log.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            did = rec.get("decision_id")
            if did:
                out[did] = rec
    return out


def load_wrong_model_feedback(feedback_dirs: list[Path]) -> list[dict]:
    """Read all llm-feedback JSON mirror entries with bucket=wrong-model-picked."""
    entries: list[dict] = []
    for d in feedback_dirs:
        if not d.is_dir():
            continue
        for path in sorted(d.glob("*.json")):
            try:
                rec = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if rec.get("bucket") == "wrong-model-picked":
                entries.append(rec)
        break  # first existing dir wins (iCloud primary, mirror fallback)
    return entries


def compute_penalties(
    decisions: Dict[str, dict],
    feedback_entries: list[dict],
    *,
    now: Optional[datetime] = None,
) -> Dict[PenaltyKey, float]:
    """Join corrections to decisions and compute decayed, capped penalties."""
    now = now or datetime.now(timezone.utc)
    penalties: Dict[PenaltyKey, float] = {}

    for entry in feedback_entries:
        decision_id = entry.get("aitr_decision_id")
        if not decision_id:
            continue
        decision = decisions.get(decision_id)
        if not decision:
            continue

        when = _parse_ts(entry.get("when", ""))
        if when is None:
            continue
        age_days = (now - when).total_seconds() / 86400.0
        if age_days < 0:
            age_days = 0.0
        if age_days >= DECAY_DAYS:
            continue

        decay_factor = 1.0 - (age_days / DECAY_DAYS)
        contribution = PENALTY_PER_CORRECTION * decay_factor

        signal = decision.get("signal") or {}
        key: PenaltyKey = (
            decision.get("caller") or signal.get("caller") or "",
            signal.get("task_kind") or "",
            decision.get("model") or "",
        )
        new_total = penalties.get(key, 0.0) + contribution
        penalties[key] = max(new_total, PENALTY_CAP)

    return penalties


def load_penalties(
    *,
    decisions_log: Optional[Path] = None,
    feedback_dirs: Optional[list[Path]] = None,
    now: Optional[datetime] = None,
) -> Dict[PenaltyKey, float]:
    """Convenience wrapper with default paths. Never raises — returns {} on any failure."""
    try:
        decisions = load_decisions(decisions_log or DEFAULT_DECISIONS_LOG)
        if not decisions:
            return {}
        feedback = load_wrong_model_feedback(feedback_dirs or DEFAULT_FEEDBACK_MIRROR_DIRS)
        if not feedback:
            return {}
        return compute_penalties(decisions, feedback, now=now)
    except Exception as exc:  # noqa: BLE001 — penalties are an enhancement, never fatal
        print(f"aitr: penalty load failed ({exc}); ranking without feedback penalties", file=sys.stderr)
        return {}


def penalty_for(
    penalties: Dict[PenaltyKey, float],
    caller: str,
    task_kind: str,
    model_id: str,
) -> float:
    """Look up the penalty for a candidate. Exact key match only."""
    return penalties.get((caller, task_kind, model_id), 0.0)
