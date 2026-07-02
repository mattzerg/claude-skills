#!/usr/bin/env python3
"""
budget — the real FAL session-spend gate for ambient-reel (the referenced
`fal_budget.py` does not exist; this replaces it).

Responsibilities:
  * Detect whether FAL generation is even possible (API key present). No key
    → "locked" → the orchestrator must STOP before spending.
  * Estimate per-clip cost from model + duration.
  * Enforce a hard per-run session cap via an append-only JSONL ledger.

It cannot query a live FAL balance (no such endpoint in fal-video-skill), so
"locked" means "no key configured"; an exhausted-balance error surfaces at
generation time and should be recorded via `record(... status="error")`.

CLI:
    budget.py probe                       # lock state + cap + spent this run
    budget.py estimate --model luma -d 5  # dollar estimate for one clip
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
# Unified ledger (2026-07-02): shared with scifi-reels _pipeline/fal_budget.py so
# every FAL touch from any pipeline lands in one append-only file. Override: FAL_LEDGER.
# (Historical rows from the old work/fal_ledger.jsonl were migrated in.)
LEDGER = Path(os.environ.get("FAL_LEDGER", "~/.config/zerg/fal_ledger.jsonl")).expanduser()

# Per-second USD estimates (conservative). Unknown models default high.
PRICE_PER_SEC = {
    "luma": 0.03,
    "minimax": 0.02,
    "minimax-t2v": 0.02,
    "hunyuan": 0.01,
    "kling": 0.05,
    "kling-t2v": 0.05,
    "kling-pro": 0.10,
    "kling-pro-t2v": 0.10,
    "kling-o3": 0.06,
    "kling-o3-t2v": 0.06,
    "veo": 0.50,
    "veo-t2v": 0.50,
    "sora": 0.50,
}
DEFAULT_PRICE_PER_SEC = 0.10

# Default hard ceiling for a single reel run. FAL_SESSION_CAP is the canonical
# env var (shared with fal_budget.py); AMBIENT_FAL_CAP kept as legacy fallback.
DEFAULT_SESSION_CAP = float(
    os.environ.get("FAL_SESSION_CAP") or os.environ.get("AMBIENT_FAL_CAP") or "2.50"
)


def estimate(model: str, duration_s: float) -> float:
    return round(PRICE_PER_SEC.get(model, DEFAULT_PRICE_PER_SEC) * float(duration_s), 4)


def fal_key_present() -> bool:
    if os.environ.get("FAL_KEY") or os.environ.get("FAL_API_KEY"):
        return True
    cfg = SKILL_DIR.parent / "fal-video-skill" / "config.json"
    if cfg.exists():
        try:
            data = json.loads(cfg.read_text())
            return bool(data.get("api_key"))
        except Exception:
            return False
    return False


def is_locked() -> bool:
    """FAL is 'locked' for our purposes when no API key is configured."""
    return not fal_key_present()


def _run_id() -> str:
    # Date.now() is unavailable in workflow scripts but this is a normal CLI;
    # time.time() is fine here.
    return f"run-{int(time.time())}"


def spent_in_run(run_id: str) -> float:
    if not LEDGER.exists():
        return 0.0
    total = 0.0
    for line in LEDGER.read_text().splitlines():
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("run_id") == run_id and e.get("status") == "ok":
            total += float(e.get("cost", 0))
    return round(total, 4)


def record(run_id: str, model: str, duration_s: float, status: str = "ok", note: str = "") -> dict:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    cost = estimate(model, duration_s) if status == "ok" else 0.0
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "run_id": run_id,
        "model": model,
        "duration_s": duration_s,
        "cost": cost,
        "est_cost": cost,      # cross-reader compat with fal_budget.summary
        "source": "ambient",
        "status": status,
        "note": note,
    }
    with LEDGER.open("a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


class Budget:
    """Per-run spend guard. Call check() before each paid generation."""

    def __init__(self, cap: float = DEFAULT_SESSION_CAP, run_id: str | None = None):
        self.cap = float(cap)
        self.run_id = run_id or _run_id()

    @property
    def spent(self) -> float:
        return spent_in_run(self.run_id)

    @property
    def remaining(self) -> float:
        return round(self.cap - self.spent, 4)

    def can_spend(self, model: str, duration_s: float) -> bool:
        return estimate(model, duration_s) <= self.remaining + 1e-9

    def commit(self, model: str, duration_s: float, note: str = "") -> dict:
        if not self.can_spend(model, duration_s):
            raise RuntimeError(
                f"session cap ${self.cap:.2f} would be exceeded "
                f"(spent ${self.spent:.2f}, next ${estimate(model, duration_s):.2f})"
            )
        return record(self.run_id, model, duration_s, status="ok", note=note)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("probe", help="show lock state, cap, spent")
    pe = sub.add_parser("estimate", help="estimate one clip's cost")
    pe.add_argument("--model", default="luma")
    pe.add_argument("-d", "--duration", type=float, default=5)
    args = ap.parse_args()

    if args.cmd == "probe":
        print(json.dumps({
            "fal_locked": is_locked(),
            "fal_key_present": fal_key_present(),
            "session_cap_usd": DEFAULT_SESSION_CAP,
            "ledger": str(LEDGER),
            "note": "locked == no FAL API key configured; top up + configure key to unlock",
        }, indent=2))
        return 0
    if args.cmd == "estimate":
        print(json.dumps({
            "model": args.model,
            "duration_s": args.duration,
            "usd": estimate(args.model, args.duration),
        }, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
