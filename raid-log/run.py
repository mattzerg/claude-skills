#!/usr/bin/env python3
"""raid-log — Risks / Assumptions / Issues / Dependencies tracker."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".claude/skills/_consultant/python"))
from _bootstrap_helper import ensure_venv  # noqa: E402

ensure_venv(__file__)

import argparse  # noqa: E402
import datetime as _dt  # noqa: E402


SCAFFOLD_BODY = """## Risks

| ID | Description | Severity | Likelihood | Owner | Status | Due | Mitigation |
|---|---|---|---|---|---|---|---|

## Assumptions

| ID | Description | Owner | Status | Validation plan |
|---|---|---|---|---|

## Issues

| ID | Description | Severity | Owner | Status | Due | Resolution |
|---|---|---|---|---|---|---|

## Dependencies

| ID | Description | Depends on | Owner | Status | Due |
|---|---|---|---|---|---|

## Notes

- IDs: R1/R2 (risk), A1/A2 (assumption), I1/I2 (issue), D1/D2 (dependency).
- Severity: high / med / low. Likelihood: high / med / low.
- Status: open / in-progress / closed / blocked.
- Anchored on `MattZerg/_style/consultant_thinking_style.md`.
- Review weekly; stale rows (>14d) flag in `review`.
"""

CATEGORY_HEADERS = {
    "risk": ("Risks", "R"),
    "assumption": ("Assumptions", "A"),
    "issue": ("Issues", "I"),
    "dependency": ("Dependencies", "D"),
}


def scaffold(args) -> int:
    from consultant_kit import frontmatter, io  # type: ignore

    engagement = args.engagement
    mode = args.mode or "ops"
    fm = frontmatter.envelope(
        engagement=engagement,
        slug=f"{io.slugify(engagement)}-raid",
        skill="raid-log",
        inputs=[],
        extra={"mode": mode, "categories": ["risk", "assumption", "issue", "dependency"]},
    )
    out_root = io.engagement_dir(engagement, mode)
    out_root.mkdir(parents=True, exist_ok=True)
    out_path = out_root / "07-raid.md"
    frontmatter.write_md(out_path, fm, SCAFFOLD_BODY)
    print(f"wrote {out_path}")
    return 0


def add(args) -> int:
    from consultant_kit import frontmatter  # type: ignore

    path = Path(args.path)
    fm, body = frontmatter.parse(path)
    cat = args.category
    section_name, prefix = CATEGORY_HEADERS[cat]
    # Find next ID
    import re as _re
    rows = [m.group(1) for m in _re.finditer(rf"^\|\s+{prefix}(\d+)\s+\|", body, _re.MULTILINE)]
    next_id = f"{prefix}{(max(int(r) for r in rows) + 1) if rows else 1}"

    if cat == "risk":
        row = f"| {next_id} | {args.description} | {args.severity or 'med'} | {args.likelihood or 'med'} | {args.owner or '—'} | {args.status or 'open'} | {args.due or '—'} | {args.mitigation or '—'} |"
    elif cat == "assumption":
        row = f"| {next_id} | {args.description} | {args.owner or '—'} | {args.status or 'open'} | {args.validation or '—'} |"
    elif cat == "issue":
        row = f"| {next_id} | {args.description} | {args.severity or 'med'} | {args.owner or '—'} | {args.status or 'open'} | {args.due or '—'} | {args.resolution or '—'} |"
    elif cat == "dependency":
        row = f"| {next_id} | {args.description} | {args.depends_on or '—'} | {args.owner or '—'} | {args.status or 'open'} | {args.due or '—'} |"

    # Append after the table header for that section
    lines = body.splitlines()
    out_lines = []
    in_section = False
    inserted = False
    for line in lines:
        out_lines.append(line)
        if line.startswith(f"## {section_name}"):
            in_section = True
        elif line.startswith("## ") and in_section:
            in_section = False
        if in_section and not inserted and line.startswith("|---"):
            out_lines.append(row)
            inserted = True
    if not inserted:
        out_lines.append("")
        out_lines.append(f"## {section_name}")
        out_lines.append(row)

    frontmatter.write_md(path, fm, "\n".join(out_lines))
    print(f"appended {next_id} to {section_name} in {path}")
    return 0


def review(args) -> int:
    from consultant_kit import frontmatter  # type: ignore

    path = Path(args.path)
    fm, body = frontmatter.parse(path)
    findings = []
    today = _dt.date.today()

    for line in body.splitlines():
        if not line.startswith("|") or "---" in line or line.startswith("| ID"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells or not cells[0]:
            continue
        rid = cells[0]
        if rid in ("ID", "—"):
            continue
        # Owner check
        owner_idx = 4 if rid.startswith(("R", "I")) else 2 if rid.startswith("A") else 3 if rid.startswith("D") else None
        if owner_idx is not None and owner_idx < len(cells) and cells[owner_idx] in ("—", "", "TBD"):
            findings.append(("MED", f"{rid}: no owner assigned"))
        # Status check
        if "open" in line.lower() and "due" in line.lower():
            for c in cells:
                if "-" in c and len(c) == 10:
                    try:
                        due = _dt.date.fromisoformat(c)
                        if due < today:
                            findings.append(("HIGH", f"{rid}: open and past due ({c})"))
                    except ValueError:
                        pass
        # HIGH risk mitigation
        if rid.startswith("R") and len(cells) >= 8:
            if cells[2].lower() == "high" and cells[7] in ("—", "", "TBD"):
                findings.append(("HIGH", f"{rid}: HIGH severity risk with no mitigation"))

    print(f"## raid-log review — {path.name}")
    print(f"engagement: {fm.get('engagement', '—')}")
    print()
    if not findings:
        print("✅ no findings")
        return 0
    severity_order = {"HIGH": 0, "MED": 1, "LOW": 2}
    findings.sort(key=lambda f: severity_order[f[0]])
    for sev, msg in findings:
        print(f"- **{sev}** — {msg}")
    high = sum(1 for s, _ in findings if s == "HIGH")
    return 1 if high else 0


def main() -> int:
    p = argparse.ArgumentParser(prog="raid-log")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scaffold")
    s.add_argument("--engagement", required=True)
    s.add_argument("--mode", choices=("client", "pm", "ops", "life"), default=None)
    s.set_defaults(func=scaffold)

    a = sub.add_parser("add")
    a.add_argument("path")
    a.add_argument("--category", choices=tuple(CATEGORY_HEADERS), required=True)
    a.add_argument("--description", required=True)
    a.add_argument("--severity", default=None)
    a.add_argument("--likelihood", default=None)
    a.add_argument("--owner", default=None)
    a.add_argument("--status", default=None)
    a.add_argument("--due", default=None)
    a.add_argument("--mitigation", default=None)
    a.add_argument("--validation", default=None)
    a.add_argument("--resolution", default=None)
    a.add_argument("--depends-on", default=None)
    a.set_defaults(func=add)

    r = sub.add_parser("review")
    r.add_argument("path")
    r.set_defaults(func=review)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
