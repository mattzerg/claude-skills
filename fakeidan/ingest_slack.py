#!/usr/bin/env python3
"""fakeidan/ingest_slack — pull Idan's actual Slack messages + extract patterns.

Phase 5 vector 1b — companion to `ingest_recent.py`. GitHub PR comments turned
out to be dry (Matt operates idanbeck and posts [fake idan] paste-backs), so
the real-Idan voice lives in Slack: #dev, #dev_git, #growzth, #andesite-internal,
DMs, etc.

What it does
------------
1. For each high-signal channel, read recent N messages via slack-skill.
2. Filter to user_id `U04R0EJACMR` (Idan Beck).
3. Filter to last <days> by ts.
4. For threaded messages, optionally pull thread replies (--threads).
5. Classify by concern category (shared catalog with ingest_recent.py).
6. Write to `~/.claude/skills/fakeidan/patterns/idanbeck-slack-YYYY-MM-DD.md`.

Run modes
---------
  ingest_slack.py                    — last 14d, default channels
  ingest_slack.py --days 30
  ingest_slack.py --channels dev,growzth
  ingest_slack.py --threads          — also fetch thread replies
  ingest_slack.py --dry-run
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

HOME = Path.home()
PATTERNS_DIR = HOME / ".claude/skills/fakeidan/patterns"
SLACK_SKILL = HOME / ".claude/skills/slack-skill/slack_skill.py"

IDAN_USER_ID = "U04R0EJACMR"
IDAN_NAMES = {"Idan Beck", "idanbeck", "idan"}

# Channels Idan posts product/code/review content in. Order matters: most-signal first.
DEFAULT_CHANNELS = [
    "dev", "dev_git", "andesite-internal", "growzth",
    "math-sci-topics", "lobby", "marketing",
]

# Slack-shaped categories — chat tends to be terser than PR comments. These are
# IN ADDITION to the GitHub concern catalog imported above.
SLACK_PATTERNS = {
    "decision":         re.compile(r"\b(?:let'?s|going to|will|should|won'?t|gonna|decided)\b", re.I),
    "concern":          re.compile(r"\b(?:worry|worried|nervous|concern|risk|issue with|problem with)\b", re.I),
    "opinion":          re.compile(r"\b(?:i think|imo|honestly|tbh|prefer|don'?t love|like.*better)\b", re.I),
    "shipped":          re.compile(r"\b(?:shipped|deployed|merged|pushed|synced|live now|in prod)\b", re.I),
    "structural":       re.compile(r"\b(?:restructur|rename|move.*under|reorg|cleanup|consolidat|migrat)\b", re.I),
    "review_signal":    re.compile(r"\b(?:LGTM|nit|approve|reject|request changes|looks good)\b", re.I),
    "ask":              re.compile(r"(?:\?|why|what.*think|thoughts|wdyt|cc @|cc <@)", re.I),
    "blocker":          re.compile(r"\b(?:blocked|blocking|waiting on|need.*from|can'?t until)\b", re.I),
}

# Reuse the concern catalog from ingest_recent.py if importable, else inline copy.
sys.path.insert(0, str(Path(__file__).parent))
try:
    from ingest_recent import CONCERN_PATTERNS, FAKE_IDAN_PREFIX  # type: ignore
except Exception:
    CONCERN_PATTERNS = {
        "atomicity":       re.compile(r"\b(?:atomic|race|crash mid|partial write|corrupt)", re.I),
        "error_handling":  re.compile(r"\b(?:error handler|EPIPE|swallow|missing.*handler|unhandled)", re.I),
        "edge_case":       re.compile(r"\b(?:edge case|boundary|off.by.one|empty|null|undefined)", re.I),
        "security":        re.compile(r"\b(?:secret|token|leak|sanitize|escape|injection|XSS|auth)", re.I),
        "perf":            re.compile(r"\b(?:perf|N\+1|quadratic|O\(N|too many queries|cache miss|hot path)", re.I),
        "data_integrity":  re.compile(r"\b(?:migration|schema|backfill|FK|orphan row|nullable)", re.I),
        "ux_polish":       re.compile(r"\b(?:looks off|copy|spacing|alignment|font|wording)", re.I),
        "test_coverage":   re.compile(r"\b(?:no test|missing test|untested|test for|regression test)", re.I),
        "money":           re.compile(r"\b(?:money|amount|currency|charge|invoice|tax|refund)", re.I),
        "multi_workspace": re.compile(r"\b(?:workspace|tenant|cross.org|org boundary|multi.tenant)", re.I),
        "async_ripple":    re.compile(r"\b(?:async|await|race condition|background job|webhook|retry|idempot)", re.I),
    }
    FAKE_IDAN_PREFIX = re.compile(r"\[fake idan\]", re.I)


def _slack(args: list[str], timeout: int = 30) -> dict | list | None:
    try:
        r = subprocess.run(
            ["/usr/bin/python3", str(SLACK_SKILL), *args],
            capture_output=True, text=True, timeout=timeout,
        )
        return json.loads(r.stdout) if r.stdout else None
    except Exception:
        return None


def is_idan(msg: dict) -> bool:
    if msg.get("user") == IDAN_USER_ID:
        return True
    if msg.get("user_name") in IDAN_NAMES:
        return True
    return False


def ts_to_dt(ts: str) -> dt.datetime | None:
    try:
        return dt.datetime.fromtimestamp(float(ts), tz=dt.timezone.utc)
    except (ValueError, TypeError):
        return None


def read_channel(channel: str, limit: int = 200) -> list[dict]:
    out = _slack(["read", channel, "-l", str(limit)], timeout=30)
    if not isinstance(out, dict):
        return []
    return out.get("messages", []) or []


def read_thread(channel: str, thread_ts: str) -> list[dict]:
    out = _slack(["thread", channel, thread_ts], timeout=20)
    if not isinstance(out, dict):
        return []
    return out.get("messages", []) or []


def classify(body: str) -> list[str]:
    if not body or FAKE_IDAN_PREFIX.search(body):
        return []
    hits = []
    for cat, regex in CONCERN_PATTERNS.items():
        if regex.search(body):
            hits.append(cat)
    for cat, regex in SLACK_PATTERNS.items():
        if regex.search(body):
            hits.append(cat)
    return hits


def render(report: dict, channels: list[str], examples: dict, raw_voice: list[tuple[str,str,str]]) -> str:
    today = dt.date.today().isoformat()
    lines = [
        f"# Idan Slack-message patterns — ingested {today}",
        "",
        f"Window: last {report['window_days']} days · channels: {', '.join(channels)}",
        f"Messages scanned: {report['scanned']} · real-Idan: {report['real_idan']} · "
        f"classified into a category: {report['classified']}.",
        "",
        "## Category distribution",
        "",
    ]
    if not report["concern_distribution"]:
        lines.append("- (no classified messages — Idan was operational/terse this window)")
    for cat, n in report["concern_distribution"].items():
        lines.append(f"- **{cat}**: {n}")
    lines += ["", "## Sample quotes per category", ""]
    for cat, samples in examples.items():
        if not samples:
            continue
        lines.append(f"### {cat}")
        lines.append("")
        for ch, quote, ts in samples:
            stamp = (ts_to_dt(ts) or dt.datetime.utcnow()).strftime("%Y-%m-%d")
            lines.append(f"- `#{ch}` ({stamp}) — {quote}")
        lines.append("")
    # Raw-voice samples — preserve ALL of Idan's actual chat. fakeidan can grep this directly.
    lines += [
        "## Raw Idan voice samples (chronological)",
        "",
        f"All {len(raw_voice)} Idan messages in window, oldest → newest. Use these for direct voice/tone reference.",
        "",
    ]
    # Sort by timestamp
    raw_voice.sort(key=lambda x: x[2])
    for ch, body, ts in raw_voice:
        stamp = (ts_to_dt(ts) or dt.datetime.utcnow()).strftime("%Y-%m-%d %H:%M")
        lines.append(f"- `#{ch}` ({stamp}) — {body}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--channels", type=str, default=",".join(DEFAULT_CHANNELS))
    parser.add_argument("--limit", type=int, default=200, help="messages per channel to fetch")
    parser.add_argument("--threads", action="store_true", help="also fetch thread replies")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    channels = [c.strip().lstrip("#") for c in args.channels.split(",") if c.strip()]
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.days)

    print(f"[ingest-slack] scanning {len(channels)} channels for Idan messages last {args.days}d", file=sys.stderr)

    scanned = 0
    real_idan = 0
    classified_count = 0
    counter: Counter = Counter()
    examples: dict[str, list[tuple[str, str, str]]] = {k: [] for k in {**CONCERN_PATTERNS, **SLACK_PATTERNS}}
    raw_voice: list[tuple[str, str, str]] = []  # (channel, body, ts) — keep ALL Idan messages as raw voice samples

    for ch in channels:
        msgs = read_channel(ch, limit=args.limit)
        for m in msgs:
            scanned += 1
            tm = ts_to_dt(m.get("ts", ""))
            if not tm or tm < cutoff:
                continue
            if not is_idan(m):
                # Also walk thread replies if this top-level was Idan-adjacent
                continue
            real_idan += 1
            body = m.get("text") or ""
            if body.strip():
                raw_voice.append((ch, body.replace("\n", " ").strip()[:300], m.get("ts", "")))
            cats = classify(body)
            if cats:
                classified_count += 1
                for cat in cats:
                    counter[cat] += 1
                    if len(examples[cat]) < 3:
                        quote = body.replace("\n", " ").strip()[:200]
                        examples[cat].append((ch, quote, m.get("ts", "")))
            # Optional: walk thread for Idan replies
            if args.threads and m.get("thread_ts") and m.get("reply_count", 0) > 0:
                for tr in read_thread(ch, m["thread_ts"]):
                    if not is_idan(tr):
                        continue
                    trt = ts_to_dt(tr.get("ts", ""))
                    if not trt or trt < cutoff:
                        continue
                    real_idan += 1
                    cats2 = classify(tr.get("text") or "")
                    if cats2:
                        classified_count += 1
                        for cat in cats2:
                            counter[cat] += 1
                            if len(examples[cat]) < 3:
                                quote = (tr.get("text") or "").replace("\n", " ").strip()[:200]
                                examples[cat].append((ch, quote, tr.get("ts", "")))
        print(f"[ingest-slack]   {ch}: scanned {len(msgs)} messages", file=sys.stderr)

    report = {
        "window_days": args.days,
        "scanned": scanned,
        "real_idan": real_idan,
        "classified": classified_count,
        "concern_distribution": dict(counter.most_common()),
    }
    today = dt.date.today().isoformat()
    out_path = PATTERNS_DIR / f"idanbeck-slack-{today}.md"

    if args.dry_run:
        print(f"[ingest-slack] DRY RUN — would write {out_path}")
        print(json.dumps(report, indent=2))
        return 0

    PATTERNS_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(report, channels, examples, raw_voice), encoding="utf-8")
    print(f"[ingest-slack] wrote {out_path}: {real_idan} Idan msgs, {classified_count} classified, "
          f"{len(raw_voice)} raw-voice samples preserved")
    return 0


if __name__ == "__main__":
    sys.exit(main())
