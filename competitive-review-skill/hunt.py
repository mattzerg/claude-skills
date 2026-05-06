#!/usr/bin/env python3
"""
hunt.py — differentiator-hunt phase.

Beyond the 4-bucket gap analysis, ask Claude to actively propose 5-10 features the
Zerg product could ship that nobody in the competitor set has and would be hard to
architecturally copy. This is the offensive layer that complements the defensive
"close table-stakes" rankings.

Reads state from compare; writes:
  - state.differentiation_opportunities (list of {name, why, pillar, defensibility})
  - vault: MattZerg/Competitive/<category>/differentiation-opportunities.md

Usage:
    python3 hunt.py <category> --product <ZergProduct>
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from lib import claude, state, vault


HUNT_PROMPT = """You are a product strategist hunting for offensive moves Zerg can make in the "{category}" market.

The defensive analysis (close table-stakes gaps) is already done. Your job: propose 5-10 concrete features the Zerg product "{product}" could ship that NO competitor in the scanned set has, and that would be ARCHITECTURALLY HARD to copy without rebuilding their stack.

ZSTACK DIFFERENTIATION PILLARS (universal moats every Zerg product shares):
1. AI-native — agents are first-class participants in the product surface, not bolted-on bots
2. Zstack-interconnected — shared auth, agents, and data primitives across products
3. Much cheaper — Zerg undercuts category leaders heavily on price by design
4. Much easier to interlink/automate — agent context flows across products without webhook scaffolding

PRODUCT SPEC (what we have / claim):
{spec_text}

POSITIONING (positioning brief from this review):
- Elevator: {elevator}
- Differentiator one-liners:
{diff_lines}

CURRENT WHITESPACE (features no competitor has, but we don't either):
{whitespace}

CURRENT WE-HAVE-THEY-DON'T (our existing differentiators):
{ours}

COMPETITOR SUMMARY:
{competitors}

YOUR JOB

Return JSON with 5-10 differentiator candidates:

{{
  "opportunities": [
    {{
      "name": "feature name (specific, not generic)",
      "what": "1-line: what does it do",
      "why_now": "why this is the right time to ship it (market gap, agent-shift, pricing pressure)",
      "pillar": "which Zstack pillar this advances most: ai-native | zstack-interconnected | cheaper | automation",
      "defensibility": "why competitors architecturally can't copy this in <6 months",
      "evidence": "competitor weakness or user-pain quote that points to this",
      "effort": "S | M | L",
      "ranking": 1
    }}
  ]
}}

Rules:
1. Be SPECIFIC. "Better integration" is not an opportunity. "Agent-completed sub-issues that auto-close parent cards via webhook+API+ZTC" is.
2. Each opportunity must EITHER advance one of the 4 Zstack pillars OR have a defensibility moat that competitors can't quickly replicate.
3. Lean on observed competitor weakness — if Linear/Asana have the same gap, that's a tell.
4. Don't propose generic "AI features" — those are easy to copy. Propose features that REQUIRE the Zstack architecture or agent-first surface to work.
5. Rank by: defensibility × strategic-fit × ship-feasibility. Best opportunity = #1.

Return only valid JSON. No prose."""


def main():
    parser = argparse.ArgumentParser(description="Hunt for product-specific differentiation opportunities")
    parser.add_argument("category")
    parser.add_argument("--product", required=True)
    args = parser.parse_args()

    s = state.load(args.category)
    if not s.get("matrix"):
        print(f"Error: no matrix in state for {args.category}. Run compare.py first.", file=sys.stderr)
        sys.exit(1)

    matrix = s.get("matrix", [])
    positioning = s.get("positioning") or {}
    spec = s.get("spec") or {}
    spec_text = (spec.get("body") or "")[:3000]

    whitespace = [m["feature"] for m in matrix if m.get("bucket") == "whitespace"][:15]
    ours = [m["feature"] for m in matrix if m.get("bucket") == "we_have_they_dont"][:10]

    diff_lines_str = "\n".join(f"  - {l}" for l in (positioning.get("core_differentiator_lines") or [])[:5])
    elevator = positioning.get("elevator_pitch", "")

    competitors = []
    for dom, scan in (s.get("scans") or {}).items():
        a = scan.get("analysis", {}) or {}
        if a.get("error"):
            continue
        competitors.append(
            f"- {a.get('name', dom)}: {a.get('value_proposition', '?')} "
            f"(complaints: {' | '.join((a.get('user_sentiment',{}) or {}).get('complaints', [])[:2])})"
        )
    competitors_str = "\n".join(competitors[:15])

    prompt = HUNT_PROMPT.format(
        category=args.category,
        product=args.product,
        spec_text=spec_text or "(no spec text available)",
        elevator=elevator or "(no positioning brief)",
        diff_lines=diff_lines_str or "  (no differentiator lines yet)",
        whitespace=", ".join(whitespace) or "(none surfaced)",
        ours=", ".join(ours) or "(none surfaced — spec may need to claim differentiators)",
        competitors=competitors_str or "(no competitor data)",
    )

    print(f"[hunt] sending {len(prompt)} chars to Claude...", file=sys.stderr)
    result = claude.call_claude_json(prompt, timeout=600)
    if not isinstance(result, dict):
        print(f"Error: malformed hunt result: {str(result)[:500]}", file=sys.stderr)
        sys.exit(1)
    opportunities = result.get("opportunities", [])
    state.update(args.category, differentiation_opportunities=opportunities, hunted_at=datetime.now().isoformat())

    # Write differentiation-opportunities.md to vault
    out_dir = vault.category_dir(args.category)
    if out_dir.exists():
        body = ["# Differentiation opportunities\n",
                f"_Hunted {datetime.now().strftime('%Y-%m-%d')}. {len(opportunities)} candidates._\n",
                "Specific features Zerg could ship that no scanned competitor has, ranked by defensibility × fit × feasibility.\n"]
        for i, opp in enumerate(opportunities, 1):
            body.append(f"## {i}. {opp.get('name','?')}")
            body.append(f"- **What:** {opp.get('what','?')}")
            body.append(f"- **Why now:** {opp.get('why_now','?')}")
            body.append(f"- **Pillar:** {opp.get('pillar','?')}")
            body.append(f"- **Defensibility:** {opp.get('defensibility','?')}")
            body.append(f"- **Evidence:** {opp.get('evidence','?')}")
            body.append(f"- **Effort:** {opp.get('effort','?')}")
            body.append("")
        out_path = out_dir / "differentiation-opportunities.md"
        out_path.write_text("\n".join(body), encoding="utf-8")
        print(f"[hunt] wrote {out_path}")

    print(f"\n[hunt] done. {len(opportunities)} opportunities.")
    for opp in opportunities[:3]:
        print(f"  {opp.get('ranking','?')}. {opp.get('name','?')} ({opp.get('pillar','?')})")


if __name__ == "__main__":
    main()
