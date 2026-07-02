#!/usr/bin/python3
"""render_rich: Rich ASCII morning-brief dashboard for in-session Claude pulls.

NOTE: shebang is pinned to /usr/bin/python3 (macOS system Python 3.9) because
that interpreter is the one with `requests` installed (used transitively via
digest.py). Homebrew /opt/homebrew/bin/python3 (Python 3.14) does NOT have
requests and is blocked by PEP 668 from `pip install`. Always invoke as:
  ./render_rich.py                     (uses pinned shebang)
  /usr/bin/python3 render_rich.py      (explicit, also fine)
Don't use bare `python3 …` — that picks Homebrew on this machine and crashes.

Different surface from the 7am Slack cron (which uses morning_brief.py +
slack_format.compose with a 15-line ceiling). This script renders the full
8-zone box for terminal/conversational read.

Reuses morning_brief.py's data builders (no duplicate data layer). Adds:
  - 🤖 AUTONOMOUS — I CAN PUSH NOW (heuristic)
  - 📊 Yesterday's 🎯 acted? — from action_led_targets/targets.jsonl + review.py
  - 🚀 Yesterday's wins — gh PRs merged + standup activity
  - 🕘 Focus block math — gap analysis around today's meetings
  - 🔴 BLOCKED ON YOU — top inbox To Do rows (excl. the 🎯)

Run modes:
  render_rich.py                 — print rich dashboard to stdout
  render_rich.py --json          — emit structured data (for piping)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import re
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

# Reuse morning_brief.py's data layer
sys.path.insert(0, str(Path.home() / ".claude" / "fakematt-today"))
import digest  # type: ignore  # noqa: E402
import morning_brief as mb  # type: ignore  # noqa: E402
import promise_state  # type: ignore  # noqa: E402

# Reuse review.py classifier for yesterday-lead status
sys.path.insert(0, str(Path.home() / ".claude" / "action_led_targets"))
try:
    import review as ledger_review  # type: ignore
except ImportError:
    ledger_review = None  # type: ignore

PT = ZoneInfo("America/Los_Angeles")
sys.path.insert(0, str(Path.home() / ".config" / "zerg" / "lib"))
from vault_path import zerg_root  # canonical vault resolver (was hardcoded iCloud — now a near-empty shell)
VAULT = zerg_root()
VAULT_MIRROR = VAULT  # writeback split retired (2026-06-30); vault is now ~/Obsidian (non-TCC, direct)
INBOX_PATH = VAULT / "MattZerg/Tasks/inbox.md"
TARGETS_LOG = Path.home() / ".claude/action_led_targets/targets.jsonl"
PR_TABLE_SCRIPT = Path.home() / ".claude/skills/pr-table/run.py"


def _freshest_vault_path(relative: str) -> Path:
    """Return whichever of (VAULT, VAULT_MIRROR) has the more-recently-modified
    copy of the given relative path. The mirror exists because launchd-run
    regenerators can't write to the iCloud-synced VAULT (macOS TCC permission
    denial); they write to ~/.zerg-vault-writeback/ instead. Reading the
    fresher of the two keeps the brief from showing stale state when only the
    mirror has been updated. Logs to stderr when the mirror wins so Matt can
    see the iCloud TCC issue needs fixing."""
    primary = VAULT / relative
    mirror = VAULT_MIRROR / relative
    p_mtime = primary.stat().st_mtime if primary.exists() else 0.0
    m_mtime = mirror.stat().st_mtime if mirror.exists() else 0.0
    if m_mtime > p_mtime and mirror.exists():
        sys.stderr.write(
            f"[morning-brief] using vault mirror for {relative} "
            f"(iCloud copy is {int(m_mtime - p_mtime)}s stale; "
            f"launchd-write to iCloud is TCC-blocked)\n"
        )
        return mirror
    return primary


GTM_INDEX = _freshest_vault_path("MattZerg/Projects/Zerg-Production/Growth/_meta/index.json")

BOX_WIDTH = 78  # outer width, inclusive of side rails
INNER = BOX_WIDTH - 4  # content width inside `║  …  ║`

logger = logging.getLogger("morning-brief.rich")


# ────────────────────────────── data layer ──────────────────────────────

def pull_inbox_todo_rows(now: dt.datetime, limit: int = 12) -> list[dict]:
    """Parse `MattZerg/Tasks/inbox.md` To Do table → top rows with date awareness."""
    if not INBOX_PATH.exists():
        return []
    text = INBOX_PATH.read_text(errors="replace")
    m = re.search(r"\n## To Do\s*\n(.+?)(?:\n## |\n---\n)", text, re.S)
    if not m:
        return []
    section = m.group(1)
    rows: list[dict] = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|---") or line.startswith("| #"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        num, item, domain, why = cells[0], cells[1], cells[2], cells[3]
        # Strip zb:tags + weekday-date prefix from item
        item_clean = re.sub(r"\s*\[zb:[A-Z]+-\d+\]\s*", " ", item).strip()
        item_clean = mb.WEEKDAY_PREFIX_RE.sub("", item_clean).strip()
        # Detect "today/overdue" priority
        today = now.date()
        due_date = None
        for txt in (item, why):
            for dm in mb.INBOX_DATE_RE.finditer(txt):
                try:
                    d = dt.date.fromisoformat(dm.group(1))
                    if d <= today:
                        due_date = d if (due_date is None or d > due_date) else due_date
                except ValueError:
                    continue
        rows.append({
            "num": num,
            "item": item_clean,
            "raw_item": item,
            "domain": domain,
            "why": why,
            "due_date": due_date,
        })
    # Sort: dated (most-recent date first) → undated (preserve file order)
    dated = sorted([r for r in rows if r["due_date"]], key=lambda r: r["due_date"], reverse=True)
    undated = [r for r in rows if not r["due_date"]]
    return (dated + undated)[:limit]


def pick_lead(now: dt.datetime, gcal_events: list, gate_lines: list[str]) -> dict:
    """Return the 🎯 TODAY lead row. Reuses morning_brief.read_inbox_priority +
    synthesize_top3, then strips the metadata tail for clean rendering."""
    opens = promise_state.open_promises()
    todays = mb.todays_meetings(gcal_events, now)
    inbox_pick = mb.read_inbox_priority(now)
    try:
        linear_issues = digest.fetch_linear_my_issues()
    except Exception:
        linear_issues = []
    top3 = mb.synthesize_top3(opens, linear_issues, todays, gate_lines, now)
    raw = inbox_pick or (top3[0] if top3 else None)
    if not raw:
        return {"action": "Open day — no urgent lead picked.", "source": "open"}
    headline = re.sub(r"\s*_\([^)]*\)_\s*$", "", raw).strip()
    return {"action": headline, "source": "inbox" if inbox_pick else "synthesized", "raw": raw}


def classify_blockers(rows: list[dict], lead_action: str, limit: int = 5) -> list[dict]:
    """Pick top 5 To Do rows to render as 🔴 BLOCKED ON YOU. Filters out:
      - the row the 🎯 TODAY lead already covers
      - rows starting with autonomous-pushable verbs (handled separately)
    """
    out: list[dict] = []
    lead_fp = " ".join(lead_action.lower().split())[:50]
    autonomous_verbs = ("run ", "resolve ", "rebase ", "draft ", "build ", "wire ", "ship ", "deploy ")
    for r in rows:
        item_fp = " ".join(r["item"].lower().split())[:50]
        if item_fp in lead_fp or lead_fp in item_fp:
            continue
        item_low = r["item"].lower()
        if item_low.startswith(autonomous_verbs):
            continue
        out.append(r)
        if len(out) >= limit:
            break
    return out


def autonomous_candidates(
    rows: list[dict],
    gate_lines: list[str],
    held_branches: list[dict],
    gtm: list[dict],
    lead: dict,
) -> list[dict]:
    """Pull rows that look autonomous-pushable + add heuristics from PR + GTM state."""
    out: list[dict] = []
    autonomous_verbs = (
        "run ", "resolve ", "rebase ", "draft ", "build ", "wire ", "deploy ",
        "audit ", "export ", "ship ", "test ",
    )
    lead_fp = " ".join(lead["action"].lower().split())[:50]
    for r in rows:
        item_low = r["item"].lower()
        if item_low.startswith(autonomous_verbs):
            item_fp = " ".join(item_low.split())[:50]
            if item_fp in lead_fp or lead_fp in item_fp:
                continue
            out.append({"text": r["item"][:90], "from": "inbox"})
    # If lead is "verify <post> is live", offer the verification command
    if "verify" in lead["action"].lower() and "post" in lead["action"].lower():
        out.insert(0, {"text": "Run `/zpub` to confirm queued post is live", "from": "heuristic"})
    # Held branches behind base → offer rebase
    for b in held_branches:
        if "behind" in b.get("blockers", ""):
            out.append({
                "text": f"Rebase `{b['branch']}` ({b.get('ahead_behind','')} behind base)",
                "from": "pr-state",
            })
    # Open GTM decisions with no draft → offer to draft options
    if gtm:
        first = gtm[0]
        out.append({
            "text": f"Draft options writeup for `{first['id']}`",
            "from": "gtm",
        })
    # Dedup (preserve order)
    seen: set[str] = set()
    dedup: list[dict] = []
    for a in out:
        key = a["text"][:40]
        if key in seen:
            continue
        seen.add(key)
        dedup.append(a)
    return dedup[:5]


def pull_pr_pipeline() -> dict:
    """Run pr-table → parse markdown into structured PR state."""
    if not PR_TABLE_SCRIPT.exists():
        return {"open": [], "held": [], "cap": "?", "merged_7d": 0, "closed_7d": 0}
    try:
        res = subprocess.run(
            ["python3", str(PR_TABLE_SCRIPT)],
            capture_output=True, text=True, timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError):
        return {"open": [], "held": [], "cap": "?", "merged_7d": 0, "closed_7d": 0}
    if res.returncode != 0:
        return {"open": [], "held": [], "cap": "?", "merged_7d": 0, "closed_7d": 0}
    text = res.stdout
    cap = "?"
    held_n = 0
    merged = 0
    closed = 0
    m = re.search(r"\*\*Open:\s*(\d+\s*/\s*\d+)\s*cap\*\*", text)
    if m:
        cap = m.group(1).replace(" ", "")
    m = re.search(r"\*\*Held:\s*(\d+)\*\*", text)
    if m:
        held_n = int(m.group(1))
    m = re.search(r"\*\*Merged \(7d\):\s*(\d+)\*\*", text)
    if m:
        merged = int(m.group(1))
    m = re.search(r"\*\*Closed \(7d\):\s*(\d+)\*\*", text)
    if m:
        closed = int(m.group(1))
    open_prs: list[dict] = []
    held: list[dict] = []
    # Open PRs table
    om = re.search(r"## Open PRs\n\n\|.+?\n(\|---.+?\n)((?:\|.+\n)+)", text)
    if om:
        for line in om.group(2).strip().splitlines():
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 6:
                open_prs.append({
                    "num": cells[0],
                    "title": cells[1],
                    "state": cells[2],
                    "reviews": cells[3],
                    "ci": cells[4],
                    "age": cells[5],
                })
    # Held local table
    hm = re.search(r"## Held local\n\n\|.+?\n(\|---.+?\n)((?:\|.+\n)+)", text)
    if hm:
        for line in hm.group(2).strip().splitlines():
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 7:
                held.append({
                    "branch": cells[0].strip("`"),
                    "surface": cells[1],
                    "ahead_behind": cells[2],
                    "last_commit": cells[3],
                    "preflight": cells[4],
                    "launch": cells[5],
                    "blockers": cells[6],
                })
    return {
        "open": open_prs, "held": held, "cap": cap,
        "merged_7d": merged, "closed_7d": closed, "held_n": held_n,
    }


DECISION_QUEUE_JSONL = Path.home() / ".claude/state/decisions_pending.jsonl"


def pull_decision_queue(now: dt.datetime, limit: int = 3) -> dict:
    """Read decision-queue (decisions_pending.jsonl) — top-N by priority desc.

    Returns {total, top, swipe_url}. If file missing or empty, total=0.
    """
    out = {"total": 0, "top": [], "swipe_url": "http://127.0.0.1:8788/swipe"}
    if not DECISION_QUEUE_JSONL.exists():
        return out
    items: list[dict] = []
    try:
        with DECISION_QUEUE_JSONL.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return out
    out["total"] = len(items)
    items.sort(key=lambda x: (-int(x.get("priority", 50) or 50),
                              -float(x.get("age_days", 0) or 0)))
    for it in items[:limit]:
        ctx = (it.get("context_one_line") or "")[:100]
        src = it.get("source", "?")
        age = it.get("age_human", "")
        cls = it.get("autonomy_class") or "—"
        out["top"].append({
            "id": it.get("id", ""),
            "context": ctx,
            "source": src,
            "age": age,
            "autonomy_class": cls,
            "priority": int(it.get("priority", 50) or 50),
            "deadline": it.get("deadline") or "",
        })
    return out


DECISION_SWIPE_URL = "http://127.0.0.1:8788/swipe"
DECISION_STALE_HOURS = 6  # regen cron runs every 15min; >6h stale ⇒ regen broke


def pull_pending_decisions(now: dt.datetime, limit: int = 3) -> dict:
    """Decision queue → morning-brief "Pending decisions" lane (Phase 9.1).

    Distinct from `pull_decision_queue` (priority-sorted): this surfaces the
    *oldest* unanswered decisions so the brief makes the write-only queue pay
    rent. Top-N by age (oldest first), each with a one-line description, age in
    days, and a runnable resolve command. Never raises — a missing, empty, or
    stale file degrades to a single status line.

    Resolve verbs (from decision-queue/SKILL.md):
      - swipe UI:   http://127.0.0.1:8788/swipe   (global, all items)
      - rapid-fire: rapid_fire.py [--class=<autonomy_class>]  (terminal)
      - slack card: slack_card.py digest

    Returns:
      {"available": bool, "status": str, "total": int,
       "swipe_url": str, "top": [{description, age_days, age_human,
                                   autonomy_class, source, resolve}]}
    """
    rapid = "~/.claude/skills/decision-queue/tools/rapid_fire.py"
    out = {
        "available": False,
        "status": "empty",
        "total": 0,
        "swipe_url": DECISION_SWIPE_URL,
        "top": [],
    }
    if not DECISION_QUEUE_JSONL.exists():
        out["status"] = "empty"  # never errors — file simply not built yet
        return out
    # Staleness: regen cron is every 15min. If the file is hours old the
    # aggregator is broken (com.zerg.decision-queue-regen YELLOW) — say so
    # rather than silently showing a frozen queue.
    try:
        mtime = DECISION_QUEUE_JSONL.stat().st_mtime
        age_h = (now.timestamp() - mtime) / 3600.0
    except OSError:
        age_h = 0.0
    items: list[dict] = []
    try:
        with DECISION_QUEUE_JSONL.open() as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    items.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        out["status"] = "empty"
        return out
    out["total"] = len(items)
    if not items:
        out["status"] = "empty"
        return out
    out["available"] = True
    if age_h > DECISION_STALE_HOURS:
        out["status"] = f"stale ({int(age_h)}h — check decision-queue-regen)"
    else:
        out["status"] = "fresh"
    # Oldest first.
    items.sort(key=lambda x: -float(x.get("age_days", 0) or 0))
    for it in items[:limit]:
        desc = (it.get("context_one_line") or it.get("id") or "")[:90]
        cls = it.get("autonomy_class") or ""
        try:
            age_d = float(it.get("age_days", 0) or 0)
        except (TypeError, ValueError):
            age_d = 0.0
        # Per-item resolve command: rapid-fire filtered to this item's class
        # is the most targeted runnable verb (there's no id-level CLI — the
        # queue is walked interactively). Swipe URL is the global fallback.
        if cls:
            resolve = f"{rapid} --class={cls}"
        else:
            resolve = rapid
        out["top"].append({
            "description": desc,
            "age_days": age_d,
            "age_human": it.get("age_human", ""),
            "autonomy_class": cls or "—",
            "source": it.get("source", "?"),
            "resolve": resolve,
        })
    return out


def pull_gtm_decisions(now: dt.datetime, limit: int = 3) -> list[dict]:
    """Open GTM decisions sorted by urgency, with `due Nd · M opts → gtm decide <id>`."""
    if not GTM_INDEX.exists():
        return []
    try:
        idx = json.loads(GTM_INDEX.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    today = now.date()
    decs: list[dict] = []
    for e in idx.get("entities", []):
        if e.get("type") != "decision":
            continue
        if e.get("status") not in ("open", "deferred"):
            continue
        decs.append(e)

    def _urgency(e: dict) -> tuple:
        try:
            dl = dt.date.fromisoformat(e.get("deadline") or "")
            return (0, (dl - today).days)
        except (ValueError, TypeError):
            return (1, 0)

    decs.sort(key=_urgency)
    out: list[dict] = []
    decisions_dir = VAULT / "MattZerg/Projects/Zerg-Production/Growth/decisions"
    for d in decs[:limit]:
        deadline = d.get("deadline") or ""
        urgency = ""
        emoji = "⚪"
        if deadline:
            try:
                dl = dt.date.fromisoformat(deadline)
                delta = (dl - today).days
                if delta < 0:
                    emoji, urgency = "🔴", f"OVERDUE {-delta}d (was due {deadline})"
                elif delta == 0:
                    emoji, urgency = "🔴", f"DUE TODAY ({deadline})"
                elif delta <= 7:
                    emoji, urgency = "🟠", f"due {delta}d ({deadline})"
                elif delta <= 21:
                    emoji, urgency = "🟡", f"due {delta}d ({deadline})"
                else:
                    emoji, urgency = "🟢", f"due {delta}d ({deadline})"
            except ValueError:
                pass
        n_opts = sum(1 for o in (d.get("options") or []) if isinstance(o, dict))
        # Pull last_touch from the decision file frontmatter for provenance
        last_touch = ""
        dec_id = d.get("id", "")
        if dec_id:
            dec_file = decisions_dir / f"{dec_id}.md"
            if dec_file.exists():
                try:
                    text = dec_file.read_text(errors="replace")
                    m = re.search(r"^last_touch:\s*(\S+)", text, re.M)
                    if m:
                        last_touch = m.group(1)
                except OSError:
                    pass
        out.append({
            "emoji": emoji,
            "title": (d.get("title") or dec_id or "")[:80],
            "id": dec_id,
            "urgency": urgency,
            "n_opts": n_opts,
            "last_touch": last_touch,
            "source_file": f"decisions/{dec_id}.md" if dec_id else "",
        })
    return out


def pull_yesterday_lead(now: dt.datetime) -> Optional[dict]:
    """Find yesterday's morning_brief 🎯 from targets.jsonl + classify it."""
    if not TARGETS_LOG.exists() or ledger_review is None:
        return None
    targets = ledger_review.load_targets()
    yesterday = (now - dt.timedelta(days=1)).date().isoformat()
    rows = [
        t for t in targets
        if t.get("surface") == "morning_brief" and (t.get("ts") or "").startswith(yesterday)
    ]
    if not rows:
        # Fall back to most recent morning_brief target within last 4 days
        rows = [t for t in targets if t.get("surface") == "morning_brief"]
        if not rows:
            return None
        rows.sort(key=lambda r: r.get("ts", ""), reverse=True)
        ts = rows[0].get("ts", "")
        # Only use if within last 4 days
        try:
            row_dt = dt.datetime.fromisoformat(ts)
            if (now - row_dt).days > 4:
                return None
        except (ValueError, TypeError):
            return None
        target = rows[0]
    else:
        target = rows[0]
    try:
        status = ledger_review.classify_target(target, now)
    except Exception:
        status = "UNKNOWN"
    raw_action = target.get("action") or ""
    # Strip "_(inbox · domain, Nd overdue)_" metadata tail
    clean_action = re.sub(r"\s*_\([^)]*\)_\s*$", "", raw_action).strip()
    return {
        "action": clean_action[:70],
        "status": status,
        "ts": target.get("ts", ""),
    }


def pull_yesterday_wins(now: dt.datetime, pr_data: Optional[dict] = None) -> dict:
    """PRs merged in last ~30h (from pr-table data) + Matt's last standup line."""
    wins: dict = {"merged_prs": [], "standup": None}
    # Parse merged-7d rows from pr-table output if provided, else re-query
    if pr_data is None:
        pr_data = pull_pr_pipeline()
    # We need the raw markdown to read the "Merged in past 7 days" age column,
    # since pull_pr_pipeline didn't extract it. Quick re-fetch for the age info.
    try:
        res = subprocess.run(
            ["python3", str(PR_TABLE_SCRIPT)],
            capture_output=True, text=True, timeout=20,
        )
    except (subprocess.TimeoutExpired, OSError):
        res = None
    if res and res.returncode == 0:
        text = res.stdout
        m = re.search(r"## Merged in past 7 days\n\n\|.+?\n\|---.+?\n((?:\|.+\n)+)", text)
        if m:
            for line in m.group(1).strip().splitlines():
                cells = [c.strip() for c in line.strip("|").split("|")]
                if len(cells) < 4:
                    continue
                num, title, age = cells[0], cells[1], cells[2]
                # "13h ago" / "1d ago" / "2d ago" — keep ≤30h
                age_match = re.match(r"(\d+)([hd]) ago", age)
                if not age_match:
                    continue
                n, unit = int(age_match.group(1)), age_match.group(2)
                hours = n if unit == "h" else n * 24
                if hours > 30:
                    continue
                wins["merged_prs"].append({
                    "num": num.lstrip("#"),
                    "title": title.rstrip("…").strip()[:60],
                    "age": age,
                })
    # Matt's most recent standup post (last 24h)
    try:
        client = digest.slack_client()
        matt_msgs = digest.fetch_standup(client, days=2)
        cutoff_ts = (now - dt.timedelta(hours=24)).timestamp()
        matt_recent = [
            m for m in matt_msgs
            if m.get("user") == digest.MATT_USER_ID and float(m.get("ts") or 0) >= cutoff_ts
        ]
        if matt_recent:
            matt_recent.sort(key=lambda m: float(m.get("ts") or 0), reverse=True)
            line = digest.first_meaningful_line(matt_recent[0].get("text") or "", max_len=80)
            wins["standup"] = line
    except Exception:
        pass
    return wins


def compute_focus_blocks(todays_evs: list, now: dt.datetime) -> list[dict]:
    """Compute free blocks between max(now,9am) → first meeting → gaps → 6pm.

    Clamps to working hours (9am-6pm PT) so the morning brief at 7am doesn't
    surface a 14-hour "focus block" that's really overnight.
    """
    work_start = now.replace(hour=9, minute=0, second=0, microsecond=0)
    work_end = now.replace(hour=18, minute=0, second=0, microsecond=0)
    if now >= work_end:
        return []
    blocks: list[dict] = []
    times: list[tuple[dt.datetime, dt.datetime, str]] = []
    for ev in todays_evs:
        start = mb.parse_event_start(ev)
        end_raw = (ev.get("end") or {}).get("dateTime") or ""
        if not (start and end_raw):
            continue
        try:
            end = dt.datetime.fromisoformat(end_raw.replace("Z", "+00:00")).astimezone(PT)
        except (ValueError, TypeError):
            continue
        if end < now:
            continue
        times.append((start, end, ev.get("summary") or "(meeting)"))
    times.sort()
    cursor = max(now, work_start)
    for start, end, _ in times:
        if start > cursor:
            gap_min = int((start - cursor).total_seconds() / 60)
            if gap_min >= 30:
                blocks.append({"start": cursor, "end": start, "minutes": gap_min})
        cursor = max(cursor, end)
    if work_end > cursor:
        gap_min = int((work_end - cursor).total_seconds() / 60)
        if gap_min >= 30:
            blocks.append({"start": cursor, "end": work_end, "minutes": gap_min})
    return blocks


# ──────────────────────────── workstreams + content pipeline ────────────────────────────

WS_STATE = Path.home() / ".claude" / "workstreams" / "state.json"
ZPUB_INDEX = VAULT / "MattZerg" / "Projects" / "Zerg-Production" / "Growth" / "publishing" / "_meta" / "index.json"
_BUCKET_ORDER = {"hot": 0, "warm": 1, "stale": 2, "parked": 3, "empty": 4}
_BUCKET_EMOJI = {"hot": "🔥", "warm": "🟠", "stale": "⏸ ", "parked": "💤", "empty": "○ "}


def pull_workstreams() -> list[dict]:
    """Return workstreams sorted hot→warm→stale (skip empty/catchall)."""
    if not WS_STATE.exists():
        return []
    try:
        ws = json.loads(WS_STATE.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    rows: list[dict] = []
    for sid, w in ws.get("workstreams", {}).items():
        if w.get("catchall"):
            continue
        bucket = w.get("bucket", "empty")
        if bucket == "empty":
            continue
        rows.append({
            "id": sid,
            "bucket": bucket,
            "emoji": _BUCKET_EMOJI.get(bucket, "•"),
            "prs": len(w.get("prs", [])),
            "sessions": len(w.get("sessions", [])),
            "inbox": len(w.get("inbox_items", []) or w.get("open_items", [])),
            "ideas": len(w.get("ideas", [])),
        })
    rows.sort(key=lambda r: (_BUCKET_ORDER.get(r["bucket"], 9), r["id"]))
    return rows


def pull_content_pipeline() -> dict:
    """Aggregate counts + top reds from zpub publishing index."""
    if not ZPUB_INDEX.exists():
        return {}
    try:
        data = json.loads(ZPUB_INDEX.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    counts = {"red": 0, "amber": 0, "yellow": 0, "green": 0}
    reds: list[dict] = []
    for e in data.get("entries", []):
        status = (e.get("status") or "").lower()
        target = e.get("publish_target")
        blockers = e.get("blockers") or []
        gates = e.get("gates") or {}
        failed_gate = any(v == "failed" for v in gates.values())
        # Match zpub RAYG logic — approximate
        if not e.get("_path"):
            continue
        if status in ("published", "distributed", "archived"):
            counts["green"] += 1
        elif blockers or failed_gate or status == "ideating":
            counts["red"] += 1
            if len(reds) < 3:
                reds.append({
                    "id": e.get("id", ""),
                    "title": (e.get("title") or "")[:80],
                    "reason": blockers[0] if blockers else f"failed gate",
                })
        elif status in ("review", "scheduled", "queued"):
            counts["yellow"] += 1
        else:
            counts["amber"] += 1
    return {"counts": counts, "top_reds": reds, "total": data.get("count", 0)}


LINKS_LEDGER = VAULT / "MattZerg/Projects/Zerg-Production/Growth/links.md"


def pull_content_performance(now: dt.datetime, top_n: int = 5) -> dict:
    """Return last-7-day content performance — Zerglytics API if api_key wired,
    else UTM-coverage proxy from links.md, else placeholder.

    Shape:
      {"available": bool, "source": "api"|"links"|"none",
       "rows": [{"title": str, "views": int|None, "clicks": int|None, "date": str}],
       "note": str}

    Fails gracefully like the ccusage panel (see `pull_token_burn`) — every
    branch returns the same shape so the renderer never crashes. Per memory
    `feedback_proactive_content_analytics.md`: morning-brief should lead with
    data on every status, not just when asked.

    Cascade:
      (a) Zerglytics public API at https://zerglytics.fly.dev/api/v1/... if
          `zerglytics_api_key` is in Keychain (per growth-dashboard SKILL.md).
          NOTE: api_key NOT in Keychain yet (Zergboard issue #68) — this path
          will degrade to (b) until wired.
      (b) Parse `Growth/links.md` for UTM campaigns with timestamps in window
          (last 7d). Surfaces campaign coverage as proxy: # of UTM links per
          campaign tells Matt where distribution effort went. Clicks=None
          because links.md is a generator ledger, not an analytics store.
      (c) Neither → placeholder telling Matt to wire api_key.
    """
    placeholder = {
        "available": False,
        "source": "none",
        "rows": [],
        "note": "No content perf data — wire Zerglytics api_key (#68) or check links.md UTM coverage",
    }
    # (a) Zerglytics API — Keychain lookup
    api_key = None
    try:
        res = subprocess.run(
            ["security", "find-generic-password", "-a", "matteisn",
             "-s", "zerglytics_api_key", "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if res.returncode == 0:
            api_key = (res.stdout or "").strip() or None
    except (subprocess.TimeoutExpired, OSError):
        pass
    if api_key:
        try:
            import urllib.request
            req = urllib.request.Request(
                "https://zerglytics.fly.dev/api/v1/posts/top?window=7d&limit=10",
                headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310
                payload = json.loads(r.read().decode("utf-8") or "{}")
            rows: list[dict] = []
            slug_to_title = _build_slug_title_map()
            for p in (payload.get("posts") or [])[:top_n]:
                slug = p.get("slug") or p.get("path") or ""
                title = slug_to_title.get(slug) or p.get("title") or slug
                rows.append({
                    "title": title[:60],
                    "views": int(p.get("views") or 0),
                    "clicks": int(p.get("utm_clicks") or 0) if p.get("utm_clicks") is not None else None,
                    "date": (p.get("published") or "")[:10],
                })
            return {
                "available": True, "source": "api", "rows": rows,
                "note": "" if rows else "Zerglytics returned 0 posts in last 7d",
            }
        except Exception as exc:
            # Fall through to (b)
            placeholder["note"] = f"Zerglytics API error ({type(exc).__name__}) — falling back to links.md"
    # (b) links.md UTM coverage proxy
    if LINKS_LEDGER.exists():
        try:
            text = LINKS_LEDGER.read_text(errors="replace")
        except OSError:
            text = ""
        today = now.date()
        cutoff = today - dt.timedelta(days=7)
        # Aggregate rows: per-(campaign,destination) within window
        agg: dict[tuple, dict] = {}
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith("|") or "| Date " in line or line.startswith("|---"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) < 6:
                continue
            date_s, campaign, source, medium, content, destination = cells[:6]
            try:
                d = dt.date.fromisoformat(date_s)
            except (ValueError, IndexError):
                continue
            if d < cutoff or d > today:
                continue
            # Skip stale campaign explicitly flagged in the file
            if "zergboard-launch-2026-05" in campaign:
                continue
            key = (campaign, destination)
            row = agg.setdefault(key, {"campaign": campaign, "destination": destination,
                                       "links": 0, "date": date_s})
            row["links"] += 1
            if date_s > row["date"]:
                row["date"] = date_s
        rows = sorted(agg.values(), key=lambda r: (-r["links"], r["date"]))
        out: list[dict] = []
        slug_to_title = _build_slug_title_map()
        for r in rows[:top_n]:
            # Try to map destination URL to a known slug→title
            dest = r["destination"]
            title = None
            for slug, t in slug_to_title.items():
                if slug and slug in dest:
                    title = t
                    break
            if not title:
                title = r["campaign"]
            out.append({
                "title": title[:60],
                "views": None,
                "clicks": r["links"],  # proxy: links generated, not actual clicks
                "date": r["date"],
            })
        if out:
            return {
                "available": True, "source": "links", "rows": out,
                "note": "UTM-coverage proxy (links generated, not actual clicks) — wire Zerglytics api_key (#68) for real data",
            }
    return placeholder


def _build_slug_title_map() -> dict[str, str]:
    """Map blog slugs → titles from zpub publishing index for friendlier display."""
    out: dict[str, str] = {}
    if not ZPUB_INDEX.exists():
        return out
    try:
        data = json.loads(ZPUB_INDEX.read_text())
    except (OSError, json.JSONDecodeError):
        return out
    for e in data.get("entries", []):
        slug = e.get("slug") or e.get("id") or ""
        title = e.get("title") or ""
        if slug and title:
            out[slug] = title
    return out


# ──────────────────────────── render layer ────────────────────────────

def _hms(d: dt.datetime) -> str:
    return d.strftime("%-I:%M%p").lower()


import unicodedata as _ud


def _display_width(s: str) -> int:
    """Approximate terminal display width — emoji/CJK = 2, combining = 0, else = 1."""
    w = 0
    for c in s:
        cat = _ud.category(c)
        if cat.startswith("M") or c == "️":  # combining marks + VS-16
            continue
        cp = ord(c)
        if (0x1F300 <= cp <= 0x1FAFF
            or 0x2600 <= cp <= 0x27BF
            or 0x1F100 <= cp <= 0x1F1FF
            or 0x2300 <= cp <= 0x23FF
            or 0x2B00 <= cp <= 0x2BFF):
            w += 2
        else:
            w += 1
    return w


def _row(text: str) -> str:
    """Wrap a line as a box body row, truncating to INNER display width."""
    if _display_width(text) > INNER:
        while text and _display_width(text + "…") > INNER:
            text = text[:-1]
        text = text + "…"
    pad = INNER - _display_width(text)
    return f"║  {text}{' ' * max(0, pad)}  ║"


def _blank() -> str:
    return f"║  {' ' * INNER}  ║"


def _section(label: str) -> str:
    """Render `╠══ <label> ═══...═╣` — fill computed by display width."""
    raw = f"══ {label} "
    fill = "═" * max(0, BOX_WIDTH - _display_width(raw) - 2)
    return f"╠{raw}{fill}╣"


def _top(date_tag: str) -> str:
    raw = f"══ 🌅 MORNING BRIEF ══ {date_tag} "
    fill = "═" * max(0, BOX_WIDTH - _display_width(raw) - 2)
    return f"╔{raw}{fill}╗"


def _bottom() -> str:
    return "╚" + "═" * (BOX_WIDTH - 2) + "╝"


def _cap_bar(cap: str, held_n: int) -> str:
    try:
        used, total = (int(x) for x in cap.split("/"))
    except (ValueError, AttributeError):
        return f"Cap {cap} · held: {held_n}"
    bar_width = 20
    filled = min(bar_width, int(round(bar_width * used / max(total, 1))))
    bar = "█" * filled + "░" * (bar_width - filled)
    state = "⛔ FULL" if used >= total else "✅ open"
    return f"Cap {bar}  {used}/{total}  {state}  · held: {held_n}"


ZONES_ALL = {
    "today", "blocked", "autonomous", "decisions", "gtm", "workstreams", "focus",
    "pr", "tokenburn", "costperoutcome", "wins", "content", "contentperf",
    "async", "next7", "blogs", "launches", "next",
}
ZONES_COMPACT = {"today", "blocked", "decisions", "content", "contentperf", "pr", "next"}
ZONE_ALIASES = {
    "auto": "autonomous", "ws": "workstreams",
    "pending-decisions": "decisions", "queue": "decisions",
    "decision-queue": "decisions",
    "pr-pipeline": "pr", "yesterday": "wins", "content-pipeline": "content",
    "content-perf": "contentperf", "perf": "contentperf",
    "content-performance": "contentperf", "analytics": "contentperf",
    "waiting": "async", "calendar": "next7", "blog-queue": "blogs",
    "next-move": "next", "meetings": "focus",
    "burn": "tokenburn", "ccusage": "tokenburn", "cost": "tokenburn",
    "cost-per-outcome": "costperoutcome", "cpo": "costperoutcome",
    "roi": "costperoutcome", "waste": "costperoutcome",
}


def _resolve_zones(spec) -> set[str]:
    """Accept None (all), 'compact', or comma-separated zone list."""
    if spec is None:
        return set(ZONES_ALL)
    if isinstance(spec, str):
        if spec == "compact":
            return set(ZONES_COMPACT)
        if spec == "all" or spec == "expanded":
            return set(ZONES_ALL)
        wanted = {ZONE_ALIASES.get(z.strip(), z.strip()) for z in spec.split(",") if z.strip()}
        unknown = wanted - ZONES_ALL
        if unknown:
            sys.stderr.write(f"WARN: unknown zone(s) {sorted(unknown)} — valid: {sorted(ZONES_ALL)}\n")
        return wanted & ZONES_ALL
    return set(spec) & ZONES_ALL


def render_dashboard(data: dict, zones=None) -> str:
    zones = _resolve_zones(zones)
    now = data["now"]
    out: list[str] = []
    ts = now.strftime("%a %b %-d %Y · %H:%M %Z")
    out.append(_top(ts))
    out.append(_blank())

    # 🎯 TODAY
    if "today" in zones:
        out.append(_row("🎯 TODAY"))
        lead_obj = data["lead"]
        lead = lead_obj["action"]
        for chunk in _wrap(lead, INNER - 2):
            out.append(_row(chunk))
        # Provenance line — show where the lead came from
        raw = lead_obj.get("raw", "")
        prov_m = re.search(r"_\(([^)]+)\)_\s*$", raw or "")
        if prov_m:
            out.append(_row(f"     from {prov_m.group(1)}"))
        elif lead_obj.get("source") and lead_obj["source"] != "open":
            out.append(_row(f"     source: {lead_obj['source']}"))
        out.append(_blank())

    # 🔴 BLOCKED ON YOU
    blockers = data["blockers"]
    if "blocked" in zones and blockers:
        # I5 — count overdue + add urgency to header
        today = data["now"].date() if hasattr(data["now"], "date") else None
        overdue_n = 0
        if today:
            for b in blockers:
                d = b.get("due_date")
                if d:
                    try:
                        bd = dt.date.fromisoformat(d) if isinstance(d, str) else d
                        if bd < today:
                            overdue_n += 1
                    except (TypeError, ValueError):
                        pass
        header = "🔴 BLOCKED ON YOU"
        if overdue_n:
            header += f"  ({overdue_n} OVERDUE)"
        out.append(_section(header))
        out.append(_blank())
        for b in blockers:
            emoji = _blocker_emoji(b)
            # I5 — urgency emoji ahead of item text
            urgency = ""
            if today and b.get("due_date"):
                try:
                    bd = dt.date.fromisoformat(b["due_date"]) if isinstance(b["due_date"], str) else b["due_date"]
                    delta = (bd - today).days
                    if delta < 0:
                        urgency = f"🚨 {-delta}d overdue  "
                    elif delta == 0:
                        urgency = "⏰ today  "
                    elif delta <= 3:
                        urgency = f"📅 +{delta}d  "
                except (TypeError, ValueError):
                    pass
            head_budget = INNER - 6 - _display_width(urgency)
            line1 = f"{emoji}  {urgency}{b['item'][:head_budget]}"
            out.append(_row(line1))
            # Provenance: which inbox row + due date if dated
            src_bits = [f"inbox #{b['num']}"]
            if b.get("due_date"):
                src_bits.append(f"due {b['due_date']}")
            if b.get("domain"):
                src_bits.append(b["domain"])
            out.append(_row(f"     {' · '.join(src_bits)[:INNER-7]}"))
            # I1 — wrap why-line instead of clip
            why_short = _condense_why(b.get("why") or "")
            if why_short:
                for chunk in _wrap(why_short, INNER - 7):
                    out.append(_row(f"     {chunk}"))
        out.append(_blank())

    # 🤖 AUTONOMOUS
    autos = data["autonomous"]
    if "autonomous" in zones and autos:
        out.append(_section("🤖 AUTONOMOUS — I CAN PUSH NOW"))
        out.append(_blank())
        for a in autos:
            out.append(_row(f"•  {a['text']}"))
        out.append(_blank())

    # 🗳 PENDING DECISIONS — oldest first (Phase 9.1: make the queue pay rent)
    pd = data.get("pending_decisions") or {}
    if "decisions" in zones:
        if not pd.get("available"):
            # Never errors — empty/stale/missing all collapse to one status line.
            status = pd.get("status", "empty")
            out.append(_section("🗳 PENDING DECISIONS"))
            out.append(_blank())
            out.append(_row(f"Decision queue: {status}"))
            out.append(_blank())
        else:
            total = pd.get("total", 0)
            status = pd.get("status", "")
            header = f"🗳 PENDING DECISIONS — {total} in queue (oldest first)"
            out.append(_section(header))
            out.append(_blank())
            if status and status != "fresh":
                out.append(_row(f"⚠️  queue {status}"))
            out.append(_row(f"     resolve all via swipe: {pd.get('swipe_url', '')}"))
            out.append(_blank())
            for d in pd.get("top", []):
                age_d = d.get("age_days", 0.0)
                age_label = f"{age_d:.0f}d old" if age_d else (d.get("age_human") or "")
                for i, ch in enumerate(_wrap(f"• {d['description']}", INNER)):
                    out.append(_row(ch if i == 0 else f"  {ch}"))
                meta = f"     {age_label} · [{d['source']}] {d['autonomy_class']}"
                out.append(_row(meta[:INNER]))
                for ch in _wrap(f"→ {d['resolve']}", INNER - 7):
                    out.append(_row(f"     {ch}"))
            out.append(_blank())

    # 🎯 Decision queue (Phase 3 S0.1)
    dq = data.get("decision_queue") or {}
    if "gtm" in zones and dq.get("total", 0) > 0:
        out.append(_section(f"🎯 DECISION QUEUE — {dq['total']} pending"))
        out.append(_blank())
        out.append(_row(f"     reply via swipe: {dq['swipe_url']}"))
        out.append(_blank())
        for d in dq.get("top", []):
            ctx_chunks = _wrap(f"• {d['context']}", INNER)
            for i, ch in enumerate(ctx_chunks):
                out.append(_row(ch if i == 0 else f"  {ch}"))
            meta = f"  [{d['source']}] {d['autonomy_class']} · {d['age']} · p={d['priority']}"
            if d.get('deadline'):
                meta += f" · ⏰ {d['deadline']}"
            out.append(_row(meta[:INNER]))
        out.append(_blank())

    # 📊 GTM decisions waiting on you
    gtm = data["gtm"]
    if "gtm" in zones and gtm:
        out.append(_section("🎚 GTM DECISIONS WAITING ON YOU"))
        out.append(_blank())
        for d in gtm:
            # I1 — wrap title if too long for one line
            title_chunks = _wrap(f"{d['emoji']}  {d['title']}", INNER)
            for i, ch in enumerate(title_chunks):
                out.append(_row(ch if i == 0 else f"    {ch}"))
            tail = f"{d['urgency']} · {d['n_opts']} opts → gtm decide {d['id']}"
            for chunk in _wrap(tail, INNER - 7):
                out.append(_row(f"     {chunk}"))
            src_bits = []
            if d.get("source_file"):
                src_bits.append(f"src: {d['source_file']}")
            if d.get("last_touch"):
                src_bits.append(f"last touch {d['last_touch']}")
            if src_bits:
                for chunk in _wrap(" · ".join(src_bits), INNER - 7):
                    out.append(_row(f"     {chunk}"))
        out.append(_blank())

    # 🎯 WORKSTREAMS (I3 — drop rows with no counts; hide zone if all empty)
    ws_rows = [
        w for w in (data.get("workstreams") or [])
        if w["prs"] or w["sessions"] or w["inbox"] or w["ideas"]
    ]
    if "workstreams" in zones and ws_rows:
        out.append(_section("🎯 WORKSTREAMS"))
        out.append(_blank())
        for w in ws_rows[:6]:
            counts_str = []
            if w["prs"]:
                counts_str.append(f"{w['prs']} PRs")
            if w["sessions"]:
                counts_str.append(f"{w['sessions']} sess")
            if w["inbox"]:
                counts_str.append(f"{w['inbox']} inbox")
            if w["ideas"]:
                counts_str.append(f"{w['ideas']} ideas")
            tail = " · ".join(counts_str)
            label = f"{w['emoji']}  {w['id']:<22}  {w['bucket']:<6}  {tail}"
            out.append(_row(label[:INNER]))
        out.append(_blank())

    # 🕘 FOCUS BLOCKS + 📆 TODAY
    todays = data["todays_meetings"]
    blocks = data["focus_blocks"]
    if "focus" in zones and (todays or blocks):
        out.append(_section("📆 TODAY"))
        out.append(_blank())
        for ev in todays[:6]:
            when = mb.parse_event_start(ev)
            tstr = _hms(when) if when else "today"
            ext = ""
            if ev.get("attendees"):
                # crude external detector — same logic as standup_draft
                attendees = ev["attendees"]
                for a in attendees:
                    email = a.get("email") or ""
                    if "@" in email and not a.get("self"):
                        domain = email.split("@", 1)[1]
                        if domain not in {"zergai.com", "epoch-ai.in"}:
                            ext = "  🤝"
                            break
            title = (ev.get("summary") or "(no title)")[:INNER - 16]
            out.append(_row(f"{tstr:>8}  {title}{ext}"))
        if blocks:
            out.append(_blank())
            out.append(_row("🕘 Focus blocks"))
            for b in blocks[:3]:
                hours = b["minutes"] / 60
                line = f"   {_hms(b['start'])} → {_hms(b['end'])}  ({hours:.1f}h)"
                out.append(_row(line))
        out.append(_blank())

    # 🚦 PR PIPELINE
    prs = data["prs"]
    if "pr" in zones and (prs["open"] or prs["held"]):
        out.append(_section("🚦 PR PIPELINE"))
        out.append(_blank())
        out.append(_row(_cap_bar(prs["cap"], prs.get("held_n", len(prs["held"])))))
        if prs["open"]:
            out.append(_blank())
            for pr in prs["open"][:3]:
                num = pr["num"].lstrip("#")
                title = (pr["title"] or "")[:INNER - 25]
                state = pr["state"]
                age = pr.get("age", "")
                state_emoji = "🔴" if state == "BLOCKED" else "🟢"
                out.append(_row(f"{state_emoji} #{num}  {title}"))
                out.append(_row(f"     {state} · {pr.get('reviews','')} · CI {pr.get('ci','')} · {age}"))
        out.append(_blank())

    # 💸 TOKEN BURN (ccusage, past 24h) — placeholder if ccusage isn't installed
    tb = data.get("token_burn") or {}
    if "tokenburn" in zones and tb:
        out.append(_section("💸 TOKEN BURN — PAST 24h"))
        out.append(_blank())
        if not tb.get("available"):
            out.append(_row(f"💸 {tb.get('note', 'ccusage unavailable')}"))
        else:
            total = tb.get("total_cost_usd")
            total_str = f"${total:.2f}" if isinstance(total, (int, float)) else "—"
            out.append(_row(f"💰 Total spend: {total_str}"))
            tops = tb.get("top_skills") or []
            if tops:
                out.append(_blank())
                for s in tops[:5]:
                    cost = s.get("cost_usd", 0.0)
                    line = f"   ${cost:>6.2f}  {s.get('name','?')}"
                    out.append(_row(line[:INNER]))
            else:
                out.append(_row("   (no per-skill breakdown returned)"))
        out.append(_blank())

    # 💎 COST-PER-OUTCOME — past 24h session ROI
    # Pairs ccusage cost × transcript-derived outcome signals (PR opened/merged,
    # zpub flips, inbox closes, malformed-agent waste). Sibling to TOKEN BURN
    # (raw spend) — this answers "which sessions burned cash for nothing?".
    cpo = data.get("cost_per_outcome") or {}
    if "costperoutcome" in zones and cpo:
        out.append(_section("💎 COST-PER-OUTCOME — PAST 24h"))
        out.append(_blank())
        if not cpo.get("available"):
            out.append(_row(f"💎 {cpo.get('note', 'cost-per-outcome unavailable')}"))
        else:
            note = cpo.get("note") or ""
            waste = cpo.get("waste") or []
            eff = cpo.get("efficiency") or []
            if not waste and not eff:
                msg = note or "no scored sessions yet"
                out.append(_row(f"💎 {msg}"))
            else:
                if waste:
                    out.append(_row("🔻 WASTE  (high cost · no detected outcome)"))
                    for s in waste:
                        head = f"   ${s['cost']:>6.2f}  {s['uuid8']}  skill={s['skill']}"
                        out.append(_row(head[:INNER]))
                        fu = (s.get("first_user") or "").replace("`", "'")
                        for i, chunk in enumerate(_wrap(fu, INNER - 8)):
                            out.append(_row(f"        {chunk}"))
                        if s.get("malformed"):
                            out.append(_row(
                                f"        malformed={s['malformed']}"[:INNER]
                            ))
                if waste and eff:
                    out.append(_blank())
                if eff:
                    out.append(_row("🟢 EFFICIENCY WINS  (best outcome per $)"))
                    for s in eff:
                        flags = ",".join(s.get("flags") or []) or "-"
                        head = (f"   ROI {s.get('roi', 0):>5.1f}  "
                                f"${s['cost']:>6.2f}  {s['uuid8']}  [{flags}]")
                        out.append(_row(head[:INNER]))
                        fu = (s.get("first_user") or "").replace("`", "'")
                        for chunk in _wrap(fu, INNER - 8):
                            out.append(_row(f"        {chunk}"))
                if note:
                    out.append(_blank())
                    for chunk in _wrap(note, INNER - 4):
                        out.append(_row(f"  ℹ  {chunk}"))
        out.append(_blank())

    # 🚀 YESTERDAY'S WINS
    wins = data["yesterday_wins"]
    if "wins" in zones and (wins["merged_prs"] or wins["standup"]):
        out.append(_section("🚀 YESTERDAY'S WINS"))
        out.append(_blank())
        if wins["merged_prs"]:
            mp = wins["merged_prs"]
            label = f"✅ {len(mp)} PRs merged: " + ", ".join(f"#{p['num']}" for p in mp[:6])
            out.append(_row(label[:INNER]))
        if wins["standup"]:
            out.append(_row(f"📣 standup: {wins['standup'][:INNER-12]}"))
        out.append(_blank())

    # 📋 CONTENT PIPELINE (zpub aggregate)
    cp = data.get("content_pipeline") or {}
    if "content" in zones and cp:
        out.append(_section("📋 CONTENT PIPELINE (zpub)"))
        out.append(_blank())
        counts = cp.get("counts", {})
        total = cp.get("total", 0)
        summary = (
            f"🔴 {counts.get('red', 0):<3} red  · "
            f"🟠 {counts.get('amber', 0):<3} amber  · "
            f"🟡 {counts.get('yellow', 0):<3} yellow  · "
            f"🟢 {counts.get('green', 0):<3} green   ({total} total)"
        )
        out.append(_row(summary[:INNER]))
        top_reds = cp.get("top_reds", [])
        total_red = counts.get("red", 0)
        if top_reds:
            out.append(_blank())
            for r in top_reds:
                # I1 — wrap title + reason
                for i, chunk in enumerate(_wrap(r["title"], INNER - 4)):
                    out.append(_row(f"🔴  {chunk}" if i == 0 else f"     {chunk}"))
                for chunk in _wrap(r["reason"], INNER - 7):
                    out.append(_row(f"     {chunk}"))
            if total_red > len(top_reds):
                out.append(_row(f"     +{total_red - len(top_reds)} more reds — `zpub all`"))
        out.append(_blank())

    # 📰 CONTENT PERFORMANCE — LAST 7 DAYS
    cperf = data.get("content_perf") or {}
    if "contentperf" in zones and cperf:
        out.append(_section("📰 CONTENT PERFORMANCE — LAST 7 DAYS"))
        out.append(_blank())
        if not cperf.get("available"):
            out.append(_row(f"📰 {cperf.get('note', 'No content perf data')}"))
        else:
            rows = cperf.get("rows") or []
            src = cperf.get("source", "?")
            if not rows:
                out.append(_row(f"📰 {cperf.get('note', 'No posts in last 7d')} (source: {src})"))
            else:
                # Header — `<title-32>  <views>  <clicks>  <date>`
                header = f"{'title':<32}  {'views':>6}  {'clicks':>6}  {'date':<10}"
                out.append(_row(header[:INNER]))
                for r in rows:
                    title = (r.get("title") or "?")[:32]
                    views = r.get("views")
                    clicks = r.get("clicks")
                    views_s = f"{views:>6}" if isinstance(views, int) else "     —"
                    clicks_s = f"{clicks:>6}" if isinstance(clicks, int) else "     —"
                    date_s = (r.get("date") or "")[:10]
                    line = f"{title:<32}  {views_s}  {clicks_s}  {date_s:<10}"
                    out.append(_row(line[:INNER]))
                note = cperf.get("note") or ""
                if note:
                    out.append(_blank())
                    for chunk in _wrap(note, INNER - 4):
                        out.append(_row(f"  ℹ  {chunk}" if chunk == _wrap(note, INNER - 4)[0]
                                        else f"     {chunk}"))
        out.append(_blank())

    # ⏳ ASYNC / WAITING
    asyncs = data["async"]
    if "async" in zones and asyncs:
        out.append(_section("⏳ ASYNC / WAITING"))
        out.append(_blank())
        for a in asyncs[:4]:
            out.append(_row(f"•  {a[:INNER-3]}"))
        out.append(_blank())

    # 🗓 NEXT 7 DAYS (calendar — gcal-only, never launches)
    upcoming = data["upcoming"]
    if "next7" in zones and upcoming:
        out.append(_section("🗓 NEXT 7 DAYS"))
        out.append(_blank())
        for u in upcoming[:6]:
            out.append(_row(u[:INNER]))
        out.append(_blank())

    # 📰 BLOG QUEUE — dated blog publishes in next 8 weeks (independent of launches)
    blog_queue = data["blog_queue"]
    if "blogs" in zones and blog_queue:
        out.append(_section("📰 BLOG QUEUE — NEXT 8 WEEKS"))
        out.append(_blank())
        for b in blog_queue:
            date_str = b["date"].strftime("%a %b %-d")
            status_emoji = {
                "scheduled": "🟢", "queued": "🟢", "review": "🟡",
                "drafting": "🟠", "ideating": "🔴",
            }.get(b["status"], "⚪")
            out.append(_row(f"{status_emoji} {date_str:>10}  {b['title']}"))
        out.append(_blank())

    # 🚧 ASPIRATIONAL LAUNCHES (date_confirmed: false — ship-when-ready)
    aspirational = data["aspirational"]
    if "launches" in zones and aspirational:
        out.append(_section("🚧 LAUNCHES — SHIP-WHEN-READY (no confirmed date)"))
        out.append(_blank())
        for a in aspirational[:6]:
            out.append(_row(f"•  {a['title']}"))
            out.append(_row(f"     aspirational target {a['target']} · state {a['state']} · src: {a['source']}"))
        out.append(_blank())

    # 🎯 NEXT MOVE
    if "next" in zones:
        out.append(_section("🎯 NEXT MOVE"))
        out.append(_blank())
        for i, step in enumerate(data["next_moves"][:3], 1):
            prefix = f"{i}) "
            budget = INNER - _display_width(prefix)
            s = step
            if _display_width(s) > budget:
                while s and _display_width(s + "…") > budget:
                    s = s[:-1]
                s = s + "…"
            out.append(_row(f"{prefix}{s}"))
        out.append(_blank())
    out.append(_bottom())

    # Footers below the box
    out.append("")
    yl = data.get("yesterday_lead")
    if yl:
        sym = {"ACTED": "✅", "OPEN": "❌", "UNKNOWN": "❓"}.get(yl["status"], "❓")
        out.append(f"📊 Yesterday 🎯: {sym} {yl['action']}  ({yl['status']})")
    healthy = data.get("healthy_footer") or []
    if healthy:
        out.append(f"✅ Healthy: {' · '.join(healthy)}")
    return "\n".join(out)


def _wrap(text: str, width: int) -> list[str]:
    if len(text) <= width:
        return [text]
    out: list[str] = []
    words = text.split()
    cur = ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            out.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        out.append(cur)
    return out


def _blocker_emoji(b: dict) -> str:
    item_low = b["item"].lower()
    if any(w in item_low for w in ("pay ", "tax", "invoice", "$", "£")):
        return "💵"
    if any(w in item_low for w in ("verify", "confirm")):
        return "🧪"
    if any(w in item_low for w in ("decide", "decision", "approve", "sign")):
        return "🎚"
    if any(w in item_low for w in ("respond", "reply", "call", "message", "ask")):
        return "📞"
    if any(w in item_low for w in ("editorial", "review draft", "copyedit")):
        return "✍️"
    if any(w in item_low for w in ("pre-flight", "fakeidan", "address")):
        return "🩹"
    return "🔸"


def _condense_why(why: str) -> str:
    """Strip noise from inbox 'Why now' column — keep first sentence or path."""
    why = re.sub(r"\s+", " ", why).strip()
    if not why:
        return ""
    # Prefer first sentence, falling back to first 100 chars
    parts = re.split(r"(?<=[.;])\s+", why)
    candidate = parts[0] if parts else why
    return candidate[:100]


def pull_blog_queue(now: dt.datetime, weeks_ahead: int = 8, max_n: int = 10) -> list[dict]:
    """Read `Growth/publishing/pub-*.md` blog entries with publish_target within window."""
    pub_dir = VAULT / "MattZerg/Projects/Zerg-Production/Growth/publishing"
    if not pub_dir.exists():
        return []
    today = now.date()
    cutoff = today + dt.timedelta(days=weeks_ahead * 7)
    out: list[dict] = []
    for p in sorted(pub_dir.glob("pub-*.md")):
        try:
            text = p.read_text(errors="replace")
        except OSError:
            continue
        type_m = re.search(r"^type:\s*(\S+)", text, re.M)
        if not type_m or type_m.group(1) != "blog":
            continue
        target_m = re.search(r"^publish_target:\s*(\S+)", text, re.M)
        if not target_m or target_m.group(1) in ("null", "~", ""):
            continue
        try:
            d = dt.date.fromisoformat(target_m.group(1))
        except ValueError:
            continue
        if d < today or d > cutoff:
            continue
        status_m = re.search(r"^status:\s*(\S+)", text, re.M)
        title_m = re.search(r"^title:\s*(.+?)$", text, re.M)
        out.append({
            "date": d,
            "id": p.stem,
            "title": (title_m.group(1).strip() if title_m else p.stem)[:60],
            "status": (status_m.group(1) if status_m else "?"),
        })
    out.sort(key=lambda r: r["date"])
    return out[:max_n]


def pull_aspirational_launches(now: dt.datetime, max_n: int = 6) -> list[dict]:
    """Read `Growth/content/*-launch.md` entities with `date_confirmed: false` and
    surface them as ship-when-ready candidates. Per `feedback_launch_dates_aspirational.md`:
    target_date is aspirational unless explicitly confirmed; these never appear
    in NEXT 7 DAYS (gcal-only), but should be visible as a separate "when ready" lane.
    """
    content_dir = VAULT / "MattZerg/Projects/Zerg-Production/Growth/content"
    if not content_dir.exists():
        return []
    out: list[dict] = []
    for p in sorted(content_dir.glob("*-launch.md")):
        try:
            text = p.read_text(errors="replace")
        except OSError:
            continue
        if "kind: launch" not in text:
            continue
        confirmed = re.search(r"^date_confirmed:\s*(true|false)", text, re.M)
        if confirmed and confirmed.group(1) == "true":
            continue  # confirmed launches show in scheduled lane
        target_m = re.search(r"^target_date:\s*(\S+)", text, re.M)
        title_m = re.search(r"^title:\s*(.+?)$", text, re.M)
        state_m = re.search(r"^state:\s*(\S+)", text, re.M)
        out.append({
            "title": (title_m.group(1).strip() if title_m else p.stem)[:60],
            "target": target_m.group(1) if target_m else "?",
            "state": state_m.group(1) if state_m else "?",
            "source": f"content/{p.name}",
        })
    # Sort by aspirational target (soonest first) — informative, not committal
    out.sort(key=lambda r: r.get("target", "9999"))
    return out[:max_n]


def pull_token_burn(top_n: int = 5) -> dict:
    """Return ccusage-derived token-burn summary for the past 24h.

    Shape: {"available": bool, "total_cost_usd": float|None,
            "top_skills": [{"name": str, "cost_usd": float}], "note": str}

    ccusage 20.0.5 doesn't expose a per-skill dimension — it groups by date,
    session UUID, or billing block. We use `session --json` (each entry has
    period=<session-uuid>, totalCost, metadata.lastActivity=YYYY-MM-DD) and
    filter to today + yesterday to approximate "past 24h". Top-N rows display
    as `<uuid8>  <date>` until we wire transcript-crawl for true skill mapping
    (deferred follow-up).

    If `ccusage` isn't installed, returns available=False with a placeholder note —
    the renderer surfaces a single line telling Matt how to enable it. Any
    invocation failure (timeout, non-zero exit, JSON parse error) also degrades
    gracefully to the placeholder rather than crashing the whole brief.
    """
    placeholder = {
        "available": False,
        "total_cost_usd": None,
        "top_skills": [],
        "note": "ccusage unavailable — install bun + bunx ccusage",
    }
    try:
        which = subprocess.run(
            ["/bin/sh", "-c", "command -v ccusage"],
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError):
        return placeholder
    if which.returncode != 0 or not (which.stdout or "").strip():
        return placeholder
    try:
        res = subprocess.run(
            ["ccusage", "session", "--json"],
            capture_output=True, text=True, timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError):
        return placeholder
    if res.returncode != 0:
        return placeholder
    try:
        payload = json.loads(res.stdout or "{}")
    except json.JSONDecodeError:
        return placeholder
    # ccusage 20.x session shape: {"session": [<entry>...], "totals": {...}}.
    # Each entry: period=<session-uuid>, totalCost, metadata.lastActivity=YYYY-MM-DD.
    sessions = payload.get("session") or payload.get("sessions") or payload.get("data") or []
    if isinstance(sessions, dict):
        sessions = list(sessions.values())
    if not isinstance(sessions, list):
        return placeholder
    today = dt.date.today()
    yest = today - dt.timedelta(days=1)
    window = {str(today), str(yest)}
    recent: list[dict] = []
    for s in sessions:
        if not isinstance(s, dict):
            continue
        last = (s.get("metadata") or {}).get("lastActivity")
        if last not in window:
            continue
        try:
            cost = float(s.get("totalCost") or 0)
        except (TypeError, ValueError):
            continue
        uuid = str(s.get("period") or s.get("sessionId") or "?")
        label = f"{uuid[:8]}  {last}"
        recent.append({"name": label, "cost_usd": cost})
    total = sum(r["cost_usd"] for r in recent) if recent else None
    recent.sort(key=lambda r: r["cost_usd"], reverse=True)
    return {
        "available": True,
        "total_cost_usd": total,
        "top_skills": recent[:top_n],
        "note": "" if recent else "no sessions in past 24h",
    }


def pull_cost_per_outcome(top_n: int = 3, max_sessions: int = 12) -> dict:
    """Pair ccusage session cost × transcript-derived outcome signals to surface
    per-session ROI. Different lens than `pull_token_burn` (raw spend) — this
    answers "which sessions spent the most for the least value?".

    Outcome proxies (extracted from transcript tool_result content):
      - PR opened    (+3)  — gh URL containing /pull/
      - PR merged    (+3)  — "merged" + "pull request" in tool result
      - zpub flip    (+2)  — "zpub" + ("green"|"published")
      - inbox close  (+1)  — "task" + ("closed"|"checked off"|"marked done")
      - malformed    (-1 each, capped at -3) — InputValidationError / tool_use_error

    Returns:
      {"available": bool, "note": str,
       "waste":      [{cost, uuid8, skill, first_user, score, flags}],   # top-N
       "efficiency": [{cost, uuid8, skill, first_user, score, roi, flags}]}

    Fail-graceful (mirrors pull_token_burn pattern):
      - ccusage missing             → available=False, placeholder note
      - transcript scan times out   → degrade to ccusage-only summary
      - any sub-pull exception      → caught & returns placeholder
    Bounded — only the top `max_sessions` by cost get transcript-walked.
    """
    import time
    from collections import Counter

    placeholder = {
        "available": False,
        "note": "ccusage unavailable — install bun + bunx ccusage",
        "waste": [],
        "efficiency": [],
    }
    try:
        which = subprocess.run(
            ["/bin/sh", "-c", "command -v ccusage"],
            capture_output=True, text=True, timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError):
        return placeholder
    if which.returncode != 0 or not (which.stdout or "").strip():
        return placeholder
    try:
        res = subprocess.run(
            ["ccusage", "session", "--json"],
            capture_output=True, text=True, timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError):
        return placeholder
    if res.returncode != 0:
        return placeholder
    try:
        payload = json.loads(res.stdout or "{}")
    except json.JSONDecodeError:
        return placeholder
    sessions = payload.get("session") or payload.get("sessions") or payload.get("data") or []
    if isinstance(sessions, dict):
        sessions = list(sessions.values())
    if not isinstance(sessions, list):
        return placeholder

    today = dt.date.today()
    yest = today - dt.timedelta(days=1)
    window = {str(today), str(yest)}
    recent: list[dict] = []
    for s in sessions:
        if not isinstance(s, dict):
            continue
        last = (s.get("metadata") or {}).get("lastActivity")
        if last not in window:
            continue
        try:
            cost = float(s.get("totalCost") or 0)
        except (TypeError, ValueError):
            continue
        uuid = str(s.get("period") or s.get("sessionId") or "")
        if not uuid:
            continue
        recent.append({"uuid": uuid, "cost": cost, "last": last})
    if not recent:
        return {"available": True, "note": "no sessions in past 24h",
                "waste": [], "efficiency": []}

    # Bound transcript-walk to the top-N most-expensive sessions (cheap ones
    # rarely move the ROI needle and the walk is the slow part).
    recent.sort(key=lambda r: r["cost"], reverse=True)
    candidates = recent[:max_sessions]

    # Build UUID → transcript path index once (cheap glob).
    projects_root = Path.home() / ".claude" / "projects"
    uuid_to_path: dict[str, Path] = {}
    try:
        for jf in projects_root.glob("*/*.jsonl"):
            uuid_to_path[jf.stem] = jf
    except OSError:
        return {"available": True, "note": "transcript index unavailable",
                "waste": [], "efficiency": []}

    def _extract_text(content) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            return " ".join(
                c.get("text", "") for c in content
                if isinstance(c, dict) and c.get("type") == "text"
            )
        return ""

    def _analyze(path: Path, deadline: float) -> dict:
        info = {
            "first_user": None, "skill": None, "outcome_score": 0,
            "flags": [], "malformed": 0,
        }
        if path is None or not path.exists():
            return info
        skills: list[str] = []
        pr_opened = pr_merged = zpub_pub = inbox_done = False
        malformed = 0
        try:
            with path.open(errors="replace") as f:
                for line in f:
                    if time.monotonic() > deadline:
                        # Bail mid-walk; return whatever we collected
                        break
                    try:
                        d = json.loads(line)
                    except Exception:
                        continue
                    t = d.get("type")
                    msg = d.get("message") or {}
                    content = msg.get("content")
                    if t == "user":
                        if info["first_user"] is None:
                            text = _extract_text(content)
                            if text and not text.startswith((
                                "<local-command-", "<system-reminder",
                                "<command-name>", "Caveat:",
                            )):
                                info["first_user"] = text[:120].replace("\n", " ").strip()
                        if isinstance(content, list):
                            for c in content:
                                if isinstance(c, dict) and c.get("type") == "tool_result":
                                    rt = _extract_text(c.get("content"))[:1500].lower()
                                    if not rt:
                                        continue
                                    if "github.com/" in rt and "/pull/" in rt:
                                        pr_opened = True
                                    if "merged" in rt and "pull request" in rt:
                                        pr_merged = True
                                    if "zpub" in rt and ("green" in rt or "published" in rt):
                                        zpub_pub = True
                                    if "task" in rt and (
                                        "closed" in rt or "checked off" in rt
                                        or "marked done" in rt
                                    ):
                                        inbox_done = True
                                    if ("inputvalidationerror" in rt
                                            or "malformed" in rt
                                            or "tool_use_error" in rt):
                                        malformed += 1
                    elif t == "assistant":
                        if isinstance(content, list):
                            for c in content:
                                if (isinstance(c, dict)
                                        and c.get("type") == "tool_use"
                                        and c.get("name") == "Skill"):
                                    inp = c.get("input") or {}
                                    sk = inp.get("skill")
                                    if sk:
                                        skills.append(str(sk))
        except OSError:
            return info
        if skills:
            info["skill"] = Counter(skills).most_common(1)[0][0]
        flags = []
        score = 0
        if pr_opened:  flags.append("pr_opened");      score += 3
        if pr_merged:  flags.append("pr_merged");      score += 3
        if zpub_pub:   flags.append("zpub_published"); score += 2
        if inbox_done: flags.append("inbox_done");     score += 1
        score -= min(malformed, 3)
        info["outcome_score"] = score
        info["flags"] = flags
        info["malformed"] = malformed
        return info

    # 60s total walk budget across all candidates (≈ 5s per session worst-case).
    deadline = time.monotonic() + 60.0
    scored: list[dict] = []
    try:
        for c in candidates:
            if time.monotonic() > deadline:
                break
            info = _analyze(uuid_to_path.get(c["uuid"]), deadline)
            scored.append({
                "uuid8": c["uuid"][:8],
                "cost": c["cost"],
                "last": c["last"],
                "first_user": info["first_user"] or "(no user message)",
                "skill": info["skill"] or "—",
                "score": info["outcome_score"],
                "flags": info["flags"],
                "malformed": info["malformed"],
            })
    except Exception:
        # Defensive — never crash the whole brief on a transcript-walk bug
        return {"available": True, "note": "transcript walk failed; ccusage-only",
                "waste": [], "efficiency": []}

    # Waste = high cost + zero-or-negative outcome score, cost > $0.10 floor
    waste = sorted(
        [s for s in scored if s["score"] <= 0 and s["cost"] > 0.10],
        key=lambda x: -x["cost"],
    )[:top_n]
    # Efficiency = best outcome-per-dollar; require score > 0 and cost > $0.01
    eff_pool = [s for s in scored if s["score"] > 0 and s["cost"] > 0.01]
    for s in eff_pool:
        s["roi"] = s["score"] / max(s["cost"], 0.01)
    eff = sorted(eff_pool, key=lambda x: -x["roi"])[:top_n]

    return {
        "available": True,
        "note": "" if scored else "no sessions analyzed",
        "waste": waste,
        "efficiency": eff,
    }


def pull_upcoming(gcal_events: list, now: dt.datetime, max_n: int = 6) -> list[str]:
    today = now.date()
    out: list[str] = []
    for ev in gcal_events:
        if "_error" in ev:
            continue
        when = mb.parse_event_start(ev)
        if when is None or when.date() <= today:
            continue
        is_all_day = "date" in (ev.get("start") or {}) and "dateTime" not in (ev.get("start") or {})
        if is_all_day and mb.TRAVEL_RE.search(ev.get("summary") or ""):
            # Allow travel — surface explicitly with ✈
            tstr = when.strftime("%a (all day)")
            out.append(f"{tstr}  ✈ {(ev.get('summary') or '?')[:50]}")
            continue
        tstr = when.strftime("%a %-I:%M%p")
        out.append(f"{tstr}  {(ev.get('summary') or '?')[:50]}")
    return out[:max_n]


def healthy_footer_bits(opens, gate_lines, prs: dict, now: dt.datetime) -> list[str]:
    bits: list[str] = []
    if not opens:
        bits.append("0 open promises")
    else:
        old = sum(
            1 for p in opens
            if (now - dt.datetime.fromtimestamp(float(p.get("ts") or 0), PT)).days >= 3
        )
        bits.append(f"{len(opens)} promises ({old} stale)" if old else f"{len(opens)} promises clean")
    # Workstreams summary
    try:
        ws_state_path = Path.home() / ".claude/workstreams/state.json"
        if ws_state_path.exists():
            ws = json.loads(ws_state_path.read_text())
            workstreams = list(ws.get("workstreams", {}).values())
            hot = sum(1 for w in workstreams if w.get("bucket") == "hot" and not w.get("catchall"))
            if hot:
                bits.append(f"{hot} hot workstreams")
    except (OSError, json.JSONDecodeError):
        pass
    # PR cap
    cap = prs.get("cap", "?")
    if "/" in cap:
        try:
            used, total = (int(x) for x in cap.split("/"))
            bits.append(f"PR cap {used}/{total}")
        except ValueError:
            pass
    return bits


def derive_next_moves(lead: dict, autos: list[dict], blockers: list[dict]) -> list[str]:
    """Pick top 3 concrete steps. Lead first, then top autonomous, then top blocker."""
    out: list[str] = []
    out.append(lead["action"][:80])
    if autos:
        out.append(autos[0]["text"][:80])
    if blockers:
        out.append(blockers[0]["item"][:80])
    return out


def pull_async(prs: dict, overnight: list[dict], user_cache: dict, now: dt.datetime) -> list[str]:
    out: list[str] = []
    if prs["open"]:
        nums = ", ".join(f"#{p['num'].lstrip('#')}" for p in prs["open"][:3])
        out.append(f"Idan review on {nums}")
    for m in overnight[:2]:
        who = user_cache.get(m.get("user", ""), m.get("user", "?"))
        age = digest.slack_human_age(float(m["ts"]), now)
        snippet = digest.first_meaningful_line(m.get("text") or "", max_len=50)
        out.append(f"{who} ({age}): {snippet}")
    return out


# ────────────────────────────── main ──────────────────────────────

def collect_data(now: dt.datetime) -> dict:
    """Fan-out — call each source, collect into one dict for the renderer."""
    try:
        client = digest.slack_client()
        standup_msgs = digest.fetch_standup(client, days=5)
        user_cache = digest.build_user_cache(
            client, {m.get("user") for m in standup_msgs if m.get("user")}
        )
    except Exception:
        logger.warning("standup fetch failed\n%s", traceback.format_exc())
        standup_msgs, user_cache = [], {}

    try:
        matt_corpus = digest.fetch_promise_corpus(client, days=14)
        digest.extract_promises(matt_corpus)
    except Exception:
        pass

    try:
        gcal_events = digest.fetch_gcal_week()
    except Exception:
        gcal_events = []

    try:
        overnight = mb.fetch_overnight_signal(client, now)
    except Exception:
        overnight = []

    gate_lines = digest.render_pr_gate_status(now=now)
    todays_evs = mb.todays_meetings(gcal_events, now)
    opens = promise_state.open_promises()

    inbox_rows = pull_inbox_todo_rows(now)
    lead = pick_lead(now, gcal_events, gate_lines)
    blockers = classify_blockers(inbox_rows, lead["action"])
    prs = pull_pr_pipeline()
    gtm = pull_gtm_decisions(now)
    decision_queue = pull_decision_queue(now)
    pending_decisions = pull_pending_decisions(now)
    autos = autonomous_candidates(inbox_rows, gate_lines, prs["held"], gtm, lead)
    yest_lead = pull_yesterday_lead(now)
    yest_wins = pull_yesterday_wins(now, pr_data=prs)
    aspirational = pull_aspirational_launches(now)
    blog_queue = pull_blog_queue(now)
    focus = compute_focus_blocks(todays_evs, now)
    upcoming = pull_upcoming(gcal_events, now)
    async_items = pull_async(prs, overnight, user_cache, now)
    healthy = healthy_footer_bits(opens, gate_lines, prs, now)
    next_moves = derive_next_moves(lead, autos, blockers)
    workstreams = pull_workstreams()
    content_pipeline = pull_content_pipeline()
    content_perf = pull_content_performance(now)
    token_burn = pull_token_burn()
    cost_per_outcome = pull_cost_per_outcome()

    return {
        "now": now,
        "lead": lead,
        "blockers": blockers,
        "autonomous": autos,
        "gtm": gtm,
        "decision_queue": decision_queue,
        "pending_decisions": pending_decisions,
        "todays_meetings": todays_evs,
        "focus_blocks": focus,
        "prs": prs,
        "yesterday_lead": yest_lead,
        "yesterday_wins": yest_wins,
        "aspirational": aspirational,
        "blog_queue": blog_queue,
        "async": async_items,
        "upcoming": upcoming,
        "next_moves": next_moves,
        "healthy_footer": healthy,
        "workstreams": workstreams,
        "content_pipeline": content_pipeline,
        "content_perf": content_perf,
        "token_burn": token_burn,
        "cost_per_outcome": cost_per_outcome,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--compact", action="store_true",
                        help="render top 5 zones only (today + blocked + pr + content + next)")
    parser.add_argument("--zone", default=None,
                        help="render only listed zones — comma-separated. e.g. blocked,pr,content")
    parser.add_argument("--list-zones", action="store_true",
                        help="print available zone slugs + aliases and exit")
    args = parser.parse_args(argv)

    if args.list_zones:
        print("Zones:", ", ".join(sorted(ZONES_ALL)))
        print("Aliases:", ", ".join(f"{k}→{v}" for k, v in sorted(ZONE_ALIASES.items())))
        print("\nModes: --compact (= today,blocked,pr,content,next), default = all")
        return 0

    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )

    # Personal-data miners (Gmail diffs, iMessage promises) — fire-and-forget,
    # daily-gated inside the script. Authorized by Matt 2026-06-01: "morning
    # briefing trigger should run automatically each morning".
    try:
        import subprocess as _sp
        _sp.Popen(
            ["/usr/bin/python3", str(Path.home() / ".claude/hooks/personal_miners.py")],
            stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
        )
    except Exception:
        pass  # mining is never allowed to break the brief

    now = dt.datetime.now(PT)
    data = collect_data(now)

    if args.json:
        # Strip non-serializable items
        safe = dict(data)
        safe["now"] = data["now"].isoformat()
        safe["todays_meetings"] = [
            {"summary": e.get("summary"), "start": (e.get("start") or {})}
            for e in data["todays_meetings"]
        ]
        safe["focus_blocks"] = [
            {**b, "start": b["start"].isoformat(), "end": b["end"].isoformat()}
            for b in data["focus_blocks"]
        ]
        print(json.dumps(safe, indent=2, default=str))
        return 0

    zones_spec = None
    if args.zone:
        zones_spec = args.zone
    elif args.compact:
        zones_spec = "compact"
    print(render_dashboard(data, zones=zones_spec))

    # Effectiveness block — appended out-of-band so we don't disturb the
    # canonical zone grid. Reads cached scanner outputs from ~/.zerg/effectiveness/.
    # Step 7 of plans/what-are-gaps-in-velvety-ripple.md.
    _eff = Path.home() / ".config/zerg/morning_brief_effectiveness.py"
    if _eff.exists() and not (args.compact or args.zone):
        try:
            import subprocess as _sp
            r = _sp.run(["python3", str(_eff)], capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and r.stdout.strip():
                print()
                print(r.stdout.rstrip())
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
