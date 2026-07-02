#!/usr/bin/env python3
"""minto-pyramid — answer-first storyline scaffold."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".claude/skills/_consultant/python"))
from _bootstrap_helper import ensure_venv  # noqa: E402

ensure_venv(__file__)

import argparse  # noqa: E402
import re  # noqa: E402


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


SCAFFOLD_BODY = """## Governing thought

> **{governing}** `[confidence: {confidence}]`

This is the single sentence that answers the SCQA Question. Every key below either proves or qualifies it.

## Key arguments

### Key 1 — [draft complete claim, not a topic]

Supporting:
- **S1.1** — _[claim]_ `upstream: <hypothesis-row-or-chart>`
- **S1.2** — _[claim]_ `[source: ...]`

### Key 2 — [draft complete claim]

Supporting:
- **S2.1** — _[claim]_ `upstream: ...`
- **S2.2** — _[claim]_ `[source: ...]`

### Key 3 — [draft complete claim]

Supporting:
- **S3.1** — _[claim]_ `upstream: ...`
- **S3.2** — _[claim]_ `[source: ...]`

## Hypothesis rollup

{rollup}

## Notes

- Every line is a complete claim, not a topic. Topic-as-key is flagged in `review`.
- Every supporting line cites either `upstream: <path>` or `[source: ...]`. Floating supporting lines are flagged.
- The pyramid rule: each supporting line must support the key directly above it. Promote/demote lines until every line reads as direct evidence.
- This file is the input to `consultant-deck` — every Key + Supporting line becomes a slide action title.
- Anchored on `MattZerg/_style/consultant_thinking_style.md`.

## Next

Approve the storyline before any `consultant-deck` render (Gate 3 in the engagement orchestrator).
"""


def scaffold(args) -> int:
    from consultant_kit import frontmatter, io  # type: ignore

    scqa_path = None
    hyp_path = None
    framework_paths: list[str] = []
    for p in args.from_paths:
        path = Path(p)
        fm, _ = frontmatter.parse(path)
        skill = fm.get("skill", "")
        if skill == "scqa-framing":
            scqa_path = path
        elif skill == "hypothesis-tree":
            hyp_path = path
        elif skill == "framework-library":
            framework_paths.append(str(path))

    engagement = args.engagement
    if not engagement and scqa_path:
        engagement = frontmatter.parse(scqa_path)[0].get("engagement")
    mode = args.mode or "ops"

    governing = "_[draft governing thought — must answer the SCQA Question]_"
    confidence = "low"
    if scqa_path:
        _, scqa_body = frontmatter.parse(scqa_path)
        answer = _extract_section(scqa_body, "answer")
        if answer:
            # take first paragraph as governing draft
            first_para = answer.split("\n\n")[0].strip()
            governing = first_para
            m = re.search(r"\[confidence:\s*(\w+)\]", answer)
            if m:
                confidence = m.group(1)

    rollup = "(no hypothesis tree provided)"
    if hyp_path:
        hyp_fm, _ = frontmatter.parse(hyp_path)
        rows = hyp_fm.get("rows", []) or []
        if rows:
            lines = []
            for r in rows:
                conf = r.get("confidence", "low")
                marker = {"high": "✅", "med": "🟡", "low": "🔴"}.get(conf, "🔴")
                lines.append(f"- {marker} **{r.get('id')}** [{conf}] {r.get('question','')[:80]} — _{r.get('initial_answer','')[:80]}_")
            rollup = "\n".join(lines)

    body = SCAFFOLD_BODY.format(governing=governing, confidence=confidence, rollup=rollup)

    if framework_paths:
        body += "\n## Framework artifacts cited\n"
        for fp in framework_paths:
            body += f"- `{fp}`\n"

    fm = frontmatter.envelope(
        engagement=engagement,
        slug=f"{io.slugify(engagement)}-minto",
        skill="minto-pyramid",
        inputs=args.from_paths,
        upstream=args.from_paths,
        extra={
            "mode": mode,
            "governing": governing,
            "confidence": confidence,
            "keys": ["[draft]", "[draft]", "[draft]"],
        },
    )

    out_root = io.engagement_dir(engagement, mode)
    out_root.mkdir(parents=True, exist_ok=True)
    out_path = out_root / "06-synthesis-minto.md"
    frontmatter.write_md(out_path, fm, body)
    print(f"wrote {out_path}")
    print("\nNEXT: tighten the Governing thought, fill the 3 Keys, link every supporting line.")
    print("Then approve before invoking consultant-deck (Gate 3).")
    return 0


KEY_PAT = re.compile(r"^###\s+Key\s+\d+\s+[—-]\s+(.+?)$", re.MULTILINE)
SUPPORT_PAT = re.compile(r"^- \*\*S\d+(?:\.\d+)?\*\*\s+[—-]\s+(.+?)$", re.MULTILINE)
TOPIC_PAT = re.compile(r"^\s*\[?[A-Za-z][\w\s-]{0,30}\]?\s*$")


def review(args) -> int:
    from consultant_kit import frontmatter  # type: ignore

    path = Path(args.path)
    fm, body = frontmatter.parse(path)
    findings = []

    # Governing thought
    gov_section = _extract_section(body, "governing thought")
    if not gov_section or "_[draft" in gov_section:
        findings.append(("HIGH", "Governing thought is still a draft placeholder"))
    elif "[confidence:" not in gov_section.lower():
        findings.append(("MED", "Governing thought missing `[confidence: ...]` tag"))

    # Keys
    keys = KEY_PAT.findall(body)
    if len(keys) < 2:
        findings.append(("HIGH", f"Only {len(keys)} keys parsed — Minto pyramid needs 3 supporting arguments"))
    for i, k in enumerate(keys):
        if k.startswith("[") or TOPIC_PAT.match(k) and "is" not in k.lower() and "are" not in k.lower():
            findings.append(("HIGH", f"Key {i+1} reads like a topic ({k[:50]!r}) — must be a complete claim"))

    # Supporting lines
    supports = SUPPORT_PAT.findall(body)
    if not supports:
        findings.append(("MED", "No supporting lines parsed — each key needs 2–4"))
    for s in supports:
        if "upstream:" not in s and "[source:" not in s and "[needs-verification]" not in s:
            findings.append(("MED", f"Supporting line lacks upstream cite: {s[:60]!r}"))

    severity_order = {"HIGH": 0, "MED": 1, "LOW": 2}
    findings.sort(key=lambda f: severity_order[f[0]])
    print(f"## minto-pyramid review — {path.name}")
    print(f"engagement: {fm.get('engagement', '—')}")
    print()
    if not findings:
        print("✅ no findings — pyramid is clean, ready for consultant-deck")
        return 0
    for sev, msg in findings:
        print(f"- **{sev}** — {msg}")
    high = sum(1 for s, _ in findings if s == "HIGH")
    return 1 if high else 0


def main() -> int:
    p = argparse.ArgumentParser(prog="minto-pyramid")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scaffold")
    s.add_argument("--engagement", default=None)
    s.add_argument("--mode", choices=("client", "pm", "ops", "life"), default=None)
    s.add_argument("--from", dest="from_paths", nargs="+", required=True)
    s.set_defaults(func=scaffold)

    r = sub.add_parser("review")
    r.add_argument("path")
    r.set_defaults(func=review)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
