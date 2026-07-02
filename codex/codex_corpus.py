#!/usr/bin/env python3
"""codex_corpus — local searchable corpus over Codex CLI sessions.

Phase 7 vector 3 of ~/.claude/plans/how-can-we-make-ticklish-quilt.md.

Sibling to slack_corpus.py and gh_corpus.py. Reads
~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl, extracts per-session metadata
+ first user message + tool-use surface, writes to a flat searchable corpus.

Why: codex-transcript-read exists for one-off pulls, but nothing aggregates
or makes the corpus searchable. The /triage Idan-signal section is great;
we want a sibling "what was Codex working on?" view to catch cross-LLM
conflicts before they become corrections.

Layout
------
~/.claude/state/codex_corpus/
    <YYYY-MM>.jsonl          — one line per session, sorted by ts
    _index.jsonl             — flat {ts, session_id, cwd, first_msg, msg_count} per session
    _meta.json               — last_pull_at

Run modes
---------
  codex_corpus.py backfill [--days 30]
  codex_corpus.py update                       — incremental, only sessions not yet in index
  codex_corpus.py search TERM [--cwd <substr>] [--since YYYY-MM-DD]
  codex_corpus.py recent [--hours 24]
  codex_corpus.py stats

Read-only. Idempotent (re-runs skip sessions already in index).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

HOME = Path.home()
SESSIONS_ROOT = HOME / ".codex/sessions"
CORPUS = HOME / ".claude/state/codex_corpus"
INDEX = CORPUS / "_index.jsonl"
META = CORPUS / "_meta.json"


def iter_session_files() -> list[Path]:
    if not SESSIONS_ROOT.exists():
        return []
    return sorted(SESSIONS_ROOT.rglob("rollout-*.jsonl"))


def parse_session(path: Path) -> dict | None:
    """Return {session_id, ts, cwd, first_msg, msg_count, model_provider, originator, file}."""
    meta = None
    first_msg: str | None = None
    msg_count = 0
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                rtype = row.get("type")
                payload = row.get("payload") or {}
                if rtype == "session_meta" and meta is None:
                    meta = payload
                if rtype in {"event_msg", "message", "user_message"} or payload.get("role") == "user":
                    text = (
                        payload.get("text")
                        or payload.get("content")
                        or payload.get("message")
                        or ""
                    )
                    if isinstance(text, list):
                        text = " ".join(
                            (x.get("text") or "") for x in text if isinstance(x, dict)
                        )
                    if not isinstance(text, str):
                        text = str(text)
                    if text.strip() and first_msg is None:
                        first_msg = text.strip()[:200]
                    msg_count += 1
    except OSError:
        return None
    if not meta:
        return None
    return {
        "session_id": meta.get("id", path.stem),
        "ts": meta.get("timestamp", ""),
        "cwd": meta.get("cwd", ""),
        "originator": meta.get("originator", ""),
        "model_provider": meta.get("model_provider", ""),
        "first_msg": first_msg or "(no user message captured)",
        "msg_count": msg_count,
        "file": str(path),
    }


def short_id(sid: str) -> str:
    return (sid or "?")[:8]


def load_meta() -> dict:
    if META.exists():
        try:
            return json.loads(META.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_meta(meta: dict) -> None:
    META.parent.mkdir(parents=True, exist_ok=True)
    META.write_text(json.dumps(meta, indent=2))


def existing_session_ids() -> set[str]:
    if not INDEX.exists():
        return set()
    out: set[str] = set()
    for line in INDEX.read_text(errors="ignore").splitlines():
        try:
            r = json.loads(line)
            sid = r.get("session_id")
            if sid:
                out.add(sid)
        except json.JSONDecodeError:
            continue
    return out


def write_session(entry: dict) -> None:
    CORPUS.mkdir(parents=True, exist_ok=True)
    # Per-month JSONL
    ts = entry.get("ts") or ""
    try:
        ym = dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%Y-%m")
    except Exception:
        ym = "unknown"
    month_path = CORPUS / f"{ym}.jsonl"
    with month_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    # Flat index
    idx_row = {
        "ts": ts,
        "session_id": entry["session_id"],
        "cwd": entry["cwd"],
        "first_msg": entry["first_msg"][:120],
        "msg_count": entry["msg_count"],
        "originator": entry.get("originator", ""),
    }
    with INDEX.open("a", encoding="utf-8") as f:
        f.write(json.dumps(idx_row, ensure_ascii=False) + "\n")


def cmd_backfill(args) -> int:
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.days)
    existing = existing_session_ids()
    files = iter_session_files()
    sys.stderr.write(f"[codex_corpus] {len(files)} session files; cutoff {cutoff.isoformat()}\n")
    added = 0
    skipped = 0
    for path in files:
        # Heuristic skip: filename embeds ts at YYYY-MM-DDTHH-MM-SS
        m = re.search(r"rollout-(\d{4}-\d{2}-\d{2})T", path.name)
        if m:
            try:
                d = dt.datetime.fromisoformat(m.group(1))
                if d < cutoff.replace(tzinfo=None):
                    continue
            except Exception:
                pass
        entry = parse_session(path)
        if not entry:
            continue
        if entry["session_id"] in existing:
            skipped += 1
            continue
        write_session(entry)
        existing.add(entry["session_id"])
        added += 1
    meta = load_meta()
    meta["last_pull_at"] = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
    meta["total_sessions"] = len(existing)
    save_meta(meta)
    print(f"[codex_corpus] +{added} new sessions ({skipped} skipped) → corpus total {len(existing)}")
    return 0


def cmd_update(args) -> int:
    args.days = 7
    return cmd_backfill(args)


def cmd_search(args) -> int:
    if not INDEX.exists():
        print("[codex_corpus] no index — run backfill first")
        return 1
    term = (args.term or "").lower()
    cwd_filter = (args.cwd or "").lower()
    since = None
    if args.since:
        try:
            since = dt.datetime.fromisoformat(args.since)
        except ValueError:
            print(f"bad --since: {args.since}")
            return 1
    matches = 0
    for line in INDEX.read_text(errors="ignore").splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        haystack = " ".join([r.get("cwd", ""), r.get("first_msg", "")]).lower()
        if term and term not in haystack:
            continue
        if cwd_filter and cwd_filter not in r.get("cwd", "").lower():
            continue
        if since:
            try:
                tm = dt.datetime.fromisoformat(r["ts"].replace("Z", "+00:00")).replace(tzinfo=None)
                if tm < since:
                    continue
            except Exception:
                continue
        ts_s = (r.get("ts") or "?")[:16]
        sid = short_id(r.get("session_id"))
        cwd = (r.get("cwd") or "?").replace(str(HOME), "~")[-40:]
        msg = (r.get("first_msg") or "")[:80]
        print(f"{ts_s}  {sid}  {cwd:40}  msgs={r.get('msg_count',0):3}  {msg}")
        matches += 1
        if matches >= (args.limit or 30):
            break
    print(f"\n[codex_corpus] {matches} match(es)", file=sys.stderr)
    return 0


def cmd_recent(args) -> int:
    if not INDEX.exists():
        print("(empty)")
        return 0
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=args.hours)
    rows = []
    for line in INDEX.read_text(errors="ignore").splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            tm = dt.datetime.fromisoformat(r["ts"].replace("Z", "+00:00"))
            if tm < cutoff:
                continue
        except Exception:
            continue
        rows.append(r)
    rows.sort(key=lambda r: r.get("ts", ""), reverse=True)
    print(f"# codex sessions in last {args.hours}h — {len(rows)} total")
    for r in rows[: args.limit or 20]:
        ts_s = (r.get("ts") or "?")[:16]
        sid = short_id(r.get("session_id"))
        cwd = (r.get("cwd") or "?").replace(str(HOME), "~")[-50:]
        msg = (r.get("first_msg") or "")[:80]
        print(f"{ts_s}  {sid}  {cwd:50}  {msg}")
    return 0


def cmd_stats(args) -> int:
    meta = load_meta()
    if not meta:
        print("(empty — run backfill)")
        return 0
    print(f"total sessions: {meta.get('total_sessions', '?')}")
    print(f"last pull: {meta.get('last_pull_at', '?')}")
    if CORPUS.exists():
        months = sorted(CORPUS.glob("*.jsonl"))
        print(f"month files: {len(months)}")
        for m in months[-6:]:
            count = sum(1 for _ in m.open())
            print(f"  {m.name:20}  {count}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd")

    bf = sub.add_parser("backfill")
    bf.add_argument("--days", type=int, default=30)
    bf.set_defaults(func=cmd_backfill)

    up = sub.add_parser("update")
    up.set_defaults(func=cmd_update)

    s = sub.add_parser("search")
    s.add_argument("term")
    s.add_argument("--cwd")
    s.add_argument("--since")
    s.add_argument("--limit", type=int, default=30)
    s.set_defaults(func=cmd_search)

    r = sub.add_parser("recent")
    r.add_argument("--hours", type=int, default=24)
    r.add_argument("--limit", type=int, default=20)
    r.set_defaults(func=cmd_recent)

    st = sub.add_parser("stats")
    st.set_defaults(func=cmd_stats)

    args = p.parse_args()
    if not getattr(args, "func", None):
        p.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
