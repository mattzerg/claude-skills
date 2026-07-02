#!/usr/bin/env python3
"""hypothesis-tree — initial answer + evidence required + analyses per issue-tree leaf."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".claude/skills/_consultant/python"))
from _bootstrap_helper import ensure_venv  # noqa: E402

ensure_venv(__file__)

import argparse  # noqa: E402
import re  # noqa: E402


LEAF_PAT = re.compile(r"\*\*L(\d+(?:\.\d+)*)\*\*\s+(.+?)$", re.MULTILINE)


def _parse_leaves(body: str) -> list[tuple[str, str]]:
    out = []
    for m in LEAF_PAT.finditer(body):
        lid = f"L{m.group(1)}"
        q = m.group(2).strip().rstrip(".")
        # Only include question leaves (not nested mermaid IDs etc.)
        if q.endswith("?") or q.startswith("["):
            out.append((lid, q))
    return out


SCAFFOLD_HEADER = """## Hypotheses

Table: one row per issue-tree leaf. Initial answer is Day-1 best guess.
**Falsifiability rule**: every row must have an analysis that would disprove the initial answer. Unfalsifiable hypotheses get killed.

| Leaf | Sub-question | Initial answer | Evidence that would PROVE | Evidence that would DISPROVE | Analyses to run | Confidence |
|---|---|---|---|---|---|---|
"""

SCAFFOLD_FOOTER = """
## Notes

- IDs (`H1.2`) derive from issue-tree leaf IDs (`L1.2`).
- `Analyses to run` should name a skill or external workstream — `cohort-analyzer`, `scenario-modeler`, `cost-benefit`, `market-sizing`, `competitive-review-skill`, `advise-bx`, "5 buyer interviews", "warehouse query".
- After Phase 2 lands, run `hypothesis-tree score` per row to update confidence + cite evidence paths.
- Anchored on `MattZerg/_style/consultant_thinking_style.md`.

## Next

After Phase 2 analyses land, return here with `score` to update confidence per row, then dispatch `minto-pyramid` for synthesis.
"""


def scaffold(args) -> int:
    from consultant_kit import frontmatter, io  # type: ignore

    path = Path(args.from_path)
    fm_up, body_up = frontmatter.parse(path)
    leaves = _parse_leaves(body_up)
    if not leaves:
        print(f"ERROR: no leaves parsed from {path}")
        return 1

    engagement = args.engagement or fm_up.get("engagement")
    mode = args.mode or fm_up.get("mode") or "ops"

    rows = []
    for lid, q in leaves:
        hid = "H" + lid[1:]
        rows.append(
            f"| {hid} | {q} | _[draft initial answer]_ | _[what proves it]_ | _[what disproves it]_ | _[name skills / workstreams]_ | low |"
        )

    body = SCAFFOLD_HEADER + "\n".join(rows) + SCAFFOLD_FOOTER

    fm = frontmatter.envelope(
        engagement=engagement,
        slug=f"{io.slugify(engagement)}-hypotheses",
        skill="hypothesis-tree",
        inputs=[str(path)],
        upstream=[str(path)],
        extra={
            "mode": mode,
            "rows": [
                {
                    "id": "H" + lid[1:],
                    "leaf": lid,
                    "question": q,
                    "initial_answer": "",
                    "evidence_prove": "",
                    "evidence_disprove": "",
                    "analyses": [],
                    "confidence": "low",
                }
                for lid, q in leaves
            ],
        },
    )

    out_root = io.engagement_dir(engagement, mode)
    out_root.mkdir(parents=True, exist_ok=True)
    out_path = out_root / "03-hypothesis-tree.md"
    frontmatter.write_md(out_path, fm, body)
    print(f"wrote {out_path}")
    print(f"\n{len(leaves)} hypothesis rows scaffolded. Each row needs an analysis path before Phase 2.")
    return 0


def score(args) -> int:
    from consultant_kit import frontmatter  # type: ignore

    path = Path(args.path)
    fm, body = frontmatter.parse(path)

    leaf_id = args.leaf
    hid = "H" + leaf_id.lstrip("L")

    # Find and update the row in the markdown body
    new_lines = []
    updated = False
    for line in body.splitlines():
        if line.startswith(f"| {hid} |"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if args.answer:
                cells[2] = args.answer
            if args.confidence:
                cells[-1] = args.confidence
            line = "| " + " | ".join(cells) + " |"
            updated = True
        new_lines.append(line)

    if not updated:
        print(f"ERROR: row for leaf {leaf_id} ({hid}) not found")
        return 1

    # Update structured rows in frontmatter
    rows = fm.get("rows", [])
    for r in rows:
        if r.get("id") == hid:
            if args.answer:
                r["initial_answer"] = args.answer
            if args.confidence:
                r["confidence"] = args.confidence
            if args.evidence_paths:
                r.setdefault("evidence_paths", [])
                r["evidence_paths"].extend(args.evidence_paths)
            break
    fm["rows"] = rows

    # Append evidence paths to upstream
    if args.evidence_paths:
        fm.setdefault("upstream", [])
        for p in args.evidence_paths:
            if p not in fm["upstream"]:
                fm["upstream"].append(p)

    frontmatter.write_md(path, fm, "\n".join(new_lines))
    print(f"updated {hid} in {path}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="hypothesis-tree")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scaffold")
    s.add_argument("--from", dest="from_path", required=True)
    s.add_argument("--engagement", default=None)
    s.add_argument("--mode", choices=("client", "pm", "ops", "life"), default=None)
    s.set_defaults(func=scaffold)

    c = sub.add_parser("score")
    c.add_argument("path")
    c.add_argument("--leaf", required=True, help="leaf ID, e.g. L1.2")
    c.add_argument("--answer", default=None)
    c.add_argument("--confidence", choices=("low", "med", "high"), default=None)
    c.add_argument("--evidence-paths", nargs="*", default=None)
    c.set_defaults(func=score)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
