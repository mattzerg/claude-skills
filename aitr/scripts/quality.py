"""Realized-quality reputation for aitr.

The penalties module (penalties.py) is the SHARP negative signal: an explicit
`wrong-model-picked` correction says "this exact pick was wrong, avoid it."

This module is the SOFT two-sided signal: observed OUTCOMES of picks (a gate
passed, output was accepted, output got flagged) accumulate into a gentle
per-(caller, task_kind, model) reputation prior — "this model tends to do
well/poorly on this task." Smaller magnitude than penalties so it nudges
ranking rather than dominating it.

The two are kept separate and must not double-count: a `wrong-model-picked`
correction feeds penalties; an outcome observation feeds reputation. A producer
emits one or the other per observation, never both.

quality.log line shape (append-only JSONL, keyed to a routing decision_id):
  {decision_id, outcome, score?, source, note?, ts}
    outcome: "good" | "bad" | "mixed"   (or pass `score` in [0,1])
    source:  who observed it (pr-gate, fakeidan, matt, …)

Pure functions take explicit paths + `now` so tests don't touch the real log.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple

from penalties import DEFAULT_DECISIONS_LOG, load_decisions, _parse_ts  # reuse

DEFAULT_QUALITY_LOG = Path.home() / ".local" / "state" / "zerg" / "aitr" / "quality.log"

# Reputation is a gentle prior: each observation is worth ±0.05, decays over 90
# days, and the net per key is clamped to ±0.15 — well below the penalty cap
# (−0.30) so an explicit correction always outweighs soft reputation.
REP_PER_EVENT = 0.05
REP_CAP = 0.15
REP_DECAY_DAYS = 90.0

ReputationKey = Tuple[str, str, str]  # (caller, task_kind, model_id)
_OUTCOME_SIGN = {"good": 1.0, "bad": -1.0, "mixed": 0.0}


def outcome_to_signed(event: dict) -> float:
    """Map an event to a signed base in [-1, 1]. Explicit `score` (0..1) wins;
    else the `outcome` label. Unknown → 0 (no effect)."""
    score = event.get("score")
    if isinstance(score, (int, float)) and 0.0 <= float(score) <= 1.0:
        return 2.0 * float(score) - 1.0  # 0→-1, 0.5→0, 1→+1
    return _OUTCOME_SIGN.get(event.get("outcome", ""), 0.0)


def record_quality(
    decision_id: str,
    outcome: str,
    *,
    source: str,
    score: Optional[float] = None,
    note: Optional[str] = None,
    log_path: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> dict:
    """Append a realized-quality observation. Returns the written record."""
    log_path = log_path or DEFAULT_QUALITY_LOG
    now = now or datetime.now(timezone.utc)
    rec = {
        "decision_id": decision_id,
        "outcome": outcome,
        "source": source,
        "ts": now.isoformat(),
    }
    if score is not None:
        rec["score"] = score
    if note:
        rec["note"] = note
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
    except OSError as exc:
        print(f"aitr: failed to write quality log {log_path}: {exc}", file=sys.stderr)
    return rec


def load_quality_events(log_path: Optional[Path] = None) -> list[dict]:
    path = log_path or DEFAULT_QUALITY_LOG
    out: list[dict] = []
    if not path.exists():
        return out
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
    except (OSError, json.JSONDecodeError):
        pass
    return out


def compute_reputation(
    decisions: Dict[str, dict],
    events: list[dict],
    *,
    now: Optional[datetime] = None,
) -> Dict[ReputationKey, float]:
    """Aggregate observed outcomes into a decayed, clamped per-key reputation."""
    now = now or datetime.now(timezone.utc)
    rep: Dict[ReputationKey, float] = {}
    for event in events:
        did = event.get("decision_id")
        if not did:
            continue
        decision = decisions.get(did)
        if not decision:
            continue
        when = _parse_ts(event.get("ts", ""))
        if when is None:
            continue
        age_days = max((now - when).total_seconds() / 86400.0, 0.0)
        if age_days >= REP_DECAY_DAYS:
            continue
        decay = 1.0 - (age_days / REP_DECAY_DAYS)
        contribution = outcome_to_signed(event) * REP_PER_EVENT * decay

        signal = decision.get("signal") or {}
        key: ReputationKey = (
            decision.get("caller") or signal.get("caller") or "",
            signal.get("task_kind") or "",
            decision.get("model") or "",
        )
        total = rep.get(key, 0.0) + contribution
        rep[key] = max(-REP_CAP, min(REP_CAP, total))
    return rep


def load_reputation(
    *,
    decisions_log: Optional[Path] = None,
    quality_log: Optional[Path] = None,
    now: Optional[datetime] = None,
) -> Dict[ReputationKey, float]:
    """Convenience wrapper with default paths. Never raises — returns {} on failure."""
    try:
        decisions = load_decisions(decisions_log or DEFAULT_DECISIONS_LOG)
        if not decisions:
            return {}
        events = load_quality_events(quality_log)
        if not events:
            return {}
        return compute_reputation(decisions, events, now=now)
    except Exception as exc:  # noqa: BLE001 — reputation is an enhancement, never fatal
        print(f"aitr: reputation load failed ({exc}); ranking without it", file=sys.stderr)
        return {}


def reputation_for(rep: Dict[ReputationKey, float], caller: str, task_kind: str, model_id: str) -> float:
    return rep.get((caller, task_kind, model_id), 0.0)
