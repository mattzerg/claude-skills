#!/usr/bin/env python3
"""working-session — agenda + decision log + parking lot."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".claude/skills/_consultant/python"))
from _bootstrap_helper import ensure_venv  # noqa: E402

ensure_venv(__file__)

import argparse  # noqa: E402
import datetime as _dt  # noqa: E402


SCAFFOLD_BODY = """## Agenda

**Date:** {date}
**Duration:** {duration} min
**Invitees:** {invitees}

| Time | Topic | Owner | Outcome target |
|---|---|---|---|
{agenda_rows}

## Decisions made

| ID | Decision | Owner | Date | Reversible? |
|---|---|---|---|---|

## Action items

| ID | Action | Owner | Due | Status |
|---|---|---|---|---|

## Parking lot

| ID | Item | Raised by | Resolution path |
|---|---|---|---|

## Follow-up questions

| ID | Question | Routes to | Due |
|---|---|---|---|

## Notes

- Decisions surface here, get a `dec-<slug>.md` in the engagement decisions folder when material.
- Anchored on `MattZerg/_style/consultant_thinking_style.md`.
"""


def scaffold(args) -> int:
    from consultant_kit import frontmatter, io  # type: ignore

    invitees = [p.strip() for p in args.invitees.split(",") if p.strip()]
    topics = [t.strip() for t in args.topics.split(",") if t.strip()]
    minutes_per = max(5, args.duration // max(len(topics), 1))

    agenda_rows = []
    for i, t in enumerate(topics):
        agenda_rows.append(f"| {minutes_per*i}–{minutes_per*(i+1)} min | {t} | _[owner]_ | _[outcome]_ |")

    body = SCAFFOLD_BODY.format(
        date=args.date,
        duration=args.duration,
        invitees=", ".join(invitees),
        agenda_rows="\n".join(agenda_rows),
    )

    engagement = args.engagement
    mode = args.mode or "ops"
    fm = frontmatter.envelope(
        engagement=engagement,
        slug=f"{io.slugify(engagement)}-session-{args.date}",
        skill="working-session",
        inputs=[],
        extra={"mode": mode, "date": args.date, "duration": args.duration, "invitees": invitees, "topics": topics},
    )
    out_root = io.engagement_dir(engagement, mode) / "working-sessions"
    out_root.mkdir(parents=True, exist_ok=True)
    out_path = out_root / f"{args.date}.md"
    frontmatter.write_md(out_path, fm, body)
    print(f"wrote {out_path}")
    return 0


SECTION_BY_TYPE = {
    "decision": "Decisions made",
    "action": "Action items",
    "parking-lot": "Parking lot",
    "question-for-followup": "Follow-up questions",
}
ID_PREFIX = {
    "decision": "D",
    "action": "A",
    "parking-lot": "P",
    "question-for-followup": "Q",
}


def log(args) -> int:
    import re as _re
    from consultant_kit import frontmatter  # type: ignore

    path = Path(args.path)
    fm, body = frontmatter.parse(path)
    section = SECTION_BY_TYPE[args.type]
    prefix = ID_PREFIX[args.type]
    rows = [m.group(1) for m in _re.finditer(rf"^\|\s+{prefix}(\d+)\s+\|", body, _re.MULTILINE)]
    next_id = f"{prefix}{(max(int(r) for r in rows) + 1) if rows else 1}"

    if args.type == "decision":
        new_row = f"| {next_id} | {args.description} | {args.owner or '—'} | {args.date or _dt.date.today().isoformat()} | {args.reversible or 'yes'} |"
    elif args.type == "action":
        new_row = f"| {next_id} | {args.description} | {args.owner or '—'} | {args.due or '—'} | {args.status or 'open'} |"
    elif args.type == "parking-lot":
        new_row = f"| {next_id} | {args.description} | {args.owner or '—'} | _[plan]_ |"
    else:
        new_row = f"| {next_id} | {args.description} | {args.routes or '—'} | {args.due or '—'} |"

    lines = body.splitlines()
    out_lines = []
    in_section = False
    inserted = False
    for line in lines:
        out_lines.append(line)
        if line.startswith(f"## {section}"):
            in_section = True
        elif line.startswith("## ") and in_section:
            in_section = False
        if in_section and not inserted and line.startswith("|---"):
            out_lines.append(new_row)
            inserted = True

    frontmatter.write_md(path, fm, "\n".join(out_lines))
    print(f"appended {next_id} to {section}")
    return 0


def summarize(args) -> int:
    from consultant_kit import frontmatter  # type: ignore

    fm, body = frontmatter.parse(Path(args.path))
    print(f"# Working session digest — {fm.get('engagement')} {fm.get('extra', {}).get('date', '')}")
    print()
    sections = ["Decisions made", "Action items", "Parking lot", "Follow-up questions"]
    current = None
    buf = []
    captured = {s: [] for s in sections}
    for line in body.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            continue
        if current in captured and line.startswith("|") and "---" not in line and not line.startswith("| ID"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells and cells[0] and cells[0] != "ID":
                captured[current].append(cells)
    for s in sections:
        rows = captured.get(s, [])
        if rows:
            print(f"## {s}")
            for r in rows:
                print(f"- **{r[0]}** — {r[1]} (owner: {r[2] if len(r) > 2 else '—'})")
            print()
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="working-session")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scaffold")
    s.add_argument("--engagement", required=True)
    s.add_argument("--mode", choices=("client", "pm", "ops", "life"), default=None)
    s.add_argument("--date", required=True)
    s.add_argument("--duration", type=int, default=60)
    s.add_argument("--invitees", required=True)
    s.add_argument("--topics", required=True)
    s.set_defaults(func=scaffold)

    l = sub.add_parser("log")
    l.add_argument("path")
    l.add_argument("--type", choices=tuple(SECTION_BY_TYPE), required=True)
    l.add_argument("--description", required=True)
    l.add_argument("--owner", default=None)
    l.add_argument("--due", default=None)
    l.add_argument("--date", default=None)
    l.add_argument("--reversible", default=None)
    l.add_argument("--status", default=None)
    l.add_argument("--routes", default=None)
    l.set_defaults(func=log)

    g = sub.add_parser("summarize")
    g.add_argument("path")
    g.set_defaults(func=summarize)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
