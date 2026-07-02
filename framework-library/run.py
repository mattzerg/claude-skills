#!/usr/bin/env python3
"""framework-library — render/suggest/audit named strategic frameworks."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".claude/skills/_consultant/python"))
from _bootstrap_helper import ensure_venv  # noqa: E402

ensure_venv(__file__)

import argparse  # noqa: E402
import re  # noqa: E402

import yaml  # noqa: E402

CARDS_DIR = Path.home() / ".claude/skills/_consultant/_knowledge/consulting/frameworks"


def load_cards() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path in CARDS_DIR.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        if text.startswith("---\n"):
            end = text.find("\n---\n", 4)
            if end > 0:
                meta = yaml.safe_load(text[4:end]) or {}
                meta["_body"] = text[end + 5 :].strip()
                meta["_path"] = str(path)
                out[meta.get("id", path.stem)] = meta
    return out


# --- suggest ----------------------------------------------------------------

SUGGEST_HINTS = [
    # (keyword set, framework-id, rationale)
    (("portfolio", "products", "skus", "lines"), "bcg", "Multi-product portfolio call"),
    (("industry", "market structure", "entry", "exit", "category attractiveness"), "porter-5f", "Industry-structure question"),
    (("prioritize", "effort", "impact", "quick wins"), "2x2", "Two-axis prioritization"),
    (("vendor", "selection", "alternatives", "options"), "pugh", "Concept selection across alternatives"),
    (("weights", "scoring", "criteria"), "weighted-scoring", "Multi-criteria with weights"),
    (("vertical", "outsource", "in-house", "build vs buy"), "value-chain", "Activity-by-activity ownership call"),
    (("business model", "go to market", "new venture", "model canvas"), "bmc", "Business-model design"),
    (("accountability", "ownership", "raci", "roles"), "raci", "Cross-functional accountability"),
    (("situation", "snapshot", "swot", "starting point"), "swot", "Situational snapshot at start of planning"),
]


def suggest(args) -> int:
    cards = load_cards()
    q = args.question.lower()
    scored: list[tuple[int, str, str, dict]] = []
    for kws, fid, rationale in SUGGEST_HINTS:
        score = sum(1 for k in kws if k in q)
        if score > 0 and fid in cards:
            scored.append((score, fid, rationale, cards[fid]))

    scored.sort(reverse=True, key=lambda x: x[0])
    print(f"## framework-library suggestions for: {args.question[:80]}")
    print()
    if not scored:
        print("No strong matches. Default candidates:")
        scored = [(0, fid, "default", cards[fid]) for fid in ("2x2", "swot", "porter-5f") if fid in cards]
    for score, fid, rationale, card in scored[:3]:
        print(f"- **{card.get('name', fid)}** (`{fid}`) — {rationale} [score: {score}]")
        wnt = card.get("when_not_to_use") or []
        for w in wnt[:2]:
            print(f"  - ⚠️ skip if: {w}")
    return 0


# --- render -----------------------------------------------------------------

def _check_when_not_to_use(card: dict, brief: str) -> list[str]:
    hits = []
    body_low = (brief or "").lower()
    for w in card.get("when_not_to_use") or []:
        # crude keyword overlap
        keywords = re.findall(r"[a-z]+", w.lower())
        sig = [k for k in keywords if len(k) > 4]
        matches = sum(1 for k in sig if k in body_low)
        if matches >= 3:
            hits.append(w)
    return hits


def render(args) -> int:
    from consultant_kit import frontmatter, io  # type: ignore

    cards = load_cards()
    if args.framework not in cards:
        print(f"ERROR: unknown framework {args.framework!r}. Known: {sorted(cards)}")
        return 1
    card = cards[args.framework]

    brief = args.question or ""
    if args.from_path:
        fm_up, body_up = frontmatter.parse(Path(args.from_path))
        brief = brief or (fm_up.get("root_question") or body_up[:400])

    blockers = _check_when_not_to_use(card, brief)
    if blockers and not args.force:
        print(f"## REFUSED — framework {args.framework!r} matches `when_not_to_use`:")
        for b in blockers:
            print(f"  - {b}")
        print("\nUse `--force` to override or pick a different framework (run `suggest`).")
        return 2

    items = [s.strip() for s in (args.items or "").split(",") if s.strip()]
    engagement = args.engagement or io.slugify(brief[:40])
    mode = args.mode or "ops"
    slug = io.slugify(engagement)[:40]

    body_parts = []
    body_parts.append(f"## {card.get('name', args.framework)}\n")
    if brief:
        body_parts.append(f"**Question / context:** {brief}\n")
    body_parts.append(f"**When to use:**\n")
    for w in card.get("when_to_use") or []:
        body_parts.append(f"- {w}")
    body_parts.append("")
    body_parts.append(f"**When NOT to use:**\n")
    for w in card.get("when_not_to_use") or []:
        body_parts.append(f"- {w}")
    body_parts.append("")

    # Framework-specific scaffold
    fid = args.framework
    if fid == "2x2":
        ax_x, ax_y = (args.axes.split(",") + ["Effort", "Impact"])[:2] if args.axes else ("Effort", "Impact")
        body_parts.append(f"**Axes:** x = {ax_x.strip()}; y = {ax_y.strip()}\n")
        body_parts.append("| Item | x | y | Quadrant | Action |\n|---|---|---|---|---|")
        for it in items or ["[Item 1]", "[Item 2]", "[Item 3]"]:
            body_parts.append(f"| {it} | _[1-10]_ | _[1-10]_ | _[auto]_ | _[verb]_ |")
    elif fid == "porter-5f":
        body_parts.append("| Force | Score (1-5) | Evidence + named number |\n|---|---|---|")
        for f in card.get("forces", []):
            body_parts.append(f"| {f} | _?_ | _[evidence + number]_ `[needs-verification]` |")
    elif fid == "bcg":
        body_parts.append("| Product | Relative share | Market growth % | Quadrant | Capital action |\n|---|---|---|---|---|")
        for it in items or ["[Product A]", "[Product B]", "[Product C]"]:
            body_parts.append(f"| {it} | _?_ | _?_ | _[auto]_ | _[invest/milk/decide/divest]_ |")
    elif fid == "value-chain":
        body_parts.append("### Primary activities")
        body_parts.append("| Stage | Margin captured | Strategic importance (1-5) |\n|---|---|---|")
        for stage in card.get("primary_activities", []):
            body_parts.append(f"| {stage} | _$?_ `[needs-verification]` | _?_ |")
        body_parts.append("\n### Support activities")
        body_parts.append("| Function | Differentiation impact | Cost |\n|---|---|---|")
        for stage in card.get("support_activities", []):
            body_parts.append(f"| {stage} | _?_ | _$?_ `[needs-verification]` |")
    elif fid == "bmc":
        body_parts.append("| Block | Content (≤30 words; concrete entities + named numbers) |\n|---|---|")
        for b in card.get("blocks", []):
            body_parts.append(f"| **{b}** | _[fill — concrete entities only]_ |")
    elif fid == "raci":
        people = items or ["[Person 1]", "[Person 2]", "[Person 3]"]
        head = "| Activity | " + " | ".join(people) + " |"
        sep = "|---" + ("|---" * len(people)) + "|"
        body_parts.append(head)
        body_parts.append(sep)
        for a in ["[Activity 1]", "[Activity 2]", "[Activity 3]"]:
            row = f"| {a} | " + " | ".join("_?_" for _ in people) + " |"
            body_parts.append(row)
        body_parts.append("\nLegend: R=Responsible, A=Accountable, C=Consulted, I=Informed. **Each row must have exactly one A.**")
    elif fid == "pugh":
        opts = items or ["Baseline", "Option A", "Option B"]
        head = "| Criterion | " + " | ".join(opts) + " |"
        sep = "|---" + ("|---" * len(opts)) + "|"
        body_parts.append(head)
        body_parts.append(sep)
        for c in ["[Criterion 1]", "[Criterion 2]", "[Criterion 3]"]:
            row = f"| {c} | 0 | _+/-/0_ | _+/-/0_ |"
            body_parts.append(row)
        body_parts.append("| **Sum** | 0 | _Σ_ | _Σ_ |")
    elif fid == "weighted-scoring":
        opts = items or ["Option A", "Option B", "Option C"]
        head = "| Criterion | Weight | " + " | ".join(opts) + " |"
        sep = "|---|---" + ("|---" * len(opts)) + "|"
        body_parts.append(head)
        body_parts.append(sep)
        for c in ["[Criterion 1]", "[Criterion 2]", "[Criterion 3]"]:
            row = f"| {c} | _w_ | _score_ | _score_ | _score_ |"
            body_parts.append(row)
        body_parts.append("| **Weighted total** | | _Σ_ | _Σ_ | _Σ_ |")
        body_parts.append("\nRun sensitivity: ±30% on the top weight; if ranking flips, the answer is the weight, not the analysis.")
    elif fid == "swot":
        body_parts.append("| | Internal | External |\n|---|---|---|")
        body_parts.append("| **Helpful** | **Strengths**<br>- _[named number]_<br>- _[named entity]_ | **Opportunities**<br>- _[named market signal]_ |")
        body_parts.append("| **Harmful** | **Weaknesses**<br>- _[named gap + number]_ | **Threats**<br>- _[named competitor / event]_ |")
        body_parts.append("\n### Cross-pairs (the real output)\n- **S×O leverage**: ...\n- **W×O improve**: ...\n- **S×T defend**: ...\n- **W×T avoid**: ...")

    body_parts.append("\n## Anti-patterns (this card flags)")
    for ap in card.get("anti_patterns") or []:
        body_parts.append(f"- {ap}")

    body_parts.append("\n## Notes")
    body_parts.append(f"- Recipe card: `{card['_path']}`")
    body_parts.append(f"- Chart recipe: `{card.get('chart_recipe') or '—'}`")
    body_parts.append("- Anchored on `MattZerg/_style/consultant_thinking_style.md`.")

    body = "\n".join(body_parts)

    fm = frontmatter.envelope(
        engagement=engagement,
        slug=f"{slug}-{fid}",
        skill="framework-library",
        inputs=[args.from_path or args.question or ""],
        upstream=[args.from_path] if args.from_path else [],
        extra={"framework": fid, "mode": mode, "items": items, "axes": args.axes},
    )

    if args.engagement:
        out_root = io.engagement_dir(args.engagement, mode) / "frameworks"
    else:
        out_root = Path(args.out_dir or "/tmp/consultant/framework-library")
    out_root.mkdir(parents=True, exist_ok=True)
    out_path = out_root / f"{fid}-{slug}.md"
    frontmatter.write_md(out_path, fm, body)
    print(f"wrote {out_path}")

    # Optional chart render
    if card.get("chart_recipe") and args.with_chart:
        try:
            from consultant_kit import chart  # type: ignore
            chart_path = out_path.with_suffix(".png")
            if fid == "2x2" and items:
                x_lab, y_lab = "Effort", "Impact"
                if args.axes:
                    parts = [s.strip() for s in args.axes.split(",")]
                    if len(parts) >= 2:
                        x_lab, y_lab = parts[0], parts[1]
                chart.render(
                    "scatter-2x2", out=chart_path,
                    items=[{"label": it, "x": i + 1, "y": (len(items) - i)} for i, it in enumerate(items)],
                    x_label=x_lab,
                    y_label=y_lab,
                )
                print(f"wrote {chart_path}")
        except Exception as e:  # noqa: BLE001
            print(f"  (chart render skipped: {e})")

    return 0


# --- audit ------------------------------------------------------------------

def audit(args) -> int:
    from consultant_kit import frontmatter  # type: ignore

    path = Path(args.path)
    fm, body = frontmatter.parse(path)
    fid = fm.get("framework") or fm.get("extra", {}).get("framework")
    if not fid:
        print(f"ERROR: cannot identify framework from {path}")
        return 1
    cards = load_cards()
    card = cards.get(fid)
    if not card:
        print(f"ERROR: unknown framework {fid!r}")
        return 1

    findings = []
    # Generic checks
    if "[needs-verification]" in body and fm.get("mode") == "client":
        findings.append(("HIGH", "Client-mode artifact carries `[needs-verification]` tags — must resolve before deliverable"))
    if not re.search(r"\b\d+\b", body):
        findings.append(("MED", "No numbers found in body — framework lacks quantitative anchor"))

    # Framework-specific
    if fid == "raci":
        # each non-header row should have exactly one A
        for line in body.splitlines():
            if line.startswith("|") and "Activity" not in line and "---" not in line:
                cells = [c.strip() for c in line.strip("|").split("|")]
                a_count = sum(1 for c in cells[1:] if c.upper() == "A")
                if a_count > 1:
                    findings.append(("HIGH", f"Row '{cells[0][:30]}' has {a_count} A's — only one allowed"))
                elif a_count == 0 and cells[0] and not cells[0].startswith("["):
                    findings.append(("HIGH", f"Row '{cells[0][:30]}' has no A — Accountable column empty"))

    severity_order = {"HIGH": 0, "MED": 1, "LOW": 2}
    findings.sort(key=lambda f: severity_order[f[0]])
    print(f"## framework-library audit — {path.name} ({fid})")
    if not findings:
        print("✅ no findings — framework is clean")
        return 0
    for sev, msg in findings:
        print(f"- **{sev}** — {msg}")
    high = sum(1 for s, _ in findings if s == "HIGH")
    return 1 if high else 0


def main() -> int:
    p = argparse.ArgumentParser(prog="framework-library")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("render")
    r.add_argument("framework")
    r.add_argument("--engagement", default=None)
    r.add_argument("--mode", choices=("client", "pm", "ops", "life"), default=None)
    r.add_argument("--from", dest="from_path", default=None)
    r.add_argument("--items", default=None, help="comma-separated items / options / activities")
    r.add_argument("--axes", default=None, help="e.g. 'Effort,Impact' for 2x2")
    r.add_argument("--question", default=None)
    r.add_argument("--out-dir", default=None)
    r.add_argument("--force", action="store_true", help="override when_not_to_use refusal")
    r.add_argument("--with-chart", action="store_true", help="render the chart_recipe as PNG")
    r.set_defaults(func=render)

    s = sub.add_parser("suggest")
    s.add_argument("question")
    s.set_defaults(func=suggest)

    a = sub.add_parser("audit")
    a.add_argument("path")
    a.set_defaults(func=audit)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
