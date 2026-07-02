#!/usr/bin/env python3
"""scqa-framing — Situation/Complication/Question/Answer scaffolder + reviewer."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".claude/skills/_consultant/python"))
from _bootstrap_helper import ensure_venv  # noqa: E402

ensure_venv(__file__)

import argparse  # noqa: E402
import re  # noqa: E402


# --- scaffold ---------------------------------------------------------------

SCAFFOLD_TEMPLATE = """## Situation

{situation}

## Complication

{complication}

## Question

{question}

## Answer

{answer} `[confidence: {confidence}]`

## Notes

- This SCQA is the anchor for `issue-tree`. The Question is the root.
- Sharpen before decomposing. If the Complication isn't surprising, rework Situation+Complication.
- Anchored on `MattZerg/_style/consultant_thinking_style.md`.
"""


def scaffold(args) -> int:
    from consultant_kit import frontmatter, io  # type: ignore

    brief = args.brief
    slug = args.slug or io.slugify(brief)[:40]

    situation = "**[draft from brief]** " + _first_sentences(brief, 3)
    complication = "**[draft — name the surprise]** What shifted to make this a decision? Replace this placeholder before Phase 2."
    question = "**[draft]** What is the single question whose answer drives action? End with `?`."
    answer = "**[draft]** Best current bet; sharpen after `issue-tree` + `hypothesis-tree`."
    confidence = "low"

    fm = frontmatter.envelope(
        engagement=args.engagement or slug,
        slug=f"{slug}-scqa",
        skill="scqa-framing",
        inputs=[brief[:120]],
        extra={"mode": args.mode, "brief_full": brief},
    )

    body = SCAFFOLD_TEMPLATE.format(
        situation=situation,
        complication=complication,
        question=question,
        answer=answer,
        confidence=confidence,
    )

    if args.engagement:
        out_root = io.engagement_dir(args.engagement, args.mode)
        out_root.mkdir(parents=True, exist_ok=True)
        out_path = out_root / "01-scqa.md"
    else:
        out_path = Path(args.out_dir or "/tmp/consultant/scqa-framing") / f"{slug}-scqa.md"

    frontmatter.write_md(out_path, fm, body)
    print(f"wrote {out_path}")
    print("\nNEXT: sharpen the Complication + Question, then invoke issue-tree --from", out_path)
    return 0


def _first_sentences(text: str, n: int) -> str:
    sents = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(sents[:n])


# --- review -----------------------------------------------------------------

HEDGE_WORDS = {
    "significant", "substantial", "robust", "comprehensive", "leverage",
    "synergies", "alignment", "rationalize", "best-in-class",
}
FLOATING_NUMBER_PAT = re.compile(r"\b\d+(?:\.\d+)?\s*(?:[KMB%]|million|billion)?\b")
CITED_NUMBER_PAT = re.compile(r"\d+[^\n\]]{0,40}?\]")  # rough: number then ] close shortly after


def review(args) -> int:
    from consultant_kit import frontmatter  # type: ignore

    path = Path(args.path)
    fm, body = frontmatter.parse(path)

    findings = []
    sections = _split_sections(body)

    # Question check
    q = sections.get("question", "").strip()
    if not q:
        findings.append(("HIGH", "Question section empty"))
    else:
        if not q.endswith("?"):
            findings.append(("HIGH", "Question does not end with '?' — likely a topic or statement, not a question"))
        if any(w in q.lower() for w in ("should we ", "do we ")) and " or " not in q.lower():
            findings.append(("MED", "Question reads like a yes/no — frame as 'what / which / how much' to leave the answer space open"))
        if len(q.split()) > 30:
            findings.append(("MED", f"Question is {len(q.split())} words — over 30 is usually two questions"))

    # Complication: is it surprising?
    c = sections.get("complication", "").strip().lower()
    if not c:
        findings.append(("HIGH", "Complication section empty"))
    elif any(k in c for k in ("as we grow", "as we scale", "going forward", "increasingly")):
        findings.append(("MED", "Complication uses 'as we grow / scale / going forward' — that's a trend, not a surprise. Name what broke."))

    # Answer
    a = sections.get("answer", "").strip()
    if not a:
        findings.append(("MED", "Answer empty — leave a low-confidence draft, don't leave blank"))
    elif "[confidence:" not in a.lower():
        findings.append(("LOW", "Answer missing `[confidence: low/med/high]` tag"))

    # Hedging adjectives
    body_low = body.lower()
    hedges = [w for w in HEDGE_WORDS if re.search(rf"\b{w}\b", body_low)]
    for w in hedges:
        findings.append(("LOW", f"Hedging word '{w}' — strike or replace with the number"))

    # Floating numbers
    numbers = FLOATING_NUMBER_PAT.findall(body)
    inline_sources = body.count("[source:") + body.count("[needs-verification]")
    if numbers and inline_sources < len(numbers):
        findings.append(("MED", f"{len(numbers)} numbers detected, {inline_sources} citation tags — some numbers may be floating without `[source: …]`"))

    severity_order = {"HIGH": 0, "MED": 1, "LOW": 2}
    findings.sort(key=lambda f: severity_order[f[0]])

    print(f"## scqa-framing review — {path.name}")
    print(f"engagement: {fm.get('engagement', '—')}")
    print()
    if not findings:
        print("✅ no findings — SCQA is sharp")
        return 0
    for sev, msg in findings:
        print(f"- **{sev}** — {msg}")
    high = sum(1 for s, _ in findings if s == "HIGH")
    return 1 if high else 0


def _split_sections(body: str) -> dict[str, str]:
    out: dict[str, str] = {}
    current = None
    buf: list[str] = []
    for line in body.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if current:
                out[current.lower()] = "\n".join(buf).strip()
            current = m.group(1).strip()
            buf = []
        else:
            buf.append(line)
    if current:
        out[current.lower()] = "\n".join(buf).strip()
    return out


def main() -> int:
    p = argparse.ArgumentParser(prog="scqa-framing")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scaffold")
    s.add_argument("brief")
    s.add_argument("--engagement", default=None)
    s.add_argument("--mode", choices=("client", "pm", "ops", "life"), default="ops")
    s.add_argument("--slug", default=None)
    s.add_argument("--out-dir", default=None)
    s.set_defaults(func=scaffold)

    r = sub.add_parser("review")
    r.add_argument("path")
    r.set_defaults(func=review)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
