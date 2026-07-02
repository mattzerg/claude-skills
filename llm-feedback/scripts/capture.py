#!/usr/bin/env python3
"""llm-feedback capture / list / promote / reclassify / digest.

Phase 1: argument parsing + ledger append + JSON mirror + promotion-hint.
Phase 2 (2026-05-27):
  - Auto-classify bucket on capture (mirrors learn-matt classify bucket regex,
    inlined so capture doesn't shell out per call).
  - `reclassify` verb so Matt can override the auto-bucket.
  - `digest` verb for the Friday cron — renders the week's captures and,
    with --post, fires the Fake Matt -> Matt DM.
  - `--dry-run` flag on capture (skip write, still print + classify).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

VAULT = Path(
    os.environ.get(
        "MATTZERG_VAULT",
        "/Users/mattheweisner/Obsidian/Zerg/MattZerg",
    )
)
LEDGER = VAULT / "Tasks" / "llm-feedback-log.md"
MIRROR_DIR = VAULT / ".llm-feedback"

RECURRING_TRIGGERS = re.compile(
    r"\b(always|never|every time|don't|do not|stop|this keeps|you keep|from now on|going forward)\b",
    re.IGNORECASE,
)

TYPES = {"code", "prose", "plan", "hero", "slack", "email", "other"}

# --- Auto-classify (mirrors learn-matt BUCKETS so capture-time classification
# matches downstream promotion). Keep this in sync with
# ~/.config/zerg/learn_matt.py:BUCKETS.
BUCKETS = [
    # wrong-model-picked is checked FIRST: model-routing corrections feed back into
    # aitr's ranker (bounded penalty on the corrected-away-from model). Requires
    # model-specific phrasing so generic "should have used X" doesn't false-match.
    ("wrong-model-picked", re.compile(
        r"(wrong model"
        r"|should have used (opus|sonnet|haiku|gpt|gemini|a (cheaper|smaller|bigger|better|faster) model)"
        r"|too expensive for this"
        r"|(haiku|sonnet|opus|gpt-\d|gemini) would have (been fine|sufficed|worked)"
        r"|didn't need (opus|gpt-5|a big model)"
        r"|overkill model|model overkill"
        r"|under-?powered model)", re.I)),
    ("needs-tool-regression", re.compile(r"(keeps happening|again|curl|live|404|source|assert|verify|status|pipeline|dashboard)", re.I)),
    ("needs-skill-wiring", re.compile(r"(skill|orchestrator|review-pack|content-release|copyedit|fakeidan|fakematt)", re.I)),
    ("new-rule", re.compile(r"(always|never|do not|don't|in the future|make sure|remember)", re.I)),
    ("already-covered", re.compile(r"(zpub|3-list|source-before|RAYG|in-flight|SPA|deferred tool)", re.I)),
]

# aitr decision IDs look like: aitr-20260602-043133-7b604e. When a correction
# references one (in the artifact pointer or the feedback text), capture it so
# aitr's ranker can penalize the exact decision's (caller, task_kind, model).
AITR_DECISION_RE = re.compile(r"\b(aitr-\d{8}-\d{6}-[0-9a-f]{6})\b")


def auto_classify(text: str) -> str:
    """Return one of wrong-model-picked / needs-tool-regression / needs-skill-wiring /
    new-rule / already-covered / archive-only. Matches learn-matt classify shape;
    wrong-model-picked additionally feeds aitr's ranker penalties."""
    for bucket, rx in BUCKETS:
        if rx.search(text):
            return bucket
    return "archive-only"


def auto_type(artifact: str, current: str) -> str:
    """If caller passed default 'other', infer from artifact path/suffix."""
    if current != "other":
        return current
    a = artifact.lower()
    if a.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".go", ".rb", ".java")):
        return "code"
    if a.endswith(".md") or "/writing/" in a or "/blog/" in a:
        return "prose"
    if a.endswith((".png", ".jpg", ".jpeg", ".webp", ".svg")) or "/hero" in a or "hero-image" in a:
        return "hero"
    if a.endswith((".plan.md", ".plan")) or "/plans/" in a:
        return "plan"
    if a.startswith("slack:") or "/slack/" in a:
        return "slack"
    if a.startswith("email:") or a.endswith(".eml"):
        return "email"
    return "other"


def _now_pt_iso() -> str:
    # Naive PT - drop tz dep for the stub; caller can override.
    return dt.datetime.now().isoformat(timespec="seconds")


def _next_seq(date_str: str) -> int:
    MIRROR_DIR.mkdir(parents=True, exist_ok=True)
    existing = sorted(MIRROR_DIR.glob(f"{date_str}-*.json"))
    return len(existing) + 1


def _ensure_ledger() -> None:
    if LEDGER.exists():
        return
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(
        "# LLM Feedback Log\n\n"
        "Append-only ledger of natural-language feedback on Claude/Codex outputs. "
        "Capture lane for `llm-feedback` skill; promotion lane is `learn-matt classify`.\n\n"
        "| ID | When (PT) | Type | Bucket | Artifact | Feedback | Hint |\n"
        "|----|-----------|------|--------|----------|----------|------|\n"
    )


def _migrate_ledger_header_if_needed() -> None:
    """Ledger from Phase 1 had no 'Bucket' column. Detect + add it the first
    time Phase 2 runs. Idempotent."""
    if not LEDGER.exists():
        return
    head = LEDGER.read_text().splitlines()[:10]
    if any("| Bucket |" in line or "| Bucket|" in line for line in head):
        return
    # Phase 1 header detected — rewrite header + separator, leave rows alone.
    lines = LEDGER.read_text().splitlines()
    new_lines = []
    swapped = False
    for line in lines:
        if not swapped and line.startswith("| ID |"):
            new_lines.append("| ID | When (PT) | Type | Bucket | Artifact | Feedback | Hint |")
            continue
        if not swapped and line.startswith("|----"):
            new_lines.append("|----|-----------|------|--------|----------|----------|------|")
            swapped = True
            continue
        new_lines.append(line)
    LEDGER.write_text("\n".join(new_lines) + "\n")


def capture(args: argparse.Namespace) -> int:
    if args.type not in TYPES:
        print(f"[llm-feedback] unknown type {args.type!r}; using 'other'", file=sys.stderr)
        args.type = "other"

    when = _now_pt_iso()
    date_str = when[:10]
    seq = _next_seq(date_str)
    entry_id = f"{date_str}-{seq:03d}"
    recurring = bool(RECURRING_TRIGGERS.search(args.feedback))
    hint = "recurring -> learn-matt classify" if recurring else "captured (one-off)"
    inferred_type = auto_type(args.artifact, args.type)
    bucket = auto_classify(args.feedback)

    # Tie model-routing corrections back to the aitr decision that made the pick.
    decision_match = AITR_DECISION_RE.search(args.artifact) or AITR_DECISION_RE.search(args.feedback)
    aitr_decision_id = decision_match.group(1) if decision_match else None

    record = {
        "id": entry_id,
        "when": when,
        "artifact": args.artifact,
        "type": inferred_type,
        "type_inferred_from": args.type if inferred_type != args.type else None,
        "bucket": bucket,
        "bucket_source": "auto",
        "feedback": args.feedback,
        "session_id": os.environ.get("CLAUDE_SESSION_ID") or os.environ.get("CODEX_SESSION_ID"),
        "model": os.environ.get("LLM_FEEDBACK_MODEL"),
        "provider": os.environ.get("LLM_FEEDBACK_PROVIDER"),
        "aitr_decision_id": aitr_decision_id,
        "hint": hint,
    }

    if args.dry_run:
        print("# DRY RUN — no ledger / mirror write")
        print(json.dumps(record, indent=2))
        return 0

    _ensure_ledger()
    _migrate_ledger_header_if_needed()
    safe_feedback = args.feedback.replace("|", "\\|").replace("\n", " ")
    safe_artifact = args.artifact.replace("|", "\\|")
    row = f"| {entry_id} | {when} | {inferred_type} | {bucket} | {safe_artifact} | {safe_feedback} | {hint} |\n"
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(row)

    mirror_path = MIRROR_DIR / f"{entry_id}.json"
    mirror_path.write_text(json.dumps(record, indent=2))

    print(json.dumps(record, indent=2))
    return 0


def listing(args: argparse.Namespace) -> int:
    if not LEDGER.exists():
        print("[llm-feedback] no ledger yet", file=sys.stderr)
        return 0
    cutoff = dt.date.today() - dt.timedelta(days=args.days)
    for line in LEDGER.read_text().splitlines():
        if not line.startswith("| 20"):
            continue
        date_str = line.split("|", 3)[1].strip()[:10]
        try:
            if dt.date.fromisoformat(date_str) >= cutoff:
                print(line)
        except ValueError:
            continue
    return 0


def promote(args: argparse.Namespace) -> int:
    mirror_path = MIRROR_DIR / f"{args.entry_id}.json"
    if not mirror_path.exists():
        print(f"[llm-feedback] entry {args.entry_id} not found", file=sys.stderr)
        return 1
    record = json.loads(mirror_path.read_text())
    # Phase 1: print the hand-off command; do not invoke `learn-matt` automatically.
    print("# Hand-off to learn-matt classify:")
    print(f'learn-matt classify "{record["feedback"]}"')
    print(f"# Source entry: {mirror_path}")
    print(f"# Auto-bucket at capture: {record.get('bucket', 'unknown')}")
    return 0


def reclassify(args: argparse.Namespace) -> int:
    """Override the auto-assigned bucket on an entry. Updates JSON mirror;
    leaves the markdown ledger row alone (append-only invariant) and appends
    a one-line `RECLASSIFIED:` note instead."""
    mirror_path = MIRROR_DIR / f"{args.entry_id}.json"
    if not mirror_path.exists():
        print(f"[llm-feedback] entry {args.entry_id} not found", file=sys.stderr)
        return 1
    valid_buckets = {"wrong-model-picked", "needs-tool-regression", "needs-skill-wiring", "new-rule", "already-covered", "archive-only"}
    if args.bucket not in valid_buckets:
        print(f"[llm-feedback] bucket must be one of {sorted(valid_buckets)}", file=sys.stderr)
        return 2
    record = json.loads(mirror_path.read_text())
    old = record.get("bucket")
    record["bucket"] = args.bucket
    record["bucket_source"] = "matt"
    record.setdefault("bucket_history", []).append({"from": old, "to": args.bucket, "when": _now_pt_iso()})
    mirror_path.write_text(json.dumps(record, indent=2))
    note = f"<!-- RECLASSIFIED: {args.entry_id} bucket {old} -> {args.bucket} at {_now_pt_iso()} -->\n"
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(note)
    print(json.dumps(record, indent=2))
    return 0


# --- Digest ---------------------------------------------------------------

def _entries_since(cutoff: dt.date) -> list[dict]:
    if not MIRROR_DIR.exists():
        return []
    out: list[dict] = []
    for path in sorted(MIRROR_DIR.glob("*.json")):
        try:
            rec = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        try:
            d = dt.date.fromisoformat(str(rec.get("when", ""))[:10])
        except ValueError:
            continue
        if d >= cutoff:
            out.append(rec)
    return out


def _last_friday(today: dt.date | None = None) -> dt.date:
    today = today or dt.date.today()
    # weekday(): Mon=0 ... Sun=6, Fri=4
    days_back = (today.weekday() - 4) % 7
    if days_back == 0:
        # Today is Friday — use the previous Friday so the digest covers a
        # full week, not zero seconds.
        days_back = 7
    return today - dt.timedelta(days=days_back)


def _render_digest(entries: list[dict], since: dt.date) -> str:
    if not entries:
        return (
            f"*llm-feedback digest* (since {since.isoformat()})\n"
            "No captures this week. Either Matt didn't correct anything (unlikely) "
            "or the capture skill isn't being invoked. Check `learn-matt scan --hours 168`."
        )
    by_bucket: dict[str, list[dict]] = {}
    for e in entries:
        by_bucket.setdefault(e.get("bucket", "archive-only"), []).append(e)
    order = ["wrong-model-picked", "needs-tool-regression", "needs-skill-wiring", "new-rule", "already-covered", "archive-only"]
    lines = [
        f"*llm-feedback digest* (since {since.isoformat()}, {len(entries)} capture(s))",
        "",
    ]
    for bucket in order:
        items = by_bucket.get(bucket, [])
        if not items:
            continue
        lines.append(f"*{bucket}* ({len(items)})")
        for e in items[:10]:
            fb = e.get("feedback", "").replace("\n", " ")[:160]
            art = e.get("artifact", "")[:60]
            lines.append(f"  - `{e['id']}` _{art}_ — {fb}")
        if len(items) > 10:
            lines.append(f"  - …+{len(items) - 10} more")
        lines.append("")
    promote_pending = [e for e in entries if e.get("hint", "").startswith("recurring") and e.get("bucket_source") == "auto"]
    if promote_pending:
        lines.append(f"*Promotion-pending ({len(promote_pending)})* — run `llm-feedback promote <id>` to hand to learn-matt.")
        for e in promote_pending[:5]:
            lines.append(f"  - `{e['id']}`")
    return "\n".join(lines).rstrip() + "\n"


def digest(args: argparse.Namespace) -> int:
    if args.since == "last-friday":
        cutoff = _last_friday()
    else:
        try:
            cutoff = dt.date.fromisoformat(args.since)
        except ValueError:
            print(f"[llm-feedback] --since must be ISO date or 'last-friday'", file=sys.stderr)
            return 2
    entries = _entries_since(cutoff)
    text = _render_digest(entries, cutoff)
    print(text)
    if args.post:
        return _post_to_slack(text)
    return 0


def _post_to_slack(text: str) -> int:
    """Best-effort fire to Fake Matt -> Matt DM via slack-skill if available."""
    slack_cli = Path.home() / ".claude/skills/slack-skill/scripts/send_dm.py"
    if not slack_cli.exists():
        # Fall back to fakematt-today daemon path if installed
        alt = Path.home() / ".config/zerg/fakematt-today/send_self_dm.py"
        if alt.exists():
            slack_cli = alt
        else:
            print("[llm-feedback] no slack send-script found; printed digest only", file=sys.stderr)
            return 0
    try:
        proc = subprocess.run(
            ["python3", str(slack_cli), "--target", "fakematt-to-matt", "--text", text],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode != 0:
            print(f"[llm-feedback] slack post failed: {proc.stderr.strip()[:200]}", file=sys.stderr)
            return proc.returncode
        return 0
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"[llm-feedback] slack post exception: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="llm-feedback")
    sub = parser.add_subparsers(dest="verb")

    cap = sub.add_parser("capture", help="append a feedback entry (default)")
    cap.add_argument("--artifact", required=True)
    cap.add_argument("--feedback", required=True)
    cap.add_argument("--type", default="other")
    cap.add_argument("--dry-run", action="store_true", help="classify + print but do not write ledger/mirror")
    cap.set_defaults(func=capture)

    lst = sub.add_parser("list", help="tail recent entries")
    lst.add_argument("--days", type=int, default=7)
    lst.set_defaults(func=listing)

    prm = sub.add_parser("promote", help="hand entry to learn-matt classify")
    prm.add_argument("entry_id")
    prm.set_defaults(func=promote)

    rc = sub.add_parser("reclassify", help="override auto-assigned bucket")
    rc.add_argument("entry_id")
    rc.add_argument("bucket", help="one of: wrong-model-picked, needs-tool-regression, needs-skill-wiring, new-rule, already-covered, archive-only")
    rc.set_defaults(func=reclassify)

    dg = sub.add_parser("digest", help="render weekly digest of captures")
    dg.add_argument("--since", default="last-friday", help="ISO date or 'last-friday' (default)")
    dg.add_argument("--post", action="store_true", help="post to Fake Matt -> Matt DM")
    dg.set_defaults(func=digest)

    args = parser.parse_args(argv)
    if not args.verb:
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
