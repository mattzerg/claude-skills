#!/usr/bin/env python3
"""dq_lib.py — shared helpers for the zpub -> decision-queue forcing-function tools.

Used by gate_age_scan.py, signoff_sheet_gen.py, portfolio_verdicts.py.

Conventions (must stay in lockstep with the decision-queue skill):
  - Intake file:   ~/.claude/state/decisions_pending.jsonl  (append-only from here;
                    aggregate.py owns full rewrites)
  - Decision log:  ~/.claude/state/decisions_log.jsonl      (read-only here; an id
                    present in the log counts as "decided")
  - Record schema: mirrors DecisionItem in decision-queue/tools/aggregate.py:
      {id, source, entity_path, entity_id, age_days, age_human, autonomy_class,
       autonomy_verdict, verdict_source, why, context_one_line, choices,
       suggested_default, deadline, priority, raw}
  - NEVER write MattZerg/Tasks/decisions_pending.md (generator-owned).

Age basis ("most honest" choice, documented):
  wait_age = max(days_past_publish_target, days_since_last_touch)
  where last_touch = the MOST RECENT of frontmatter `updated_at` and file mtime.
  Rationale: `updated_at` alone overstates staleness when a file was edited
  without bumping frontmatter; mtime alone understates it for items that are
  weeks past their publish_target but got an incidental edit (e.g. Zergboard
  pSEO: mtime 2d, target 22d overdue -> honest wait is 22d). Taking the max of
  "overdue" and "untouched" is the least gameable measure of how long the item
  has actually been waiting on a human.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, date, timedelta, timezone
from pathlib import Path

VAULT = Path.home() / "Obsidian/Zerg"  # post-migration live vault root (contains MattZerg/)
META_DIR = VAULT / "MattZerg/Projects/Zerg-Production/Growth/publishing/_meta"
INDEX_JSON = META_DIR / "index.json"
GATES_JSON = META_DIR / "gates.json"
TASKS_DIR = VAULT / "MattZerg/Tasks"
DECISIONS_MD = TASKS_DIR / "decisions_pending.md"   # READ-ONLY, generator-owned

STATE_DIR = Path(os.path.expanduser("~/.claude/state"))
PENDING_JSONL = STATE_DIR / "decisions_pending.jsonl"
LOG_JSONL = STATE_DIR / "decisions_log.jsonl"

PENDING_GATE_VALUES = ("pending", "needed", "blocked", "failed")
TERMINAL_STATUSES = ("published", "killed", "archived", "triaged", "done")

# Pending-gate precedence for picking the ONE gate a record is keyed on.
GATE_PRECEDENCE = [
    "signoff", "pr_gate", "client_signoff", "send_gate", "launch_announcement",
    "fakeidan", "fakematt_copyedit", "fakematt_feedback", "fakematt_email",
    "imagery_quality", "prod_deployed", "ledger_clean", "date_confirmed",
]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def today() -> date:
    return utcnow().date()


def parse_dt(s):
    """Parse iso datetime/date strings (tolerant). Returns aware datetime or None."""
    if s is None or s == "":
        return None
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
    s = str(s).strip().replace("Z", "+00:00")
    for cand in (s, s + "T00:00:00+00:00"):
        try:
            d = datetime.fromisoformat(cand)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def age_human(d: float) -> str:
    """Same rendering as decision-queue aggregate.py."""
    if d < 1:
        return "%dh" % int(d * 24)
    if d < 14:
        return "%dd" % int(d)
    return "%dw" % int(d / 7)


def iso_week(d: date = None) -> str:
    d = d or today()
    y, w, _ = d.isocalendar()
    return "%d-W%02d" % (y, w)


# ---------- intake jsonl I/O ----------

def load_jsonl(path: Path):
    items = []
    if not path.exists():
        return items
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return items


def pending_ids() -> set:
    return {r.get("id") for r in load_jsonl(PENDING_JSONL) if r.get("id")}


def decided_ids() -> set:
    return {r.get("id") for r in load_jsonl(LOG_JSONL) if r.get("id")}


def append_records(records, dry_run: bool) -> int:
    """Append records to the intake jsonl. Returns count written."""
    if dry_run or not records:
        return 0
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with PENDING_JSONL.open("a") as fh:
        for rec in records:
            fh.write(json.dumps(rec, default=str) + "\n")
    return len(records)


# ---------- zpub index ----------

def load_index_entries():
    if not INDEX_JSON.exists():
        raise FileNotFoundError("zpub index not found: %s" % INDEX_JSON)
    data = json.loads(INDEX_JSON.read_text())
    entries = data.get("entries", data if isinstance(data, list) else [])
    return [e for e in entries if isinstance(e, dict)]


def pending_gates(entry) -> list:
    gates = entry.get("gates") or {}
    pend = [g for g, v in gates.items()
            if str(v).lower() in PENDING_GATE_VALUES]
    # date_confirmed pseudo-gate: a publish_target exists but Matt has not
    # confirmed the date. Lowest precedence; only meaningful with a target.
    if entry.get("publish_target") and not entry.get("date_confirmed"):
        if "date_confirmed" not in pend:
            pend.append("date_confirmed")
    return pend


def primary_gate(pend: list) -> str:
    for g in GATE_PRECEDENCE:
        if g in pend:
            return g
    return pend[0] if pend else ""


def entry_wait_age(entry):
    """Return (age_days_float, basis_str). See module docstring for rationale."""
    now = utcnow()
    candidates = []  # (age_days, basis)

    tgt = parse_dt(entry.get("publish_target"))
    overdue = None
    if tgt is not None:
        overdue = (now - tgt).total_seconds() / 86400.0
        if overdue > 0:
            candidates.append((overdue, "days past publish_target %s"
                               % tgt.date().isoformat()))

    touches = []
    upd = parse_dt(entry.get("updated_at"))
    if upd is not None:
        touches.append((now - upd).total_seconds() / 86400.0)
    p = entry.get("_path")
    if p and Path(p).exists():
        mt = datetime.fromtimestamp(Path(p).stat().st_mtime, tz=timezone.utc)
        touches.append((now - mt).total_seconds() / 86400.0)
    if touches:
        last_touch = min(touches)  # most recent of updated_at / mtime
        candidates.append((last_touch, "days since last touch (updated_at/mtime)"))

    if not candidates:
        return 0.0, "no timestamps available"
    return max(candidates)


# ---------- recommendation heuristics (from signoff-sheet-2026-06-11.md) ----------

def recommend(entry, age_days: float):
    """Derive (verdict, rationale, revisit_date|None) for one zpub entry.

    verdict in {"ship", "hold"} for zpub entries — archive is always offered as
    an OPTION but never recommended as the default for real content (the
    06-11 sheet only killed duplicate-tracker noise, never content). Deletion
    is never an option anywhere.
    """
    t = today()
    typ = (entry.get("type") or "").lower()
    status = (entry.get("status") or "").lower()
    blockers = entry.get("blockers") or []
    pend = pending_gates(entry)
    tgt_dt = parse_dt(entry.get("publish_target"))
    tgt = tgt_dt.date() if tgt_dt else None

    if "pr_gate" in pend:
        revisit = t + timedelta(days=3)
        return ("hold", "pr_gate hasn't passed yet — decide after the gate "
                "result lands", revisit)

    if tgt and tgt <= t:
        overdue = (t - tgt).days
        if overdue > 21 and typ == "blog":
            return ("ship", "%dd past target — research/commentary ages fast; "
                    "sign and publish this week or archive on staleness"
                    % overdue, None)
        if blockers:
            return ("ship", "%dd past target with %d blocker(s) — sign off, "
                    "name a real date this week and clear the blockers, or "
                    "downstream keeps slipping" % (overdue, len(blockers)), None)
        return ("ship", "%dd past target with no blockers — only the gate is "
                "missing; publish" % overdue, None)

    if tgt:
        days_out = (tgt - t).days
        if typ == "launch" or blockers:
            revisit = max(t + timedelta(days=1), tgt - timedelta(days=7))
            return ("hold", "launch %dd out%s — decision isn't due yet; "
                    "revisit one week pre-target, then commit to the date or "
                    "archive (no silent drift)"
                    % (days_out,
                       ", %d blocker(s)" % len(blockers) if blockers else ""),
                    revisit)
        if days_out <= 14:
            return ("ship", "on schedule, %dd out, no blockers — signing now "
                    "is what keeps the date" % days_out, None)
        revisit = tgt - timedelta(days=7)
        return ("hold", "%dd out — nothing to decide today; revisit one week "
                "pre-target" % days_out, revisit)

    # no target at all
    if status == "ideating":
        revisit = t + timedelta(days=14)
        return ("hold", "idea-stage with no publish target — gates are "
                "meaningless until a date exists; assign a target or archive "
                "at revisit", revisit)
    revisit = t + timedelta(days=7)
    return ("hold", "no publish target — signoff is meaningless without a "
            "date; assign a publish target or archive at revisit", revisit)
