#!/usr/bin/env python3
"""Content calendar — sequence editorial pieces through state transitions.

Usage:
    python3 ~/.claude/skills/content-calendar/run.py add \\
        --title "..." --type blog|launch|pseo|case-study|newsletter|thread \\
        --target YYYY-MM-DD --slug <slug> [--owner Matt]
    python3 ~/.claude/skills/content-calendar/run.py next [--days N]
    python3 ~/.claude/skills/content-calendar/run.py status [--state STATE] [--type TYPE]
    python3 ~/.claude/skills/content-calendar/run.py slip --slug <slug> --to YYYY-MM-DD --reason "..."
    python3 ~/.claude/skills/content-calendar/run.py transition --slug <slug> --to STATE
    python3 ~/.claude/skills/content-calendar/run.py audit
    python3 ~/.claude/skills/content-calendar/run.py pulse [--past-days 30] [--next-days 30]

Forward-only state machine. Refuses skips. Refuses missing required artifacts.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

# Override with $ZERG_VAULT for non-author runs (S2 from fakeidan review).
DEFAULT_VAULT = "/Users/mattheweisner/Obsidian/Zerg/MattZerg"
VAULT = Path(os.environ.get("ZERG_VAULT", DEFAULT_VAULT))
GROWTH_DIR = VAULT / "Projects" / "Zerg-Production" / "Growth"
CONTENT_DIR = GROWTH_DIR / "content"
LEDGER_FILE = GROWTH_DIR / "content-calendar.md"

VALID_TYPES = ("blog", "launch", "pseo", "case-study", "newsletter", "thread")
STATES = ("idea", "drafted", "reviewed", "scheduled", "published", "distributed", "cancelled")
FORWARD = {
    "idea": ("drafted", "cancelled"),
    "drafted": ("reviewed", "cancelled"),
    "reviewed": ("scheduled", "cancelled"),
    "scheduled": ("published", "cancelled"),
    "published": ("distributed",),
    "distributed": (),
    "cancelled": (),
}

SLIP_DRIFT_THRESHOLD = 3
SCHEDULED_HORIZON_DAYS = 14


def parse_yaml_frontmatter(text: str) -> tuple[dict, str]:
    """Naive YAML frontmatter parser. Supports scalars + simple lists/dicts (no nesting)."""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}, text
    fm_block = text[4:end]
    body = text[end + 5:]
    meta: dict = {}
    current_key = None
    current_dict = None
    for line in fm_block.splitlines():
        if not line.strip():
            continue
        if line.startswith("  ") and current_dict is not None:
            k, _, v = line.strip().partition(":")
            v = v.strip().strip('"')
            current_dict[k.strip()] = v
            continue
        if line.startswith("  - ") and current_key is not None:
            if not isinstance(meta.get(current_key), list):
                meta[current_key] = []
            meta[current_key].append(line[4:].strip().strip('"'))
            continue
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k = k.strip()
        v = v.strip()
        if v == "":
            current_key = k
            meta[k] = {}
            current_dict = meta[k]
            continue
        if v.startswith('"') and v.endswith('"'):
            v = v[1:-1]
        if v == "[]":
            v = []
        meta[k] = v
        current_key = k
        current_dict = None
    # Clean: empty dicts → "" if no children added
    for k, v in list(meta.items()):
        if isinstance(v, dict) and not v:
            meta[k] = ""
    return meta, body


def render_yaml_frontmatter(meta: dict) -> str:
    lines = ["---"]
    for k, v in meta.items():
        if v == "" or v is None:
            lines.append(f"{k}:")
        elif isinstance(v, list):
            if not v:
                lines.append(f"{k}: []")
            else:
                lines.append(f"{k}:")
                for item in v:
                    if isinstance(item, dict):
                        first = True
                        for ik, iv in item.items():
                            prefix = "  - " if first else "    "
                            lines.append(f'{prefix}{ik}: "{iv}"')
                            first = False
                    else:
                        lines.append(f'  - "{item}"')
        elif isinstance(v, dict):
            lines.append(f"{k}:")
            for ik, iv in v.items():
                lines.append(f'  {ik}: "{iv}"' if iv else f"  {ik}:")
        elif any(c in str(v) for c in [":", "#", "\n"]):
            esc = str(v).replace('"', '\\"')
            lines.append(f'{k}: "{esc}"')
        else:
            lines.append(f"{k}: {v}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def piece_kind(meta: dict) -> str:
    """Return blog/launch/pseo/... — `kind` is the gtm-hub canonical field.

    Falls back to legacy `type` for files pre-hub-normalization. After
    migration `type` is always `content` and the actual kind lives in `kind`.
    """
    return meta.get("kind") or meta.get("type", "?")


def slug_path(slug: str) -> Path:
    return CONTENT_DIR / f"{slug}.md"


def all_pieces() -> list[tuple[Path, dict]]:
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for f in sorted(CONTENT_DIR.glob("*.md")):
        if f.name.startswith("_"):
            continue
        meta, _ = parse_yaml_frontmatter(f.read_text())
        if meta.get("slug"):
            out.append((f, meta))
    return out


def cmd_add(args: argparse.Namespace) -> int:
    if args.type not in VALID_TYPES:
        print(f"ERROR: --type must be one of {VALID_TYPES}", file=sys.stderr)
        return 1
    try:
        target = dt.date.fromisoformat(args.target)
    except ValueError:
        print(f"ERROR: --target {args.target!r} is not YYYY-MM-DD", file=sys.stderr)
        return 1
    if not re.match(r"^[a-z0-9][a-z0-9-]+$", args.slug):
        print(f"ERROR: --slug must be lowercase alphanumeric + hyphens", file=sys.stderr)
        return 1
    f = slug_path(args.slug)
    if f.exists():
        print(f"ERROR: piece {args.slug!r} already exists at {f}", file=sys.stderr)
        return 1

    today = dt.date.today().isoformat()
    meta = {
        # gtm-hub envelope
        "id": args.slug,
        "type": "content",
        "title": args.title,
        "status": "idea",
        "owner": args.owner.lower() if isinstance(args.owner, str) else args.owner,
        "created": today,
        "last_touch": today,
        # content-calendar fields
        "slug": args.slug,
        "kind": args.type,
        "state": "idea",
        "target_date": target.isoformat(),
        "slips": 0,
        "slip_log": [],
        "artifacts": {
            "draft": "",
            "imagery": "",
            "copyedit_review": "",
            "distribution_card": "",
        },
        "related_experiments": [],
    }
    body = (
        f"# {args.title}\n\n"
        f"**Slug:** `{args.slug}`  \n"
        f"**Type:** {args.type}  \n"
        f"**Target:** {target.isoformat()}\n\n"
        f"## State log\n\n| Date | From | To | Note |\n|---|---|---|---|\n"
        f"| {today} | — | idea | Created |\n\n"
        f"## Notes\n\n"
    )
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(render_yaml_frontmatter(meta) + "\n" + body)
    print(f"Added {args.slug} ({args.type}, target {target.isoformat()}) at {f}")
    print(f"State: idea. Next: run transition --to drafted when draft exists.")
    return 0


def cmd_next(args: argparse.Namespace) -> int:
    today = dt.date.today()
    horizon = today + dt.timedelta(days=args.days)
    rows = []
    for f, meta in all_pieces():
        if meta.get("state") in ("distributed", "cancelled"):
            continue
        try:
            td = dt.date.fromisoformat(meta.get("target_date", ""))
        except ValueError:
            continue
        if td > horizon:
            continue
        rows.append((td, meta))
    rows.sort(key=lambda r: r[0])
    if not rows:
        print(f"(no pieces in next {args.days} days)")
        return 0
    print(f"# Next {args.days} days ({today.isoformat()} → {horizon.isoformat()})\n")
    print("| Target | Slug | Type | State | Next |")
    print("|---|---|---|---|---|")
    for td, m in rows:
        nxt = _next_action(m)
        marker = " ⚠️ OVERDUE" if td < today else ""
        print(f"| {td.isoformat()}{marker} | {m['slug']} | {piece_kind(m)} | {m['state']} | {nxt} |")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    rows = all_pieces()
    if args.state:
        rows = [r for r in rows if r[1].get("state") == args.state]
    if args.type:
        rows = [r for r in rows if piece_kind(r[1]) == args.type]
    if not rows:
        print("(no matching pieces)")
        return 0
    rows.sort(key=lambda r: r[1].get("target_date", "9999"))
    print("| Target | Slug | Type | State | Owner | Slips |")
    print("|---|---|---|---|---|---|")
    for _, m in rows:
        print(f"| {m.get('target_date','?')} | {m['slug']} | {piece_kind(m)} | {m['state']} | {m.get('owner','?')} | {m.get('slips',0)} |")
    return 0


def cmd_slip(args: argparse.Namespace) -> int:
    f = slug_path(args.slug)
    if not f.exists():
        print(f"ERROR: no such piece {args.slug!r}", file=sys.stderr)
        return 1
    try:
        new_target = dt.date.fromisoformat(args.to)
    except ValueError:
        print(f"ERROR: --to {args.to!r} is not YYYY-MM-DD", file=sys.stderr)
        return 1
    meta, body = parse_yaml_frontmatter(f.read_text())
    today = dt.date.today().isoformat()
    old = meta.get("target_date", "?")
    meta["target_date"] = new_target.isoformat()
    slips = int(meta.get("slips", 0)) + 1
    meta["slips"] = slips
    log = meta.get("slip_log") or []
    if not isinstance(log, list):
        log = []
    log.append(f"{today}: {old} → {new_target.isoformat()} — {args.reason}")
    meta["slip_log"] = log
    meta["last_touch"] = today  # gtm-hub envelope
    f.write_text(render_yaml_frontmatter(meta) + "\n" + body)
    print(f"Slipped {args.slug}: {old} → {new_target.isoformat()} (slip count: {slips}).")
    if slips >= SLIP_DRIFT_THRESHOLD:
        print(f"WARN: {slips} slips on {args.slug}. Drift forcing function — consider cancelling or finishing now.", file=sys.stderr)
    return 0


def _next_action(meta: dict) -> str:
    state = meta.get("state", "?")
    typ = piece_kind(meta)
    if state == "idea":
        if typ == "pseo":
            return "scaffold via programmatic-seo"
        if typ == "launch":
            return "scaffold via launch-announcement"
        if typ == "case-study":
            return "scaffold via case-study-skill"
        return "draft → transition --to drafted"
    if state == "drafted":
        artifacts = meta.get("artifacts", {})
        if isinstance(artifacts, dict) and not artifacts.get("imagery"):
            return "run blog-imagery → then transition --to reviewed"
        return "run fakematt-copyedit → transition --to reviewed"
    if state == "reviewed":
        return "transition --to scheduled when target ≤ 14 days"
    if state == "scheduled":
        return "publish → transition --to published"
    if state == "published":
        return "run content-distribution → transition --to distributed"
    if state == "distributed":
        return "(done)"
    return "(unknown)"


def cmd_transition(args: argparse.Namespace) -> int:
    f = slug_path(args.slug)
    if not f.exists():
        print(f"ERROR: no such piece {args.slug!r}", file=sys.stderr)
        return 1
    if args.to not in STATES:
        print(f"ERROR: --to must be one of {STATES}", file=sys.stderr)
        return 1
    meta, body = parse_yaml_frontmatter(f.read_text())
    cur = meta.get("state", "idea")
    if args.to not in FORWARD.get(cur, ()):
        print(f"ERROR: cannot transition {cur} → {args.to}. Valid: {FORWARD.get(cur, ())}", file=sys.stderr)
        return 1

    # Required-artifact gates
    artifacts = meta.get("artifacts", {})
    if not isinstance(artifacts, dict):
        artifacts = {}
    typ = meta.get("type", "")
    msg_extra = []

    if args.to == "reviewed":
        if typ in ("blog", "launch") and not artifacts.get("copyedit_review"):
            print(f"ERROR: transition to 'reviewed' requires artifacts.copyedit_review path. "
                  f"Run fakematt-copyedit first, then update with --artifact copyedit_review=<path>.", file=sys.stderr)
            return 1
    if args.to == "scheduled":
        try:
            td = dt.date.fromisoformat(meta.get("target_date", ""))
            today = dt.date.today()
            if (td - today).days > SCHEDULED_HORIZON_DAYS:
                print(f"ERROR: target_date {td.isoformat()} is more than {SCHEDULED_HORIZON_DAYS} days out. "
                      f"Stay in 'reviewed' until ≤ {SCHEDULED_HORIZON_DAYS} days.", file=sys.stderr)
                return 1
        except ValueError:
            pass
    if args.to == "distributed":
        if not artifacts.get("distribution_card"):
            print(f"ERROR: transition to 'distributed' requires artifacts.distribution_card. "
                  f"Run content-distribution first, then update with --artifact distribution_card=<id>.", file=sys.stderr)
            return 1

    today = dt.date.today().isoformat()
    meta["state"] = args.to
    meta["status"] = args.to  # gtm-hub envelope mirror
    meta["last_touch"] = today
    f.write_text(render_yaml_frontmatter(meta) + "\n" + body)

    # Append to state log
    needle = "## State log\n\n| Date | From | To | Note |\n|---|---|---|---|\n"
    text = f.read_text()
    if needle in text:
        row = f"| {today} | {cur} | {args.to} | {args.note or ''} |\n"
        text = text.replace(needle, needle + row, 1)
        f.write_text(text)

    print(f"Transitioned {args.slug}: {cur} → {args.to}.")
    print(f"Next: {_next_action({'state': args.to, 'type': typ, 'artifacts': artifacts})}")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    today = dt.date.today()
    overdue = []
    missing_imagery = []
    missing_distribution = []
    high_slip = []
    for _, meta in all_pieces():
        state = meta.get("state", "")
        if state in ("distributed", "cancelled"):
            continue
        try:
            td = dt.date.fromisoformat(meta.get("target_date", ""))
            if td < today:
                overdue.append(meta)
        except ValueError:
            pass
        artifacts = meta.get("artifacts", {})
        if isinstance(artifacts, dict):
            if state == "drafted" and not artifacts.get("imagery"):
                missing_imagery.append(meta)
            if state == "published" and not artifacts.get("distribution_card"):
                missing_distribution.append(meta)
        if int(meta.get("slips", 0) or 0) >= SLIP_DRIFT_THRESHOLD:
            high_slip.append(meta)

    if not (overdue or missing_imagery or missing_distribution or high_slip):
        print("✓ No drift detected.")
        return 0

    print("# Content Calendar Audit\n")
    if overdue:
        print(f"## Overdue ({len(overdue)})")
        for m in overdue:
            print(f"- `{m['slug']}` ({m['state']}) — target {m.get('target_date','?')} ")
        print()
    if missing_imagery:
        print(f"## Missing imagery ({len(missing_imagery)})")
        for m in missing_imagery:
            print(f"- `{m['slug']}` is in 'drafted' but has no imagery artifact. Run blog-imagery.")
        print()
    if missing_distribution:
        print(f"## Missing distribution ({len(missing_distribution)})")
        for m in missing_distribution:
            print(f"- `{m['slug']}` is 'published' but has no distribution_card. Run content-distribution.")
        print()
    if high_slip:
        print(f"## High slip count (≥{SLIP_DRIFT_THRESHOLD})")
        for m in high_slip:
            print(f"- `{m['slug']}` has slipped {m['slips']} times. Cancel or finish.")
        print()
    return 0 if not overdue else 2


STATE_CODE = {
    "idea": "id",
    "drafted": "dr",
    "reviewed": "rv",
    "scheduled": "sc",
    "published": "pb",
    "distributed": "di",
    "cancelled": "ca",
}
TYPE_CODE = {
    "blog": "B",
    "launch": "L",
    "pseo": "P",
    "case-study": "C",
    "newsletter": "N",
    "thread": "T",
}


def _slug_cell(slug: str, slips: int, width: int) -> str:
    prefix = "!" if int(slips or 0) >= SLIP_DRIFT_THRESHOLD else ""
    body = prefix + slug
    if len(body) > width:
        body = body[: width - 3] + "..."
    return body.ljust(width)


def cmd_pulse(args: argparse.Namespace) -> int:
    today = dt.date.today()
    past_floor = today - dt.timedelta(days=args.past_days)
    next_ceil = today + dt.timedelta(days=args.next_days)

    past, upcoming, overdue = [], [], []
    for _, meta in all_pieces():
        try:
            td = dt.date.fromisoformat(meta.get("target_date", ""))
        except ValueError:
            continue
        state = meta.get("state", "idea")
        if state == "cancelled":
            continue
        if state in ("published", "distributed"):
            if past_floor <= td <= today:
                past.append((td, meta))
        elif td < today:
            overdue.append((td, meta))
        elif td <= next_ceil:
            upcoming.append((td, meta))

    past.sort(key=lambda r: r[0], reverse=True)
    upcoming.sort(key=lambda r: r[0])
    overdue.sort(key=lambda r: r[0])

    SLUG_W = 17
    HEADER_PAST = "DATE  SLUG              T ST O"
    HEADER_NEXT = "DATE  SLUG              T ST O   D"
    LINE = "=" * 36

    print(f"PUBLISHING PULSE  {today.isoformat()}")
    print(LINE)
    print()

    print(f"PAST {args.past_days}D  ({len(past)} shipped)")
    if past:
        print(HEADER_PAST)
        for td, m in past:
            print(
                f"{td.strftime('%m-%d')} {_slug_cell(m['slug'], m.get('slips', 0), SLUG_W)} "
                f"{TYPE_CODE.get(m.get('type',''), '?')} "
                f"{STATE_CODE.get(m.get('state',''), '??')} "
                f"{(m.get('owner') or '?')[:1]}"
            )
    else:
        print("(none)")
    print()

    print(f"NEXT {args.next_days}D  ({len(upcoming)} upcoming)")
    if upcoming:
        print(HEADER_NEXT)
        for td, m in upcoming:
            d = (td - today).days
            print(
                f"{td.strftime('%m-%d')} {_slug_cell(m['slug'], m.get('slips', 0), SLUG_W)} "
                f"{TYPE_CODE.get(m.get('type',''), '?')} "
                f"{STATE_CODE.get(m.get('state',''), '??')} "
                f"{(m.get('owner') or '?')[:1]} "
                f"{d:3d}"
            )
    else:
        print("(none)")
    print()

    print(f"OVERDUE  ({len(overdue)})")
    if overdue:
        print(HEADER_NEXT)
        for td, m in overdue:
            d = (td - today).days
            print(
                f"{td.strftime('%m-%d')} {_slug_cell(m['slug'], m.get('slips', 0), SLUG_W)} "
                f"{TYPE_CODE.get(m.get('type',''), '?')} "
                f"{STATE_CODE.get(m.get('state',''), '??')} "
                f"{(m.get('owner') or '?')[:1]} "
                f"{d:3d}"
            )
    print()

    print("LEGEND")
    print("type  B blog  L launch  P pseo")
    print("      C case  N newsl   T thread")
    print("state id dr rv sc pb di")
    print("flag  ! prefix = slips >= 3")
    print(LINE)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="content-calendar", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("add", help="register a new piece")
    pa.add_argument("--title", required=True)
    pa.add_argument("--type", required=True, choices=VALID_TYPES)
    pa.add_argument("--target", required=True, help="YYYY-MM-DD")
    pa.add_argument("--slug", required=True)
    pa.add_argument("--owner", default="Matt")
    pa.set_defaults(func=cmd_add)

    pn = sub.add_parser("next", help="today + N day forecast")
    pn.add_argument("--days", type=int, default=7)
    pn.set_defaults(func=cmd_next)

    ps = sub.add_parser("status", help="table of all pieces")
    ps.add_argument("--state", choices=STATES)
    ps.add_argument("--type", choices=VALID_TYPES)
    ps.set_defaults(func=cmd_status)

    psl = sub.add_parser("slip", help="push target date")
    psl.add_argument("--slug", required=True)
    psl.add_argument("--to", required=True, help="YYYY-MM-DD")
    psl.add_argument("--reason", required=True)
    psl.set_defaults(func=cmd_slip)

    pt = sub.add_parser("transition", help="move state forward")
    pt.add_argument("--slug", required=True)
    pt.add_argument("--to", required=True, choices=STATES)
    pt.add_argument("--note", default="")
    pt.set_defaults(func=cmd_transition)

    pau = sub.add_parser("audit", help="flag overdue + missing artifacts")
    pau.set_defaults(func=cmd_audit)

    pp = sub.add_parser("pulse", help="terminal pulse — past + next + overdue, <40 chars wide")
    pp.add_argument("--past-days", type=int, default=30, dest="past_days")
    pp.add_argument("--next-days", type=int, default=30, dest="next_days")
    pp.set_defaults(func=cmd_pulse)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
