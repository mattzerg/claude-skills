"""Append-only usage telemetry for the idea-backlog skill.

Every script that mutates state or runs a search calls `log_event(...)`.
Lines land in `_workdir/usage.jsonl`. Read by `metrics.py` for the weekly
digest and any ad-hoc audit.

Schema:
  {"ts": "<UTC iso>", "event": "<verb>", "source": "<script>", ...kwargs}

Common events:
  capture                ← new idea written
  recall                 ← search performed (incl. hits count)
  triage                 ← keep/merge/kill/defer/to-task action
  promote                ← raw → active or category move
  kill                   ← archived
  touch                  ← last_touched bumped
  demote_from_task       ← Tasks/inbox.md row → idea
  promote_to_task        ← idea → Tasks/inbox.md row
  extract_run            ← seed sweep stage 1 finished
  dedupe_run             ← stage 2 finished
  write_inbox_run        ← stage 3 finished
  rebuild_index          ← index.json regenerated
  weekly_digest          ← cron message posted
  auto_suggest_fire      ← Claude surfaced ideas in a session (hand-logged via log_suggest.py)

Telemetry is best-effort — never raise. If the file is unwriteable, the
calling script still completes.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

USAGE_PATH = Path.home() / ".claude" / "skills" / "idea-backlog" / "_workdir" / "usage.jsonl"


def log_event(event: str, *, source: str = "unknown", **kwargs: Any) -> None:
    """Append one event to usage.jsonl. Silent on any failure."""
    try:
        USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        rec = {
            "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "event": event,
            "source": source,
            **kwargs,
        }
        with USAGE_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def read_events() -> list[dict[str, Any]]:
    """Read all events. Returns [] on missing file."""
    if not USAGE_PATH.exists():
        return []
    out: list[dict[str, Any]] = []
    for line in USAGE_PATH.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out
