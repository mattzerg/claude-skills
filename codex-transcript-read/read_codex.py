#!/usr/bin/env python3
"""Read Codex CLI session transcripts from ~/.codex/sessions/."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

SESSIONS_ROOT = Path.home() / ".codex" / "sessions"


def iter_session_files():
    if not SESSIONS_ROOT.exists():
        return
    for p in SESSIONS_ROOT.rglob("rollout-*.jsonl"):
        yield p


def parse_session(path: Path) -> dict | None:
    """Return {ts, session_id, cwd, msg_count, first_user_text, path} or None on parse failure."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except OSError:
        return None
    if not lines:
        return None
    meta = None
    first_user_text = None
    msg_count = 0
    for line in lines:
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
            msg_count += 1
            if first_user_text is None:
                text = (
                    payload.get("text")
                    or payload.get("content")
                    or payload.get("message")
                    or ""
                )
                if isinstance(text, list):
                    text = " ".join(
                        seg.get("text", "") if isinstance(seg, dict) else str(seg)
                        for seg in text
                    )
                if isinstance(text, str) and text.strip():
                    s = text.strip()
                    if (
                        s.startswith("# AGENTS.md")
                        or s.startswith("<environment_context>")
                        or s.startswith("<INSTRUCTIONS>")
                    ):
                        continue
                    first_user_text = s
    if meta is None:
        return None
    return {
        "ts": meta.get("timestamp") or row.get("timestamp"),
        "session_id": meta.get("id", ""),
        "cwd": meta.get("cwd", ""),
        "msg_count": msg_count,
        "first_user_text": first_user_text or "",
        "path": str(path),
    }


def parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def truncate(s: str, n: int = 100) -> str:
    s = " ".join(s.split())
    return s if len(s) <= n else s[: n - 1] + "…"


def short_id(sid: str) -> str:
    return sid.split("-", 1)[0] if sid else "?"


def cmd_recent(hours: int, slug_filter: str | None = None) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    rows: list[dict] = []
    for p in iter_session_files():
        s = parse_session(p)
        if not s:
            continue
        ts = parse_ts(s["ts"])
        if not ts:
            continue
        if ts < cutoff:
            continue
        if slug_filter and slug_filter.lower() not in s["cwd"].lower():
            continue
        rows.append({**s, "_ts": ts})
    rows.sort(key=lambda r: r["_ts"], reverse=True)
    if not rows:
        scope = f" matching '{slug_filter}'" if slug_filter else ""
        print(f"(no Codex sessions in last {hours}h{scope})")
        return 0
    for r in rows:
        ts_local = r["_ts"].astimezone().strftime("%Y-%m-%d %H:%M")
        print(
            f"[{ts_local}] {short_id(r['session_id'])}  "
            f"cwd={r['cwd']}  msgs={r['msg_count']}  "
            f'first="{truncate(r["first_user_text"])}"'
        )
    return 0


def cmd_show(session_prefix: str) -> int:
    for p in iter_session_files():
        if session_prefix in p.name:
            print(f"# {p}")
            with p.open("r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    payload = row.get("payload") or {}
                    role = payload.get("role")
                    if role == "user" or row.get("type") in {"user_message"}:
                        text = payload.get("text") or payload.get("content") or ""
                        if isinstance(text, list):
                            text = " ".join(
                                seg.get("text", "") if isinstance(seg, dict) else str(seg)
                                for seg in text
                            )
                        ts = row.get("timestamp", "")
                        print(f"\n--- USER [{ts}] ---")
                        print(text)
            return 0
    print(f"(no session matching '{session_prefix}')", file=sys.stderr)
    return 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="read_codex")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_recent = sub.add_parser("recent", help="list sessions in last N hours")
    p_recent.add_argument("--hours", type=int, default=24)

    p_slug = sub.add_parser("for-slug", help="filter sessions by cwd substring")
    p_slug.add_argument("slug")
    p_slug.add_argument("--hours", type=int, default=72)

    p_show = sub.add_parser("show", help="dump user turns of one session")
    p_show.add_argument("session_id")

    args = ap.parse_args(argv)

    if args.cmd == "recent":
        return cmd_recent(args.hours)
    if args.cmd == "for-slug":
        return cmd_recent(args.hours, slug_filter=args.slug)
    if args.cmd == "show":
        return cmd_show(args.session_id)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
