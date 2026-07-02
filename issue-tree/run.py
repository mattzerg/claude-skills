#!/usr/bin/env python3
"""issue-tree — MECE decomposition of a question into a hierarchical issue tree."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".claude/skills/_consultant/python"))
from _bootstrap_helper import ensure_venv  # noqa: E402

ensure_venv(__file__)

import argparse  # noqa: E402
import re  # noqa: E402


# --- scaffold ---------------------------------------------------------------

SCAFFOLD_BODY = """## Root

> {root_q}

## Tree (placeholder — replace with the real decomposition)

- **L1** [Draft sub-question 1 — make it MECE with L2 and L3]?
  - **L1.1** [Draft deeper sub-question]?
  - **L1.2** [Draft deeper sub-question]?
- **L2** [Draft sub-question 2]?
  - **L2.1** [Draft deeper sub-question]?
  - **L2.2** [Draft deeper sub-question]?
- **L3** [Draft sub-question 3]?
  - **L3.1** [Draft deeper sub-question]?
  - **L3.2** [Draft deeper sub-question]?

## Notes

- Each leaf must end in `?`. Topic-only leaves ("Pricing") fail the MECE check.
- Aim for 3–5 children per node. Fewer means parent is too narrow; more means a layer is missing.
- Stable IDs (`L1.2.3`) propagate to `hypothesis-tree`, `framework-library`, `minto-pyramid`, and `consultant-deck`.
- Anchored on `MattZerg/_style/consultant_thinking_style.md`.

## Next

Invoke `hypothesis-tree --from <this-file>` to draft an initial answer + evidence-required per leaf.
"""


def _mermaid_from_leaves(root_q: str, leaves: list[tuple[str, str]]) -> str:
    """Render a mermaid flowchart from (id, question) pairs."""
    lines = ["```mermaid", "graph TD", '  Root["' + _esc(root_q[:80]) + '"]']
    for lid, q in leaves:
        parent_id = ".".join(lid.lstrip("L").split(".")[:-1])
        parent = "Root" if not parent_id else f"L{parent_id}"
        lines.append(f'  {parent} --> {lid}["{lid} {_esc(q[:60])}"]')
    lines.append("```")
    return "\n".join(lines)


def _esc(s: str) -> str:
    return s.replace('"', "'").replace("\n", " ")


def scaffold(args) -> int:
    from consultant_kit import frontmatter, io  # type: ignore

    upstream: list[str] = []
    if args.from_path:
        upstream.append(args.from_path)
        fm_up, body_up = frontmatter.parse(Path(args.from_path))
        root_q = _extract_section(body_up, "question") or args.question or "[draft question]"
        engagement = args.engagement or fm_up.get("engagement")
        mode = args.mode or fm_up.get("mode") or "ops"
    else:
        root_q = args.question or "[draft question]"
        engagement = args.engagement
        mode = args.mode or "ops"

    slug = io.slugify(engagement or root_q)[:40]
    placeholder_leaves = [
        ("L1", "[Draft sub-question 1]"),
        ("L1.1", "[Draft deeper sub-question]"),
        ("L1.2", "[Draft deeper sub-question]"),
        ("L2", "[Draft sub-question 2]"),
        ("L2.1", "[Draft deeper sub-question]"),
        ("L2.2", "[Draft deeper sub-question]"),
        ("L3", "[Draft sub-question 3]"),
        ("L3.1", "[Draft deeper sub-question]"),
        ("L3.2", "[Draft deeper sub-question]"),
    ]

    fm = frontmatter.envelope(
        engagement=engagement or slug,
        slug=f"{slug}-issue-tree",
        skill="issue-tree",
        inputs=[args.from_path] if args.from_path else [args.question or ""],
        upstream=upstream,
        extra={
            "mode": mode,
            "root_question": root_q,
            "leaves": [{"id": lid, "q": q} for lid, q in placeholder_leaves],
        },
    )

    body = SCAFFOLD_BODY.format(root_q=root_q)
    body += "\n\n## Mermaid\n\n" + _mermaid_from_leaves(root_q, placeholder_leaves) + "\n"

    if engagement:
        out_root = io.engagement_dir(engagement, mode)
        out_root.mkdir(parents=True, exist_ok=True)
        out_path = out_root / "02-issue-tree.md"
    else:
        out_path = Path(args.out_dir or "/tmp/consultant/issue-tree") / f"{slug}-tree.md"

    frontmatter.write_md(out_path, fm, body)
    # Also write a standalone .mmd file
    mmd_path = out_path.with_suffix(".mmd")
    mmd_path.write_text(_mermaid_from_leaves(root_q, placeholder_leaves).replace("```mermaid\n", "").replace("\n```", ""))
    print(f"wrote {out_path}")
    print(f"wrote {mmd_path}")
    print("\nNEXT: invoke hypothesis-tree --from", out_path)
    return 0


# --- review / mece-check ----------------------------------------------------

LEAF_PAT = re.compile(r"\*\*L(\d+(?:\.\d+)*)\*\*\s+(.+?)$", re.MULTILINE)
STOPWORDS = {"the", "and", "or", "is", "to", "for", "of", "in", "on", "a", "an", "we", "our", "their", "are", "be"}


def _extract_section(body: str, name: str) -> str:
    current = None
    buf: list[str] = []
    for line in body.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if current and current.lower() == name.lower():
                return "\n".join(buf).strip()
            current = m.group(1).strip()
            buf = []
        elif current:
            buf.append(line)
    if current and current.lower() == name.lower():
        return "\n".join(buf).strip()
    return ""


def _parse_leaves(body: str) -> list[tuple[str, str]]:
    out = []
    for m in LEAF_PAT.finditer(body):
        out.append((f"L{m.group(1)}", m.group(2).strip().rstrip(".")))
    return out


def _keywords(s: str) -> set[str]:
    words = re.findall(r"\b[a-z]+\b", s.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 2}


def review(args, lint_only: bool = False) -> int:
    from consultant_kit import frontmatter  # type: ignore

    path = Path(args.path)
    fm, body = frontmatter.parse(path)
    leaves = _parse_leaves(body)

    findings = []

    if not leaves:
        findings.append(("HIGH", "No leaves parsed — tree body uses unexpected format"))
        return _emit(findings, path, fm)

    # Topic leaves (no ?)
    for lid, q in leaves:
        if not q.endswith("?") and not q.startswith("["):
            findings.append(("HIGH", f"Leaf {lid} is a topic, not a question (missing `?`): '{q[:60]}'"))

    # Branch count
    children: dict[str, list[str]] = {}
    for lid, _ in leaves:
        parts = lid.lstrip("L").split(".")
        if len(parts) == 1:
            children.setdefault("root", []).append(lid)
        else:
            parent = "L" + ".".join(parts[:-1])
            children.setdefault(parent, []).append(lid)
    for parent, kids in children.items():
        if len(kids) < 3:
            findings.append(("MED", f"Parent {parent} has only {len(kids)} children — fewer than 3 usually means too narrow"))
        elif len(kids) > 5:
            findings.append(("MED", f"Parent {parent} has {len(kids)} children — more than 5 means a layer is missing"))

    # Depth
    max_depth = max(lid.count(".") + 1 for lid, _ in leaves)
    if max_depth > 3:
        findings.append(("MED", f"Tree depth is {max_depth} — over 3 usually means the root Question is wrong"))

    # Overlap candidates among siblings
    by_parent = {}
    for lid, q in leaves:
        if q.startswith("["):
            continue
        parts = lid.lstrip("L").split(".")
        parent = "root" if len(parts) == 1 else "L" + ".".join(parts[:-1])
        by_parent.setdefault(parent, []).append((lid, _keywords(q)))
    for parent, sibs in by_parent.items():
        for i in range(len(sibs)):
            for j in range(i + 1, len(sibs)):
                overlap = sibs[i][1] & sibs[j][1]
                if len(overlap) >= 3:
                    findings.append((
                        "MED",
                        f"Leaves {sibs[i][0]} and {sibs[j][0]} share {len(overlap)} keywords ({', '.join(sorted(overlap)[:4])}) — possible MECE violation",
                    ))

    # Root drift vs SCQA upstream
    if not lint_only and fm.get("upstream"):
        for up in fm["upstream"]:
            up_path = Path(up)
            if up_path.exists():
                up_fm, up_body = frontmatter.parse(up_path)
                up_q = _extract_section(up_body, "question")
                root_q = fm.get("root_question") or _extract_section(body, "root")
                if up_q and root_q and _keywords(up_q) != _keywords(root_q):
                    overlap_pct = (
                        len(_keywords(up_q) & _keywords(root_q)) / max(len(_keywords(up_q)), 1)
                    )
                    if overlap_pct < 0.5:
                        findings.append((
                            "MED",
                            f"Tree root question may have drifted from upstream SCQA — keyword overlap {int(overlap_pct*100)}%",
                        ))

    return _emit(findings, path, fm)


def _emit(findings: list[tuple[str, str]], path: Path, fm: dict) -> int:
    severity_order = {"HIGH": 0, "MED": 1, "LOW": 2}
    findings.sort(key=lambda f: severity_order[f[0]])
    print(f"## issue-tree review — {path.name}")
    print(f"engagement: {fm.get('engagement', '—')}")
    print()
    if not findings:
        print("✅ no findings — tree is MECE-clean")
        return 0
    for sev, msg in findings:
        print(f"- **{sev}** — {msg}")
    high = sum(1 for s, _ in findings if s == "HIGH")
    return 1 if high else 0


def main() -> int:
    p = argparse.ArgumentParser(prog="issue-tree")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scaffold")
    s.add_argument("question", nargs="?", default=None)
    s.add_argument("--from", dest="from_path", default=None)
    s.add_argument("--engagement", default=None)
    s.add_argument("--mode", choices=("client", "pm", "ops", "life"), default=None)
    s.add_argument("--out-dir", default=None)
    s.set_defaults(func=scaffold)

    for verb in ("review", "mece-check"):
        r = sub.add_parser(verb)
        r.add_argument("path")
        r.set_defaults(func=lambda a, v=verb: review(a, lint_only=(v == "mece-check")))

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
