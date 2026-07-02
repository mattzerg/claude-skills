#!/usr/bin/python3
"""triage — 4-section "blocked-by-Matt vs autonomous" snapshot.

Sibling to morning-brief: morning-brief is the daily firehose; triage is the
categorical filter — does this item need Matt's brain, or can Claude move it?

Read-only. Fans out to zpub, pr-table, workstreams show, inbox.md, zinflight.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from zoneinfo import ZoneInfo

PT = ZoneInfo("America/Los_Angeles")
HOME = Path.home()
VAULT = HOME / "Obsidian/Zerg"
VAULT_MIRROR = HOME / ".zerg-vault-writeback"
INBOX = "MattZerg/Tasks/inbox.md"

ZPUB = HOME / ".claude/skills/zpub/zpub.py"
PR_TABLE = HOME / ".claude/skills/pr-table/run.py"
WORKSTREAMS_SHOW = HOME / ".claude/skills/workstreams/commands/show.py"
REPAIR_LEDGER = HOME / ".claude/state/correction_repairs.jsonl"


@dataclass
class Item:
    title: str
    source: str          # zpub | pr | inbox | workstream
    detail: str = ""     # short hint, e.g. "signoff gate" or "behind 14"
    bucket: str = ""     # blocked_matt | autonomous_inflight | autonomous_queued | async_waiting


def _vault_path(rel: str) -> Path:
    primary = VAULT / rel
    mirror = VAULT_MIRROR / rel
    pm = primary.stat().st_mtime if primary.exists() else 0.0
    mm = mirror.stat().st_mtime if mirror.exists() else 0.0
    return mirror if mm > pm and mirror.exists() else primary


def _run(cmd: list[str], timeout: int = 20) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


# ─────────────────────────── data collectors ───────────────────────────


def collect_zpub() -> list[Item]:
    """Parse `zpub all` rows. State emoji + NEEDS column drive bucket choice."""
    out = _run(["/usr/bin/python3", str(ZPUB), "all"])
    items: list[Item] = []
    section = ""
    for line in out.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("IN FLIGHT"):
            section = "in_flight"; continue
        if s.startswith("PUBLISHING"):
            section = "publishing"; continue
        if s.startswith("BACKLOG"):
            section = "backlog"; continue
        # rows start with a status emoji (🟢🟡🟠🔴)
        if not s[:1] in ("🟢", "🟡", "🟠", "🔴"):
            continue
        # crude column split — fields separated by ≥2 spaces
        cols = re.split(r"\s{2,}", s)
        if len(cols) < 3:
            continue
        title = cols[-2] if len(cols) >= 3 else ""
        needs = cols[-1]
        if "LIVE" in needs or "archived" in needs:
            continue
        # classify
        nl = needs.lower()
        if "signoff" in nl:
            bucket = "blocked_matt"
            detail = "signoff gate"
        elif "matt has not confirmed" in nl or "founder calendar" in nl or "matt confirmed" in nl:
            bucket = "blocked_matt"
            detail = needs[:60]
        elif "awaiting idan" in nl or "neurips" in nl or "pending idan" in nl:
            bucket = "async_waiting"
            detail = needs[:60]
        elif "pr cap" in nl:
            bucket = "async_waiting"
            detail = "PR cap"
        elif "redo gate `imagery_quality`" in nl or "needs draft" in nl or "add a `MattZerg/Writing/<title>.md` surface" in nl:
            bucket = "autonomous_queued"
            detail = needs[:60]
        elif "phase a: hold" in nl:
            bucket = "async_waiting"
            detail = "Phase A hold"
        else:
            continue
        items.append(Item(title=title, source="zpub", detail=detail, bucket=bucket))
    return items


def collect_pr_table() -> list[Item]:
    """Parse pr-table output for open PRs + held branches."""
    out = _run(["/usr/bin/python3", str(PR_TABLE)], timeout=30)
    items: list[Item] = []
    repo = ""
    in_open = in_held = False
    for line in out.splitlines():
        s = line.strip()
        m = re.match(r"# PR pipeline — ([\w/\-]+)", s)
        if m:
            repo = m.group(1).split("/")[-1]
            in_open = in_held = False
            continue
        if s.startswith("## Open PRs"):
            in_open, in_held = True, False; continue
        if s.startswith("## Held local"):
            in_open, in_held = False, True; continue
        if s.startswith("## "):
            in_open = in_held = False; continue
        # table row?
        if not s.startswith("|") or s.startswith("|---") or s.startswith("| #") or s.startswith("| Branch"):
            continue
        cols = [c.strip() for c in s.split("|")[1:-1]]
        if in_open and len(cols) >= 5:
            num, title, state, reviews, ci = cols[:5]
            detail = f"{repo} {state} rev={reviews} ci={ci}"
            if "READY" in state and "approved" not in reviews.lower():
                items.append(Item(title=f"PR {num}: {title}", source="pr", detail=detail, bucket="async_waiting"))
            elif "BLOCKED" in state or "DRAFT" in state:
                items.append(Item(title=f"PR {num}: {title}", source="pr", detail=detail, bucket="async_waiting"))
        elif in_held and len(cols) >= 7:
            branch, surface, ahead, last, preflight, launch, blockers = cols[:7]
            # held branches are rebase candidates I can run autonomously
            items.append(Item(
                title=f"branch {branch}",
                source="pr",
                detail=f"{repo}/{surface} {ahead}, pre-flight {preflight}",
                bucket="autonomous_queued",
            ))
    return items


def collect_inbox() -> list[Item]:
    """Parse Matt's inbox.md for blocked + open TODOs. Handles bullet AND table rows."""
    p = _vault_path(INBOX)
    if not p.exists():
        return []
    try:
        txt = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    items: list[Item] = []
    for line in txt.splitlines():
        s = line.strip()
        # Bullet form: "- [TODO] Foo [blocked:matt-review]"
        # Table form:  "| 39 | Foo [blocked:matt-review] | Network | …"
        candidate = ""
        if s.startswith("- "):
            candidate = s[2:]
        elif s.startswith("|") and s.count("|") >= 3:
            cells = [c.strip() for c in s.split("|")[1:-1]]
            # Skip header/separator rows
            if cells and not all(c.startswith("---") or c.isdigit() or c == "" for c in cells):
                # Pick the longest cell that contains a `[blocked:` tag
                blocked_cells = [c for c in cells if "[blocked:" in c]
                if blocked_cells:
                    candidate = max(blocked_cells, key=len)
        if not candidate:
            continue
        clean = re.sub(r"\[blocked:[^\]]+\]", "", candidate).strip()
        if "[blocked:matt-review]" in candidate or "[blocked:matt]" in candidate:
            items.append(Item(title=clean[:80], source="inbox", detail="awaiting Matt review", bucket="blocked_matt"))
        elif "[blocked:idan]" in candidate:
            items.append(Item(title=clean[:80], source="inbox", detail="awaiting Idan", bucket="async_waiting"))
    return items


def collect_inflight() -> list[Item]:
    """Active sessions = autonomous in flight. zinflight is a shell alias →
    invoke its underlying script directly. NOTE: zinflight.py uses Python 3.10+
    union syntax so it must run on Homebrew python3 (per feedback_gui_path_resolution.md)."""
    zinflight_py = HOME / ".config/zerg/zinflight.py"
    if not zinflight_py.exists():
        return []
    py = "/opt/homebrew/bin/python3" if Path("/opt/homebrew/bin/python3").exists() else "python3"
    out = _run([py, str(zinflight_py), "--window", "120"], timeout=10)
    items: list[Item] = []
    for line in out.splitlines():
        m = re.match(r"\s*(\d+)m\s+([a-f0-9]{8})\s+(\S+)", line)
        if m:
            mins, sid, cwd = m.groups()
            items.append(Item(
                title=f"session {sid}",
                source="session",
                detail=f"{mins}m  {cwd[:40]}",
                bucket="autonomous_inflight",
            ))
    return items


SLACK_CORPUS_INDEX = HOME / ".claude/state/slack_corpus/_index.jsonl"
GH_CORPUS_INDEX = HOME / ".claude/state/gh_corpus/_index.jsonl"
CODEX_CORPUS_INDEX = HOME / ".claude/state/codex_corpus/_index.jsonl"
IDAN_SLACK = "U04R0EJACMR"
IDAN_GH = "idanbeck"


def collect_inbox_action_counts(max_items: int = 4) -> list[Item]:
    """Surface inbox-triage action-shape counts as a quick summary tile."""
    state = HOME / ".claude/state/inbox_triage.json"
    if not state.exists():
        return []
    try:
        r = json.loads(state.read_text())
    except Exception:
        return []
    counts = r.get("counts") or {}
    if not counts:
        return []
    items = []
    label_order = [
        ("action-required", "🔴 action-required"),
        ("reply-pending", "📨 reply-pending"),
        ("async-waiting", "⏳ async-waiting"),
        ("archive-candidate", "📦 archive-candidate"),
    ]
    for key, label in label_order[:max_items]:
        n = counts.get(key, 0)
        if n <= 0:
            continue
        items.append(Item(
            title=f"{label}: {n}",
            source="inbox",
            detail=f"of {r.get('total_rows', '?')} inbox rows",
            bucket="inbox_summary",
        ))
    return items


def collect_stale_prs(max_items: int = 5) -> list[Item]:
    """Pull stale-PR report — PRs waiting > 24h on Idan/external review."""
    report_path = HOME / ".claude/state/pr_staleness.json"
    if not report_path.exists():
        return []
    try:
        r = json.loads(report_path.read_text())
    except Exception:
        return []
    items = []
    for s in r.get("stale", [])[:max_items]:
        idan = "Idan: " + (s.get("last_idan_comment") or "never")[:10]
        items.append(Item(
            title=f"PR {s.get('repo')}#{s.get('pr')}: {(s.get('title') or '')[:60]}",
            source="stale-pr",
            detail=f"{s.get('age_hours', '?')}h stale · {idan}",
            bucket="async_waiting",
        ))
    return items


def collect_idea_freshness(max_items: int = 5) -> list[Item]:
    """Top ideas heating up across corpora — from idea_freshness_scorer.py."""
    # iCloud `Downloads` can transiently raise InterruptedError [Errno 4] when
    # the system call is preempted (file provider scanning, etc.). Treat any
    # filesystem hiccup as "no data" rather than crashing the entire /triage view.
    try:
        candidates = sorted((HOME / "Downloads").glob("idea-freshness-*.md"), reverse=True)
    except (OSError, InterruptedError):
        return []
    if not candidates:
        return []
    path = candidates[0]
    try:
        age_h = (dt.datetime.now().timestamp() - path.stat().st_mtime) / 3600
    except (OSError, InterruptedError):
        return []
    if age_h > 36:
        return []
    items = []
    try:
        txt = path.read_text(errors="ignore")
        for line in txt.splitlines():
            m = re.match(r"^### (\d+)\. (.+?)\s+·\s+score (\d+(?:\.\d+)?)", line)
            if m and int(m.group(1)) <= max_items:
                items.append(Item(
                    title=m.group(2)[:70],
                    source="idea",
                    detail=f"score {m.group(3)}",
                    bucket="idea_freshness",
                ))
    except (OSError, InterruptedError):
        pass
    return items


def collect_codex_recent(days: int = 3, max_items: int = 6) -> list[Item]:
    """Pull recent Codex sessions — cross-LLM signal. What's the other model doing?"""
    if not CODEX_CORPUS_INDEX.exists():
        return []
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=days)
    items: list[Item] = []
    try:
        for line in CODEX_CORPUS_INDEX.read_text(errors="ignore").splitlines():
            try:
                r = json.loads(line)
            except Exception:
                continue
            ts = r.get("ts") or ""
            try:
                tm = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except Exception:
                continue
            if tm < cutoff:
                continue
            cwd = (r.get("cwd") or "").replace(str(HOME), "~")
            msg = (r.get("first_msg") or "")[:90].replace("\n", " ")
            items.append(Item(
                title=f"{cwd[-45:]} — {msg}",
                source="codex",
                detail=tm.strftime("%m-%d %H:%M"),
                bucket="codex_signal",
            ))
    except OSError:
        return []
    items.sort(key=lambda x: x.detail, reverse=True)
    return items[:max_items]


def collect_idan_recent(days: int = 7, max_items: int = 6) -> list[Item]:
    """Pull recent real-Idan signal from the local corpora — context cue, not a bucket."""
    cutoff_unix = (dt.datetime.now() - dt.timedelta(days=days)).timestamp()
    import re as _re
    fake = _re.compile(r"\[fake idan\]", _re.I)
    items: list[Item] = []
    if SLACK_CORPUS_INDEX.exists():
        for line in SLACK_CORPUS_INDEX.read_text(errors="ignore").splitlines():
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("user_id") != IDAN_SLACK:
                continue
            try:
                ts_f = float(r.get("ts", "0"))
            except Exception:
                continue
            if ts_f < cutoff_unix:
                continue
            snippet = r.get("snippet", "")
            if not snippet or fake.search(snippet):
                continue
            items.append(Item(
                title=f"#{r.get('channel')} — {snippet}",
                source="idan",
                detail=dt.datetime.fromtimestamp(ts_f).strftime("%m-%d %H:%M"),
                bucket="idan_signal",
            ))
    if GH_CORPUS_INDEX.exists():
        cutoff_iso = (dt.datetime.now() - dt.timedelta(days=days)).isoformat()
        for line in GH_CORPUS_INDEX.read_text(errors="ignore").splitlines():
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("author") != IDAN_GH:
                continue
            ts = r.get("ts") or ""
            if ts < cutoff_iso:
                continue
            snippet = r.get("snippet", "")
            if not snippet or fake.search(snippet):
                continue
            items.append(Item(
                title=f"{r.get('repo')}#{r.get('pr')} — {snippet}",
                source="idan",
                detail=ts[:10],
                bucket="idan_signal",
            ))
    # Dedup by title (corpus may have duplicate rows from earlier ingest runs
    # before user_name field stabilized)
    seen: set[str] = set()
    deduped: list[Item] = []
    for it in items:
        key = it.title[:60]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(it)
    # newest first
    deduped.sort(key=lambda x: x.detail, reverse=True)
    return deduped[:max_items]


def collect_loop_repairs() -> list[Item]:
    """Recent repair-ledger entries = closed-loop activity (informational)."""
    if not REPAIR_LEDGER.exists():
        return []
    cutoff = dt.datetime.now(PT) - dt.timedelta(days=2)
    items: list[Item] = []
    for line in REPAIR_LEDGER.read_text(errors="ignore").splitlines()[-30:]:
        try:
            rec = json.loads(line)
            ts = dt.datetime.fromisoformat(rec["ts"].replace("Z", "+00:00")).astimezone(PT)
            if ts >= cutoff:
                files = ", ".join(Path(f).name for f in rec.get("repair_files", [])[:2])
                items.append(Item(
                    title=f"repair: {rec.get('repair_class', '?')}",
                    source="loop",
                    detail=files,
                    bucket="autonomous_inflight",
                ))
        except Exception:
            continue
    return items


# ─────────────────────────── rendering ───────────────────────────

BOX_W = 78


def _box_top(title: str) -> str:
    inner = f" {title} "
    return f"╔{'═' * (BOX_W - 2)}╗\n║{inner.ljust(BOX_W - 2)}║\n╠{'═' * (BOX_W - 2)}╣"


def _box_bot() -> str:
    return f"╚{'═' * (BOX_W - 2)}╝"


def _line(text: str) -> str:
    text = text[:BOX_W - 4]
    return f"║ {text.ljust(BOX_W - 4)} ║"


def render(items: list[Item], as_json: bool = False) -> str:
    by_bucket: dict[str, list[Item]] = {
        "blocked_matt": [],
        "autonomous_inflight": [],
        "autonomous_queued": [],
        "async_waiting": [],
        "idan_signal": [],
        "codex_signal": [],
        "idea_freshness": [],
        "inbox_summary": [],
    }
    for it in items:
        if it.bucket in by_bucket:
            by_bucket[it.bucket].append(it)

    if as_json:
        return json.dumps({k: [asdict(i) for i in v] for k, v in by_bucket.items()}, indent=2)

    sections = [
        ("🔴 BLOCKED BY YOU", "blocked_matt", 10),
        ("🟢 AUTONOMOUS — IN FLIGHT (mine)", "autonomous_inflight", 8),
        ("🟡 AUTONOMOUS — QUEUED (yours to greenlight)", "autonomous_queued", 12),
        ("⏳ ASYNC-WAITING (counterparties)", "async_waiting", 10),
        ("📡 IDAN SIGNAL — last 7d (corpus-grep)", "idan_signal", 6),
        ("🤖 CODEX SIGNAL — last 3d (other-LLM-in-stack)", "codex_signal", 6),
        ("💡 IDEAS HEATING UP — last 7d (corpus-matched)", "idea_freshness", 5),
        ("📥 INBOX SHAPE — auto-classified", "inbox_summary", 4),
    ]
    now = dt.datetime.now(PT).strftime("%a %Y-%m-%d %H:%M PT")
    lines: list[str] = [f"# /triage — {now}", ""]
    for title, key, cap in sections:
        bucket_items = by_bucket[key][:cap]
        total = len(by_bucket[key])
        header = f"{title}  ({total})"
        lines.append(_box_top(header))
        if not bucket_items:
            lines.append(_line("(empty)"))
        else:
            for it in bucket_items:
                src = f"[{it.source}]"
                detail = f" — {it.detail}" if it.detail else ""
                lines.append(_line(f"{src} {it.title}{detail}"))
            if total > cap:
                lines.append(_line(f"… +{total - cap} more"))
        lines.append(_box_bot())
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    items: list[Item] = []
    items += collect_zpub()
    items += collect_pr_table()
    items += collect_inbox()
    items += collect_inflight()
    items += collect_loop_repairs()
    items += collect_idan_recent()
    items += collect_codex_recent()
    items += collect_stale_prs()
    items += collect_idea_freshness()
    items += collect_inbox_action_counts()

    print(render(items, as_json=args.json))
    return 0


if __name__ == "__main__":
    sys.exit(main())
