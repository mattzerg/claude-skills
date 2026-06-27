#!/usr/bin/env python3
"""Experiment tracker — register, track, adjudicate Zerg growth experiments.

Usage:
    python3 ~/.claude/skills/experiment-tracker/run.py register \\
        --name slug --hypothesis "If X then Y because Z" \\
        --variant-a "control" --variant-b "treatment" \\
        --success-metric metric --success-threshold "+15%" --kill-threshold "+3%" \\
        --kill-date YYYY-MM-DD --sample-size 800 --rice 224 --problem P2|P1|both
    python3 ~/.claude/skills/experiment-tracker/run.py read [--id exp-NNN | --status running]
    python3 ~/.claude/skills/experiment-tracker/run.py log --id exp-NNN --read "..." --note "..."
    python3 ~/.claude/skills/experiment-tracker/run.py conclude --id exp-NNN \\
        --verdict kill|scale-A|scale-B|inconclusive --learning "..."
    python3 ~/.claude/skills/experiment-tracker/run.py prompt    (kill-decision prompts for kill_date - 2)
    python3 ~/.claude/skills/experiment-tracker/run.py list      (one-line status of all experiments)

Refuses registration without success_metric + success_threshold + kill_threshold + kill_date.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

def _resolve_vault_root(sub: str = "Zerg/MattZerg") -> Path:
    """Live vault is ~/Obsidian/<sub>; the iCloud path was retired 2026-06-24.
    Prefer the live path, fall back to the legacy iCloud path only if it still exists."""
    primary = Path.home() / "Obsidian" / sub
    if primary.exists():
        return primary
    legacy = (
        Path.home()
        / "Library" / "Mobile Documents" / "iCloud~md~obsidian" / "Documents" / sub
    )
    return legacy if legacy.exists() else primary


VAULT = _resolve_vault_root("Zerg/MattZerg")
GROWTH_DIR = VAULT / "Projects" / "Zstack" / "Growth"
EXPERIMENTS_DIR = GROWTH_DIR / "experiments"
LEDGER_FILE = GROWTH_DIR / "experiments.md"

VALID_PROBLEMS = {"P1", "P2", "both"}
VALID_VERDICTS = {"kill", "scale-A", "scale-B", "inconclusive"}
VALID_STATUSES = {"proposed", "running", "killed", "won", "inconclusive"}

CONCURRENT_LIMIT = 8
CONCURRENT_FLOOR = 2  # below this, dashboard turns red


class TrackerError(Exception):
    pass


def parse_yaml_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Parse YAML frontmatter. Returns (metadata, body). Naive parser — no nesting."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    fm_block = text[4:end]
    body = text[end + 5 :]
    meta: dict[str, str] = {}
    for line in fm_block.splitlines():
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        v = v.strip()
        # Strip surrounding quotes
        if v.startswith('"') and v.endswith('"'):
            v = v[1:-1]
        meta[k.strip()] = v
    return meta, body


def render_yaml_frontmatter(meta: dict[str, str]) -> str:
    lines = ["---"]
    for k, v in meta.items():
        if v is None or v == "":
            lines.append(f"{k}:")
        elif any(c in str(v) for c in [":", "#", "\n"]):
            esc = str(v).replace('"', '\\"')
            lines.append(f'{k}: "{esc}"')
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def next_experiment_id() -> str:
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    ids = [
        int(m.group(1))
        for f in EXPERIMENTS_DIR.glob("exp-*.md")
        if (m := re.match(r"exp-(\d+)\.md", f.name))
    ]
    n = max(ids, default=0) + 1
    return f"exp-{n:03d}"


def all_experiments() -> list[tuple[Path, dict[str, str]]]:
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)
    out: list[tuple[Path, dict[str, str]]] = []
    for f in sorted(EXPERIMENTS_DIR.glob("exp-*.md")):
        if f.name.startswith("_"):
            continue
        meta, _ = parse_yaml_frontmatter(f.read_text())
        if meta.get("id"):
            out.append((f, meta))
    return out


def running_experiments() -> list[tuple[Path, dict[str, str]]]:
    return [(f, m) for (f, m) in all_experiments() if m.get("status") == "running"]


def cmd_register(args: argparse.Namespace) -> int:
    # Anti-drift: required fields
    missing = []
    for fld in ("hypothesis", "variant_a", "variant_b", "success_metric",
                "success_threshold", "kill_threshold", "kill_date"):
        v = getattr(args, fld)
        if not v:
            missing.append(fld.replace("_", "-"))
    if missing:
        print(f"ERROR: missing required field(s): {', '.join(missing)}", file=sys.stderr)
        print("Refused per anti-drift contract: every experiment requires "
              "kill_date + kill_threshold + success_metric + success_threshold.", file=sys.stderr)
        return 1

    # Concurrent limit
    running = running_experiments()
    if args.start and len(running) >= CONCURRENT_LIMIT:
        print(f"ERROR: {len(running)} experiments already running; limit is {CONCURRENT_LIMIT}.",
              file=sys.stderr)
        return 1

    if args.problem not in VALID_PROBLEMS:
        print(f"ERROR: --problem must be one of {VALID_PROBLEMS}", file=sys.stderr)
        return 1

    # Validate kill_date
    try:
        dt.date.fromisoformat(args.kill_date)
    except ValueError:
        print(f"ERROR: --kill-date {args.kill_date!r} is not YYYY-MM-DD", file=sys.stderr)
        return 1

    eid = next_experiment_id()
    today = dt.date.today().isoformat()
    status = "running" if args.start else "proposed"
    meta = {
        "id": eid,
        "name": args.name,
        "hypothesis": args.hypothesis,
        "variant_a": args.variant_a,
        "variant_b": args.variant_b,
        "traffic_split": args.traffic_split,
        "success_metric": args.success_metric,
        "success_threshold": args.success_threshold,
        "kill_threshold": args.kill_threshold,
        "kill_date": args.kill_date,
        "sample_size_target": args.sample_size,
        "RICE_score": args.rice,
        "status": status,
        "problem": args.problem,
        "owner": args.owner,
        "created": today,
        "concluded": "",
        "verdict": "",
    }
    body = (
        f"# {eid} — {args.name}\n\n"
        f"## Hypothesis\n\n{args.hypothesis}\n\n"
        f"## Variants\n\n### Control (A)\n\n{args.variant_a}\n\n### Treatment (B)\n\n{args.variant_b}\n\n"
        f"## Success metric\n\n{args.success_metric}\n\n"
        f"- Success threshold: {args.success_threshold}\n"
        f"- Kill threshold: {args.kill_threshold}\n"
        f"- Sample size target: {args.sample_size}\n"
        f"- Kill date: {args.kill_date}\n\n"
        f"## Decision log\n\n| Date | Read | Note |\n|---|---|---|\n\n"
        f"## Conclusion\n\n(Filled at kill date.)\n"
    )
    text = render_yaml_frontmatter(meta) + "\n" + body
    out = EXPERIMENTS_DIR / f"{eid}.md"
    out.write_text(text)
    print(f"Registered {eid} ({status}) at {out}")
    if status == "running" and len(running) + 1 < CONCURRENT_FLOOR:
        print(f"WARN: only {len(running) + 1} experiments running; floor is {CONCURRENT_FLOOR}. "
              "Dashboard line #5 will turn red.", file=sys.stderr)
    return 0


def cmd_read(args: argparse.Namespace) -> int:
    if args.id:
        f = EXPERIMENTS_DIR / f"{args.id}.md"
        if not f.exists():
            print(f"ERROR: no such experiment {args.id}", file=sys.stderr)
            return 1
        print(f.read_text())
        return 0
    rows = all_experiments()
    if args.status:
        rows = [r for r in rows if r[1].get("status") == args.status]
    for f, meta in rows:
        print(f"--- {f.name} ---")
        print(f.read_text())
        print()
    return 0


def cmd_log(args: argparse.Namespace) -> int:
    f = EXPERIMENTS_DIR / f"{args.id}.md"
    if not f.exists():
        print(f"ERROR: no such experiment {args.id}", file=sys.stderr)
        return 1
    text = f.read_text()
    today = dt.date.today().isoformat()
    row = f"| {today} | {args.read} | {args.note or ''} |\n"
    # Append to the table under "## Decision log"
    needle = "## Decision log\n\n| Date | Read | Note |\n|---|---|---|\n"
    if needle in text:
        text = text.replace(needle, needle + row, 1)
    else:
        text = text + f"\n## Decision log\n\n| Date | Read | Note |\n|---|---|---|\n{row}"
    f.write_text(text)
    print(f"Logged read for {args.id} on {today}.")
    return 0


def cmd_conclude(args: argparse.Namespace) -> int:
    if args.verdict not in VALID_VERDICTS:
        print(f"ERROR: --verdict must be one of {VALID_VERDICTS}", file=sys.stderr)
        return 1
    f = EXPERIMENTS_DIR / f"{args.id}.md"
    if not f.exists():
        print(f"ERROR: no such experiment {args.id}", file=sys.stderr)
        return 1
    text = f.read_text()
    meta, body = parse_yaml_frontmatter(text)
    if not meta:
        print(f"ERROR: {args.id} has no frontmatter", file=sys.stderr)
        return 1
    today = dt.date.today().isoformat()
    new_status = {"kill": "killed", "scale-A": "won", "scale-B": "won",
                  "inconclusive": "inconclusive"}[args.verdict]
    meta["status"] = new_status
    meta["concluded"] = today
    meta["verdict"] = args.verdict

    # Append conclusion section
    conclusion = (
        f"\n### Verdict ({today})\n\n"
        f"- Verdict: {args.verdict}\n"
        f"- Status: {new_status}\n"
        f"- Learning: {args.learning or '(none recorded)'}\n"
    )
    if "## Conclusion" in body:
        body = body.replace("(Filled at kill date.)", conclusion)
    else:
        body = body + "\n## Conclusion\n" + conclusion

    f.write_text(render_yaml_frontmatter(meta) + "\n" + body)
    print(f"Concluded {args.id}: verdict={args.verdict}, status={new_status}.")
    return 0


def cmd_prompt(args: argparse.Namespace) -> int:
    """Fire kill-decision prompts. Writes to experiment decision_log AND stdout.

    Writing to the file means even if Slack drops the cron post, the prompt is
    recoverable from `Growth/experiments/<id>.md`. Anti-drift: 2-channel notify.
    """
    today = dt.date.today()
    threshold = today + dt.timedelta(days=2)
    needs_decision: list[tuple[Path, dict[str, str]]] = []
    overdue: list[tuple[Path, dict[str, str]]] = []
    for f, meta in running_experiments():
        try:
            kd = dt.date.fromisoformat(meta.get("kill_date", ""))
        except ValueError:
            continue
        if kd < today:
            overdue.append((f, meta))
        elif kd <= threshold:
            needs_decision.append((f, meta))
    if not needs_decision and not overdue:
        print("No kill-decision prompts due.")
        return 0

    today_str = today.isoformat()
    for f, meta in needs_decision:
        print(f"[DECIDE] {meta['id']} ({meta['name']}) — kill_date={meta['kill_date']} (≤2 days)")
        print(f"   Hypothesis: {meta.get('hypothesis', '?')}")
        print(f"   Decision: kill / scale-A / scale-B / extend? (Reply 48h or auto-kill.)")
        print()
        # Persist to decision_log so the prompt is recoverable even if Slack drops it
        _append_log_row(f, today_str, "PROMPT-FIRED",
                        f"kill_date={meta['kill_date']} ≤ 2 days. Awaiting decision (kill/scale-A/scale-B/extend).")
    for f, meta in overdue:
        print(f"[OVERDUE] {meta['id']} ({meta['name']}) — kill_date={meta['kill_date']} PASSED")
        print(f"   Auto-killing per anti-drift contract.")
        print(f"   Run: experiment-tracker conclude --id {meta['id']} --verdict kill --learning '<...>'")
        print()
        _append_log_row(f, today_str, "OVERDUE",
                        f"kill_date={meta['kill_date']} passed. Auto-kill recommended (run conclude --verdict kill).")
    return 0


def _append_log_row(f: Path, date_str: str, status: str, note: str) -> None:
    """Append a row to an experiment's decision_log table. Idempotency by-day:
    if today already has a PROMPT-FIRED row, skip (don't double-log on re-runs)."""
    text = f.read_text()
    needle = "## Decision log\n\n| Date | Read | Note |\n|---|---|---|\n"
    today_marker = f"| {date_str} | {status} |"
    if needle in text:
        # Skip if already logged for today with same status
        block_start = text.find(needle) + len(needle)
        block_end = text.find("\n## ", block_start)
        if block_end < 0:
            block_end = len(text)
        block = text[block_start:block_end]
        if today_marker in block:
            return  # idempotent
        new_row = f"| {date_str} | {status} | {note} |\n"
        text = text.replace(needle, needle + new_row, 1)
    else:
        text = text + f"\n## Decision log\n\n| Date | Read | Note |\n|---|---|---|\n| {date_str} | {status} | {note} |\n"
    f.write_text(text)


def cmd_start(args: argparse.Namespace) -> int:
    f = EXPERIMENTS_DIR / f"{args.id}.md"
    if not f.exists():
        print(f"ERROR: no such experiment {args.id}", file=sys.stderr)
        return 1
    text = f.read_text()
    meta, body = parse_yaml_frontmatter(text)
    if not meta:
        print(f"ERROR: {args.id} has no frontmatter", file=sys.stderr)
        return 1
    if meta.get("status") not in {"proposed", "running"}:
        print(f"ERROR: {args.id} is in status {meta.get('status')!r} — cannot start", file=sys.stderr)
        return 1
    # Concurrent limit guard
    running = [
        (rf, rm) for rf, rm in all_experiments()
        if rm.get("status") == "running" and rm.get("id") != meta.get("id")
    ]
    if len(running) >= CONCURRENT_LIMIT:
        print(f"ERROR: {len(running)} experiments already running; limit is {CONCURRENT_LIMIT}.", file=sys.stderr)
        return 1
    today = dt.date.today().isoformat()
    meta["status"] = "running"
    if not meta.get("started"):
        meta["started"] = today
    f.write_text(render_yaml_frontmatter(meta) + "\n" + body)
    print(f"Started {args.id} at {today}. Now running: {len(running) + 1}/{CONCURRENT_LIMIT}.")
    if len(running) + 1 < CONCURRENT_FLOOR:
        print(f"WARN: only {len(running) + 1} experiments running; floor is {CONCURRENT_FLOOR}. Dashboard line #5 still RED.", file=sys.stderr)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    rows = all_experiments()
    if not rows:
        print("(no experiments registered)")
        return 0
    for f, m in rows:
        print(f"{m['id']:<10}  {m.get('status','?'):<14}  kill={m.get('kill_date','?'):<12}  RICE={m.get('RICE_score','?'):<6}  {m.get('name','?')}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="experiment-tracker", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("register", help="register a new experiment")
    pr.add_argument("--name", required=True)
    pr.add_argument("--hypothesis", required=True)
    pr.add_argument("--variant-a", dest="variant_a", required=True)
    pr.add_argument("--variant-b", dest="variant_b", required=True)
    pr.add_argument("--traffic-split", dest="traffic_split", default="50/50")
    pr.add_argument("--success-metric", dest="success_metric", required=True)
    pr.add_argument("--success-threshold", dest="success_threshold", required=True)
    pr.add_argument("--kill-threshold", dest="kill_threshold", required=True)
    pr.add_argument("--kill-date", dest="kill_date", required=True)
    pr.add_argument("--sample-size", dest="sample_size", required=True)
    pr.add_argument("--rice", required=True, help="RICE score (numeric)")
    pr.add_argument("--problem", required=True, choices=sorted(VALID_PROBLEMS))
    pr.add_argument("--owner", default="Matt")
    pr.add_argument("--start", action="store_true", help="register as running, not proposed")
    pr.set_defaults(func=cmd_register)

    pre = sub.add_parser("read", help="read experiment(s)")
    pre.add_argument("--id")
    pre.add_argument("--status", choices=sorted(VALID_STATUSES))
    pre.set_defaults(func=cmd_read)

    pl = sub.add_parser("log", help="log a weekly read")
    pl.add_argument("--id", required=True)
    pl.add_argument("--read", required=True, help="data summary, e.g. 'A: 12% n=412 / B: 14% n=408'")
    pl.add_argument("--note", help="qualitative note")
    pl.set_defaults(func=cmd_log)

    pc = sub.add_parser("conclude", help="adjudicate a finished experiment")
    pc.add_argument("--id", required=True)
    pc.add_argument("--verdict", required=True, choices=sorted(VALID_VERDICTS))
    pc.add_argument("--learning", required=True)
    pc.set_defaults(func=cmd_conclude)

    pp = sub.add_parser("prompt", help="fire kill-decision prompts (Phase 1: stdout)")
    pp.set_defaults(func=cmd_prompt)

    pst = sub.add_parser("start", help="flip a proposed experiment to running")
    pst.add_argument("--id", required=True)
    pst.set_defaults(func=cmd_start)

    pls = sub.add_parser("list", help="one-line status of all experiments")
    pls.set_defaults(func=cmd_list)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
