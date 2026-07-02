#!/usr/bin/env python3
"""raci-matrix — Responsible/Accountable/Consulted/Informed matrix."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".claude/skills/_consultant/python"))
from _bootstrap_helper import ensure_venv  # noqa: E402

ensure_venv(__file__)

import argparse  # noqa: E402


def scaffold(args) -> int:
    from consultant_kit import frontmatter, io  # type: ignore

    people = [p.strip() for p in args.people.split(",") if p.strip()]
    activities = [a.strip() for a in args.activities.split(",") if a.strip()]

    head = "| Activity | " + " | ".join(people) + " |"
    sep = "|---" + ("|---" * len(people)) + "|"
    rows = [head, sep]
    for a in activities:
        rows.append(f"| {a} | " + " | ".join("_" for _ in people) + " |")

    body = "\n".join([
        "## RACI",
        "",
        "Legend: R=Responsible, A=Accountable, C=Consulted, I=Informed. **Exactly one A per row.**",
        "",
        *rows,
        "",
        "## Notes",
        "",
        "- Empty cells are valid — not everyone touches every activity.",
        "- The Accountable role can be held by only one person per row.",
        "- Anchored on `MattZerg/_style/consultant_thinking_style.md`.",
    ])

    engagement = args.engagement
    mode = args.mode or "ops"
    fm = frontmatter.envelope(
        engagement=engagement,
        slug=f"{io.slugify(engagement)}-raci",
        skill="raci-matrix",
        inputs=[],
        extra={"mode": mode, "people": people, "activities": activities},
    )
    out_root = io.engagement_dir(engagement, mode)
    out_root.mkdir(parents=True, exist_ok=True)
    out_path = out_root / "07-raci.md"
    frontmatter.write_md(out_path, fm, body)
    print(f"wrote {out_path}")
    return 0


def _parse_rows(body: str) -> list[list[str]]:
    out = []
    for line in body.splitlines():
        if line.startswith("|") and "---" not in line and "Activity" not in line:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells and cells[0]:
                out.append(cells)
    return out


def validate(args, lint_only: bool = False) -> int:
    from consultant_kit import frontmatter  # type: ignore

    path = Path(args.path)
    fm, body = frontmatter.parse(path)
    rows = _parse_rows(body)
    findings = []

    for row in rows:
        activity = row[0]
        cells = [c.upper() for c in row[1:]]
        a_count = cells.count("A")
        r_count = cells.count("R")
        any_role = sum(1 for c in cells if c in ("R", "A", "C", "I"))

        if a_count == 0:
            findings.append(("HIGH", f"`{activity}`: no Accountable — every row must have exactly one A"))
        elif a_count > 1:
            findings.append(("HIGH", f"`{activity}`: {a_count} Accountables — only one allowed"))
        if r_count == 0:
            findings.append(("MED", f"`{activity}`: no Responsible — at least one R expected"))
        if any_role == 0:
            findings.append(("MED", f"`{activity}`: no roles assigned"))

        if not lint_only:
            if cells.count("R") + cells.count("A") + cells.count("C") + cells.count("I") > 5:
                findings.append(("LOW", f"`{activity}`: >5 people involved — consider splitting activity"))
            if "C" not in cells and "I" not in cells:
                findings.append(("LOW", f"`{activity}`: no Consulted or Informed listed — likely too thin"))

    print(f"## raci-matrix {'validate' if lint_only else 'audit'} — {path.name}")
    print(f"engagement: {fm.get('engagement', '—')}")
    print()
    if not findings:
        print("✅ no findings — RACI is clean")
        return 0
    severity_order = {"HIGH": 0, "MED": 1, "LOW": 2}
    findings.sort(key=lambda f: severity_order[f[0]])
    for sev, msg in findings:
        print(f"- **{sev}** — {msg}")
    high = sum(1 for s, _ in findings if s == "HIGH")
    return 1 if high else 0


def main() -> int:
    p = argparse.ArgumentParser(prog="raci-matrix")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scaffold")
    s.add_argument("--engagement", required=True)
    s.add_argument("--mode", choices=("client", "pm", "ops", "life"), default=None)
    s.add_argument("--people", required=True)
    s.add_argument("--activities", required=True)
    s.set_defaults(func=scaffold)

    v = sub.add_parser("validate")
    v.add_argument("path")
    v.set_defaults(func=lambda a: validate(a, lint_only=True))

    a = sub.add_parser("audit")
    a.add_argument("path")
    a.set_defaults(func=lambda x: validate(x, lint_only=False))

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
