#!/usr/bin/env python3
"""portfolio_verdicts.py — weekly keep/park/archive verdicts for projects.

Part 1 — project verdicts:
  Reads ~/.claude/workstreams/state.json. A parallel agent is adding a
  `projects` section with per-project health (advancing/parked/archived +
  RED/AMBER/GREEN). For each RED/AMBER project, emit ONE decision-queue
  record into ~/.claude/state/decisions_pending.jsonl:
    - stable key: verdict:<project-id>:<iso-week>   (e.g. verdict:zergtube:2026-W24)
    - options: keep advancing / park until <date> / archive — NEVER delete
    - defaults: RED -> park until +28d; AMBER -> keep advancing (revisit weekly)
  If state.json has no `projects` section yet (parallel agent unfinished),
  exit 0 with "projects section not present yet" — the weekly wrapper guards
  on this.
  Idempotent: the iso-week key means at most one record per project per week;
  keys already pending or already decided (decisions_log.jsonl) are skipped.

Part 2 — repo archive proposals:
  Appends a "## Repo archive proposals" section to TODAY'S signoff sheet
  (highest -rN signoff-sheet-<today>*.md; created fresh if none exists).
  Candidates: zergtube, zergaudit, zerg-gg, airwallex_poc under ~/zerg.
  Each row is an archive-to-~/Backups recommendation for Matt to verdict —
  nothing is moved, archived, or deleted by this script. A candidate with
  recent git activity (commit within --active-days, default 7) or, for
  zergaudit, live vault-side zpub work, is NOT proposed; it is listed as
  active with a re-check date instead.
  Idempotent: skipped if the section marker already exists in the sheet.

Never touches MattZerg/Tasks/decisions_pending.md. Nothing auto-ships.

Usage:
  portfolio_verdicts.py [--dry-run] [--active-days N]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dq_lib as dq  # noqa: E402

STATE_JSON = Path.home() / ".claude/workstreams/state.json"
ZERG_DIR = Path.home() / "zerg"

# Candidate dormant repos (facts as of 2026-06-10; freshness re-checked live).
CANDIDATES = [
    {"name": "zergtube", "path": ZERG_DIR / "zergtube",
     "note": "~17GB; dormant"},
    {"name": "zergaudit", "path": ZERG_DIR / "zergaudit",
     "note": "~3MB; check vault-side Zergaudit work before archiving",
     "vault_check": "zergaudit"},
    {"name": "zerg-gg", "path": ZERG_DIR / "zerg-gg",
     "note": "~293MB; PR #1 open since May 17 — close or merge it first"},
    {"name": "airwallex_poc", "path": ZERG_DIR / "airwallex_poc",
     "note": "~548MB; idle since May 19"},
]

SECTION_MARKER = "## Repo archive proposals"


# ---------- part 1: project verdicts ----------

def iter_projects(projects):
    """Tolerate dict {id: obj} or list [{id/name, ...}] shapes."""
    if isinstance(projects, dict):
        for pid, obj in projects.items():
            if isinstance(obj, dict):
                yield pid, obj
    elif isinstance(projects, list):
        for obj in projects:
            if isinstance(obj, dict):
                pid = obj.get("id") or obj.get("name") or obj.get("slug")
                if pid:
                    yield str(pid), obj


def project_health(obj):
    for k in ("health", "rag", "rayg", "color", "status_color"):
        v = obj.get(k)
        if isinstance(v, str) and v.upper() in ("RED", "AMBER", "YELLOW", "GREEN"):
            return v.upper()
    return None


def project_state(obj):
    for k in ("state", "status", "mode"):
        v = obj.get(k)
        if isinstance(v, str) and v.lower() in ("advancing", "parked", "archived"):
            return v.lower()
    return None


def build_verdict_record(pid, obj):
    health = project_health(obj)
    state = project_state(obj) or "advancing"
    week = dq.iso_week()
    t = dq.today()
    park_date = (t + timedelta(days=28)).isoformat()
    park_choice = "park until %s" % park_date
    default = park_choice if health == "RED" else "keep advancing"
    why = ("Project health %s (%s) — weekly portfolio verdict: keep "
           "advancing, park, or archive. Never delete." % (health, state))
    context = ("Project %s is %s and %s — keep advancing, park until %s, "
               "or archive?" % (pid, health, state, park_date))
    return {
        "id": "verdict:%s:%s" % (pid, week),
        "source": "portfolio-verdicts",
        "entity_path": str(STATE_JSON),
        "entity_id": pid,
        "age_days": 0.0,
        "age_human": "0h",
        "autonomy_class": "portfolio_review",
        "autonomy_verdict": "needs_matt",
        "verdict_source": "portfolio_verdicts",
        "why": why,
        "context_one_line": context,
        "choices": ["keep advancing", park_choice, "archive", "details"],
        "suggested_default": default,
        "deadline": None,
        "priority": 75 if health == "RED" else 55,
        "raw": {"health": health, "state": state, "iso_week": week,
                "project": obj,
                "refs": {"project_id": pid, "state_json": str(STATE_JSON)}},
    }


def run_project_verdicts(dry_run):
    if not STATE_JSON.exists():
        print("projects section not present yet (no %s)" % STATE_JSON)
        return []
    try:
        state = json.loads(STATE_JSON.read_text())
    except Exception as e:
        print("ERROR: cannot parse %s: %s" % (STATE_JSON, e), file=sys.stderr)
        raise
    projects = state.get("projects")
    if not projects:
        print("projects section not present yet")
        return []
    existing = dq.pending_ids()
    decided = dq.decided_ids()
    records, skipped = [], 0
    for pid, obj in iter_projects(projects):
        if project_state(obj) == "archived":
            continue
        health = project_health(obj)
        if health not in ("RED", "AMBER"):
            continue
        rec = build_verdict_record(pid, obj)
        if rec["id"] in existing or rec["id"] in decided:
            skipped += 1
            continue
        records.append(rec)
    label = "DRY-RUN would emit" if dry_run else "emitting"
    print("%s %d project-verdict record(s); skipped %d already-pending/decided"
          % (label, len(records), skipped))
    for rec in records:
        print("  %-40s default=%s" % (rec["id"], rec["suggested_default"]))
    written = dq.append_records(records, dry_run=dry_run)
    if not dry_run and written:
        print("appended %d record(s) to %s" % (written, dq.PENDING_JSONL))
    return records


# ---------- part 2: repo archive proposals ----------

def last_commit_date(path: Path):
    try:
        out = subprocess.run(
            ["git", "-C", str(path), "log", "-1", "--format=%cI"],
            capture_output=True, text=True, timeout=15)
        if out.returncode == 0 and out.stdout.strip():
            return dq.parse_dt(out.stdout.strip())
    except Exception:
        pass
    return None


def vault_side_active(token: str) -> str:
    """Return a description of live vault-side zpub work matching token, or ''."""
    try:
        for e in dq.load_index_entries():
            eid = (e.get("id") or "").lower()
            if token in eid and (e.get("status") or "").lower() not in dq.TERMINAL_STATUSES:
                return "vault zpub `%s` is %s" % (e.get("id"), e.get("status"))
    except Exception:
        pass
    return ""


def build_repo_section(active_days: float) -> str:
    t = dq.today()
    recheck = (t + timedelta(days=14)).isoformat()
    lines = ["", SECTION_MARKER, "",
             "Proposals only — Matt verdicts each row; the script moves "
             "nothing. Archive = move to `~/Backups/`, never delete.", "",
             "| Repo | Last commit | Proposal |", "|---|---|---|"]
    now = datetime.now(timezone.utc)
    for c in CANDIDATES:
        path = c["path"]
        if not path.exists():
            lines.append("| `%s` | — | not found at `%s` — skip |"
                         % (c["name"], path))
            continue
        lc = last_commit_date(path)
        lc_str = lc.date().isoformat() if lc else "unknown"
        idle_days = (now - lc).days if lc else None
        active_bits = []
        if idle_days is not None and idle_days <= active_days:
            active_bits.append("commit %dd ago" % idle_days)
        if c.get("vault_check"):
            v = vault_side_active(c["vault_check"])
            if v:
                active_bits.append(v)
        if active_bits:
            lines.append("| `%s` | %s | **NOT proposed — active** (%s); "
                         "re-check %s |" % (c["name"], lc_str,
                                            "; ".join(active_bits), recheck))
        else:
            lines.append("| `%s` | %s | **ARCHIVE to ~/Backups/%s** — %s; "
                         "idle %sd |" % (c["name"], lc_str, c["name"],
                                         c["note"],
                                         idle_days if idle_days is not None
                                         else "?"))
    lines.append("")
    return "\n".join(lines)


def todays_sheet() -> Path:
    t = dq.today().isoformat()
    cands = sorted(dq.TASKS_DIR.glob("signoff-sheet-%s*.md" % t))
    if cands:
        return cands[-1]  # highest -rN sorts last
    return dq.TASKS_DIR / ("signoff-sheet-%s.md" % t)


def run_repo_section(dry_run, active_days):
    sheet = todays_sheet()
    section = build_repo_section(active_days)
    if sheet.exists() and SECTION_MARKER in sheet.read_text():
        print("repo-archive section already present in %s — skipping (idempotent)"
              % sheet.name)
        return
    if dry_run:
        print("DRY-RUN: would append repo-archive section to %s:" % sheet)
        print(section)
        return
    if sheet.exists():
        with sheet.open("a") as fh:
            fh.write(section)
    else:
        sheet.write_text("# Batch signoff sheet — %s\n%s"
                         % (dq.today().isoformat(), section))
    print("appended repo-archive section -> %s" % sheet)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Weekly portfolio verdicts (RED/AMBER projects -> "
                    "decision-queue) + repo archive proposals appended to "
                    "today's signoff sheet. Proposals only; nothing is "
                    "moved, deleted, shipped, or posted.")
    ap.add_argument("--dry-run", action="store_true",
                    help="print would-be records/section; write nothing")
    ap.add_argument("--active-days", type=float, default=7.0,
                    help="a repo with a commit within N days is NOT proposed "
                         "for archive (default: 7)")
    args = ap.parse_args()

    try:
        run_project_verdicts(args.dry_run)
    except Exception as e:
        print("ERROR in project verdicts: %s" % e, file=sys.stderr)
        return 1
    try:
        run_repo_section(args.dry_run, args.active_days)
    except Exception as e:
        print("ERROR in repo-archive section: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
