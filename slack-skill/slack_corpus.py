#!/usr/bin/env python3
"""slack_corpus — backfill Slack history into a local searchable corpus.

Phase 6.A of ~/.claude/plans/how-can-we-make-ticklish-quilt.md.

Why: Idan, Matt, Andre, and the team have months of real conversations in
Slack that capture decisions, voice, concerns, and history. We want this
locally indexed so fakeidan + future analysis can ground on real data
(today's GitHub PR-comment ingest came up dry because Matt operates the
idanbeck account; Slack is the actual gold mine).

Layout
------
~/.claude/state/slack_corpus/
    <channel-name>/
        <YYYY-MM>.jsonl     — one line per message in that month
        threads/
            <thread_ts>.jsonl  — thread replies (only fetched with --threads)
    _index.jsonl            — flat {ts, channel, user_id, snippet} per line
    _meta.json              — last_pull_ts per channel for incremental updates

Each message line: full Slack message dict, augmented with `channel_name`
and `year_month`.

Run modes
---------
  slack_corpus.py backfill [--months 12] [--channels all|c1,c2,...] [--threads]
  slack_corpus.py update                          # incremental, only new since last pull
  slack_corpus.py search TERM [--user idan] [--channel dev] [--since YYYY-MM-DD]
  slack_corpus.py stats                           # corpus size by channel/month

Rate limit aware. Idempotent (won't re-pull what already exists).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterator

HOME = Path.home()
CORPUS = HOME / ".claude/state/slack_corpus"
INDEX = CORPUS / "_index.jsonl"
META = CORPUS / "_meta.json"
SLACK_SKILL = HOME / ".claude/skills/slack-skill/slack_skill.py"

# Default high-signal channel set. Get the full list via `slack_skill.py channels`.
DEFAULT_CHANNELS = [
    "dev", "dev_git", "andesite-internal", "growzth", "math-sci-topics",
    "lobby", "marketing", "general-not-used", "design", "memes-and-marketing",
    "easy-listening", "for-the-lulz", "durable-zerg", "cesium-astro-internal",
    "cve", "dmatrix-internal", "durable-internal", "gameloft-internal",
]


def _slack(args: list[str], timeout: int = 30) -> dict | None:
    try:
        r = subprocess.run(
            ["/usr/bin/python3", str(SLACK_SKILL), *args],
            capture_output=True, text=True, timeout=timeout,
        )
        return json.loads(r.stdout) if r.stdout else None
    except Exception as e:
        sys.stderr.write(f"[slack_corpus] slack-skill call failed: {e}\n")
        return None


def ts_to_yearmonth(ts: str) -> str:
    try:
        d = dt.datetime.fromtimestamp(float(ts), tz=dt.timezone.utc)
        return d.strftime("%Y-%m")
    except (ValueError, TypeError):
        return "unknown"


def list_channels() -> list[dict]:
    out = _slack(["channels"], timeout=30)
    if not isinstance(out, dict):
        return []
    return out.get("channels", [])


def page_channel(channel: str, oldest_ts: str, threads: bool = False) -> Iterator[list[dict]]:
    """Yield batches of messages from `channel`, oldest first, until exhausted.

    `oldest_ts` is a unix timestamp string (epoch.fraction). Each yielded
    batch is a list of message dicts (Slack format augmented by slack-skill).
    """
    cursor = ""
    page = 0
    while True:
        args = ["read", channel, "--oldest", oldest_ts, "-l", "200", "--as-user"]
        if cursor:
            args += ["--cursor", cursor]
        out = _slack(args, timeout=45)
        if not isinstance(out, dict):
            sys.stderr.write(f"[slack_corpus] {channel}: page {page} returned non-dict; stopping\n")
            return
        if "error" in out:
            err = out["error"]
            # Benign: the bot/user can't see this channel (archived, renamed, or not
            # a member). Skip quietly instead of logging an error line every run.
            # Re-inviting the bot or pruning DEFAULT_CHANNELS is a manual fix.
            if err in ("channel_not_found", "not_in_channel"):
                sys.stderr.write(f"[slack_corpus] {channel}: skipping ({err})\n")
            else:
                sys.stderr.write(f"[slack_corpus] {channel}: error: {err}\n")
            return
        msgs = out.get("messages", []) or []
        page += 1
        if msgs:
            yield msgs
        if not out.get("has_more") or not out.get("next_cursor"):
            return
        cursor = out["next_cursor"]
        # Slack rate-limit-friendly pause
        time.sleep(0.5)


def write_messages(channel: str, msgs: list[dict]) -> tuple[int, dict[str, int]]:
    """Append messages to per-month jsonl files. Returns (written, per_month_counts).
    Idempotent: drops messages whose ts already exists in the destination file."""
    per_month: dict[str, int] = {}
    written = 0
    chan_dir = CORPUS / channel
    chan_dir.mkdir(parents=True, exist_ok=True)
    # Group by year-month
    by_ym: dict[str, list[dict]] = {}
    for m in msgs:
        ym = ts_to_yearmonth(m.get("ts", ""))
        by_ym.setdefault(ym, []).append(m)
    for ym, batch in by_ym.items():
        path = chan_dir / f"{ym}.jsonl"
        existing_ts: set[str] = set()
        if path.exists():
            for line in path.read_text(errors="ignore").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    existing_ts.add(json.loads(line).get("ts", ""))
                except json.JSONDecodeError:
                    continue
        new_lines = []
        for m in batch:
            if m.get("ts") in existing_ts:
                continue
            m_out = {**m, "channel_name": channel, "year_month": ym}
            new_lines.append(json.dumps(m_out, ensure_ascii=False))
            written += 1
        if new_lines:
            with path.open("a", encoding="utf-8") as f:
                f.write("\n".join(new_lines) + "\n")
            per_month[ym] = per_month.get(ym, 0) + len(new_lines)
    return written, per_month


def update_index(channel: str, msgs: list[dict]) -> None:
    """Append flat index rows for fast scanning."""
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for m in msgs:
        snippet = (m.get("text") or "").replace("\n", " ").strip()[:80]
        lines.append(json.dumps({
            "ts": m.get("ts"),
            "channel": channel,
            "user_id": m.get("user_id") or m.get("user"),
            "user_name": m.get("user") if m.get("user_id") else "",
            "snippet": snippet,
        }))
    if lines:
        with INDEX.open("a", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")


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


def cmd_backfill(args) -> int:
    CORPUS.mkdir(parents=True, exist_ok=True)
    if args.channels == "all":
        channels = [c["name"] for c in list_channels() if c.get("name")]
        sys.stderr.write(f"[slack_corpus] backfilling ALL {len(channels)} channels\n")
    else:
        channels = [c.strip().lstrip("#") for c in args.channels.split(",") if c.strip()]
    cutoff_dt = dt.datetime.now() - dt.timedelta(days=args.months * 30)
    oldest_ts = f"{cutoff_dt.timestamp():.6f}"
    sys.stderr.write(f"[slack_corpus] cutoff = {cutoff_dt.isoformat()} (ts={oldest_ts})\n")

    meta = load_meta()
    total_written = 0
    for ch in channels:
        sys.stderr.write(f"[slack_corpus] {ch}: starting backfill...\n")
        ch_written = 0
        ch_per_month: dict[str, int] = {}
        max_seen_ts = "0"
        for batch in page_channel(ch, oldest_ts, threads=args.threads):
            written, per_month = write_messages(ch, batch)
            update_index(ch, batch)
            ch_written += written
            for ym, n in per_month.items():
                ch_per_month[ym] = ch_per_month.get(ym, 0) + n
            for m in batch:
                if m.get("ts", "0") > max_seen_ts:
                    max_seen_ts = m["ts"]
            sys.stderr.write(f"[slack_corpus]   {ch}: +{written} (running {ch_written}), batch_max_ts={batch[-1].get('ts','?')}\n")
            if args.cap and ch_written >= args.cap:
                sys.stderr.write(f"[slack_corpus]   {ch}: hit cap {args.cap}, stopping\n")
                break
        meta[ch] = {
            "last_pull_ts": max_seen_ts,
            "last_pull_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
            "per_month": ch_per_month,
            "total_messages": ch_written + meta.get(ch, {}).get("total_messages", 0),
        }
        save_meta(meta)
        total_written += ch_written
        sys.stderr.write(f"[slack_corpus] {ch}: DONE +{ch_written} messages\n")

    print(f"[slack_corpus] backfill complete: +{total_written} new messages across {len(channels)} channels")
    return 0


def cmd_update(args) -> int:
    """Incremental: for each channel, pull anything newer than last_pull_ts in meta."""
    meta = load_meta()
    if not meta:
        sys.stderr.write("[slack_corpus] no prior backfill — run `backfill` first\n")
        return 1
    total_written = 0
    for ch, info in meta.items():
        oldest_ts = info.get("last_pull_ts") or "0"
        sys.stderr.write(f"[slack_corpus] {ch}: incremental from ts={oldest_ts}\n")
        ch_written = 0
        max_seen_ts = oldest_ts
        for batch in page_channel(ch, oldest_ts):
            # Skip the one message at exactly oldest_ts (the boundary)
            batch = [m for m in batch if m.get("ts", "0") > oldest_ts]
            if not batch:
                continue
            written, _ = write_messages(ch, batch)
            update_index(ch, batch)
            ch_written += written
            for m in batch:
                if m.get("ts", "0") > max_seen_ts:
                    max_seen_ts = m["ts"]
        if ch_written:
            meta[ch]["last_pull_ts"] = max_seen_ts
            meta[ch]["last_pull_at"] = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")
            meta[ch]["total_messages"] = info.get("total_messages", 0) + ch_written
            save_meta(meta)
        total_written += ch_written
        sys.stderr.write(f"[slack_corpus] {ch}: +{ch_written} new\n")
    print(f"[slack_corpus] update complete: +{total_written} new messages")
    return 0


def cmd_search(args) -> int:
    if not INDEX.exists():
        sys.stderr.write("[slack_corpus] no index — run `backfill` first\n")
        return 1
    term = args.term.lower()
    user_filter = args.user
    channel_filter = args.channel
    since_dt = None
    if args.since:
        try:
            since_dt = dt.datetime.fromisoformat(args.since)
        except ValueError:
            sys.stderr.write(f"[slack_corpus] bad --since: {args.since}\n")
            return 1

    matches = 0
    for line in INDEX.read_text(errors="ignore").splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if term and term not in (r.get("snippet") or "").lower():
            continue
        if user_filter:
            uf = user_filter.lower()
            if uf not in (r.get("user_id", "") or "").lower() and uf not in (r.get("user_name", "") or "").lower():
                continue
        if channel_filter and r.get("channel") != channel_filter:
            continue
        if since_dt:
            try:
                tm = dt.datetime.fromtimestamp(float(r["ts"]))
                if tm < since_dt:
                    continue
            except (ValueError, TypeError):
                continue
        ts_str = ""
        try:
            ts_str = dt.datetime.fromtimestamp(float(r["ts"])).strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            pass
        who = (r.get("user_name") or r.get("user_id") or "?")[:16]
        print(f"{ts_str}  #{r.get('channel'):20}  {who:16}  {r.get('snippet')}")
        matches += 1
        if matches >= (args.limit or 50):
            break
    print(f"\n[slack_corpus] {matches} match(es)", file=sys.stderr)
    return 0


def cmd_stats(args) -> int:
    meta = load_meta()
    if not meta:
        print("(empty — run backfill)")
        return 0
    total_msgs = 0
    print(f"{'channel':25}  {'messages':>9}  {'months':>7}  {'last_pull_at'}")
    print("-" * 80)
    for ch, info in sorted(meta.items(), key=lambda x: -x[1].get("total_messages", 0)):
        n = info.get("total_messages", 0)
        months = len(info.get("per_month", {}))
        total_msgs += n
        print(f"{ch:25}  {n:>9}  {months:>7}  {info.get('last_pull_at', '?')}")
    print("-" * 80)
    print(f"{'TOTAL':25}  {total_msgs:>9}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd")

    bf = sub.add_parser("backfill")
    bf.add_argument("--months", type=int, default=12)
    bf.add_argument("--channels", default=",".join(DEFAULT_CHANNELS))
    bf.add_argument("--cap", type=int, default=0, help="max messages per channel (0 = unlimited)")
    bf.add_argument("--threads", action="store_true", help="also pull thread replies (TODO)")
    bf.set_defaults(func=cmd_backfill)

    up = sub.add_parser("update")
    up.set_defaults(func=cmd_update)

    s = sub.add_parser("search")
    s.add_argument("term")
    s.add_argument("--user")
    s.add_argument("--channel")
    s.add_argument("--since")
    s.add_argument("--limit", type=int, default=50)
    s.set_defaults(func=cmd_search)

    st = sub.add_parser("stats")
    st.set_defaults(func=cmd_stats)

    args = p.parse_args()
    if not getattr(args, "func", None):
        p.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
