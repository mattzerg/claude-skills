#!/usr/bin/env python3
"""
Landing Page Auditor — compare competitors against Zerg pages and produce ranked recommendations.
Uses the Claude Code CLI (claude --print) — no separate API key needed.

Usage:
    # Analyze and compare in one pass:
    python3 audit.py --urls https://cursor.com https://devin.ai --zerg-urls https://zergai.com

    # Use previously saved insights:
    python3 audit.py --insights-dir ./insights --zerg-urls https://zergai.com

    # Save report to file:
    python3 audit.py --urls https://cursor.com --zerg-urls https://zergai.com --output ~/Desktop/audit.md
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SKILL_DIR = Path(__file__).parent
INSIGHTS_DIR = SKILL_DIR / "insights"
CLAUDE_BIN = str(Path.home() / ".local" / "bin" / "claude")

_AITR_SCRIPTS = Path.home() / ".claude" / "skills" / "aitr" / "scripts"
_ROUTED_MODEL = None


def _routed_model() -> str:
    """aitr-routed CLI model (flat Max-plan); loud fallback to sonnet-4-6. Memoized."""
    global _ROUTED_MODEL
    if _ROUTED_MODEL is None:
        if str(_AITR_SCRIPTS) not in sys.path:
            sys.path.insert(0, str(_AITR_SCRIPTS))
        try:
            from skill_default import aitr_model_or
            _ROUTED_MODEL = aitr_model_or(
                "claude-sonnet-4-6", task_kind="prose-review", caller="landing-page-audit",
                quality_floor="medium",
            )
        except ImportError:
            _ROUTED_MODEL = "claude-sonnet-4-6"
    return _ROUTED_MODEL


AUDIT_PROMPT = """You are a senior conversion rate optimizer and brand strategist advising Zerg AI.

Zerg AI context:
- AI agent platform for autonomous software development targeting enterprise/mission-critical engineering teams
- Products: ZDE (web IDE), ZTC (terminal), Zergboard (project management), Zerg Cloud
- Design language: dark + cream/beige, mono typography, technical/premium aesthetic
- Positioning: serious AI for serious engineering work (NOT consumer/hobbyist)

COMPETITOR INSIGHTS:
{competitor_insights}

ZERG PAGE INSIGHTS:
{zerg_insights}

Produce a comprehensive audit report as JSON:
{{
  "executive_summary": "2-3 sentence overall assessment of Zerg's positioning vs competitors",
  "competitive_landscape": {{
    "patterns_across_competitors": ["patterns that appear in 3+ competitor pages"],
    "best_in_class": {{"element": "what it is", "source": "which competitor does this best", "description": "details"}},
    "market_gaps": ["opportunities none of the competitors are owning that Zerg could"]
  }},
  "zerg_assessment": {{
    "strengths": ["what Zerg's pages do well vs competitors"],
    "gaps": ["meaningful things competitors do that Zerg doesn't"],
    "positioning_clarity": "assessment of how clear Zerg's value prop is",
    "conversion_bottlenecks": ["specific friction points that likely reduce conversions"]
  }},
  "recommendations": [
    {{
      "priority": 1,
      "category": "headline|cta|social_proof|pricing|copy|design|trust|structure",
      "title": "short recommendation title",
      "current_state": "what Zerg does now",
      "recommendation": "specific, actionable change",
      "rationale": "why this matters based on competitor data",
      "effort": "low|medium|high",
      "impact": "low|medium|high"
    }}
  ],
  "quick_wins": ["3-5 changes that are low effort and high impact"],
  "copy_rewrites": [
    {{
      "element": "H1/subheadline/CTA/etc",
      "current": "current text",
      "suggested": "improved version",
      "why": "brief rationale"
    }}
  ],
  "new_sections_to_add": [
    {{
      "section": "section name",
      "rationale": "why based on competitor analysis",
      "content_guidance": "what should go in it"
    }}
  ]
}}

Return only valid JSON. Be specific — quote actual text, reference actual competitor patterns.
Rank recommendations 1 = highest priority. Include at least 8 recommendations."""


def call_claude(prompt: str) -> str:
    result = subprocess.run(
        [CLAUDE_BIN, "--print", "--model", _routed_model(), "--tools", ""],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=600
    )
    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI error: {result.stderr.strip()}")
    return result.stdout.strip()


def load_insights_from_dir(directory: Path) -> list[dict]:
    insights = []
    for f in sorted(directory.glob("*.json")):
        if f.name.startswith("audit_"):
            continue
        try:
            data = json.loads(f.read_text())
            insights.append(data)
        except Exception as e:
            print(f"  Warning: Could not load {f.name}: {e}")
    return insights


def run_analysis(urls: list[str], save_dir: Path, take_screenshot: bool) -> list[dict]:
    sys.path.insert(0, str(SKILL_DIR))
    from analyze import analyze_url
    results = []
    for url in urls:
        if not url.startswith("http"):
            url = "https://" + url
        results.append(analyze_url(url, save_dir, take_screenshot))
    return results


def generate_audit(competitor_insights: list[dict], zerg_insights: list[dict]) -> dict:
    def trim(insights_list, max_per=3000):
        trimmed = []
        for ins in insights_list:
            s = json.dumps({k: v for k, v in ins.items() if k not in ("raw", "analyzed_at")})
            trimmed.append(s[:max_per])
        return "\n\n---\n\n".join(trimmed)

    prompt = AUDIT_PROMPT.format(
        competitor_insights=trim(competitor_insights),
        zerg_insights=trim(zerg_insights)
    )

    print("\nGenerating audit report with Claude...")
    raw = call_claude(prompt)
    raw = re.sub(r'^```(?:json)?\n?', '', raw)
    raw = re.sub(r'\n?```$', '', raw)
    idx = raw.find('{')
    if idx > 0:
        raw = raw[idx:]
    last = raw.rfind('}')
    if last != -1:
        raw = raw[:last+1]

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Warning: JSON parse error: {e}")
        return {"raw_report": raw, "parse_error": str(e)}


def format_report(audit: dict, output_path: Path = None) -> str:
    lines = []
    lines.append("# Landing Page Competitive Audit")
    lines.append(f"_Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}_\n")

    if "executive_summary" in audit:
        lines.append("## Executive Summary")
        lines.append(audit["executive_summary"] + "\n")

    cl = audit.get("competitive_landscape", {})
    if cl:
        lines.append("## Competitive Landscape\n")
        for p in cl.get("patterns_across_competitors", []):
            lines.append(f"- {p}")
        bic = cl.get("best_in_class", {})
        if isinstance(bic, list):
            for item in bic:
                if isinstance(item, dict):
                    lines.append(f"\n**Best-in-class:** {item.get('source', '?')} — {item.get('element', '?')}")
                    lines.append(f"_{item.get('description', '')}_")
        elif isinstance(bic, dict) and bic:
            lines.append(f"\n**Best-in-class:** {bic.get('source', '?')} — {bic.get('element', '?')}")
            lines.append(f"_{bic.get('description', '')}_")
        for g in cl.get("market_gaps", []):
            lines.append(f"\n**Gap:** {g}")
        lines.append("")

    za = audit.get("zerg_assessment", {})
    if za:
        lines.append("## Zerg Assessment\n")
        for s in za.get("strengths", []):
            lines.append(f"+ {s}")
        for g in za.get("gaps", []):
            lines.append(f"- {g}")
        if za.get("positioning_clarity"):
            lines.append(f"\n**Positioning:** {za['positioning_clarity']}")
        for b in za.get("conversion_bottlenecks", []):
            lines.append(f"  * {b}")
        lines.append("")

    recs = audit.get("recommendations", [])
    if recs:
        lines.append("## Recommendations\n")
        for rec in recs:
            lines.append(f"### {rec.get('priority', '?')}. {rec.get('title', 'Untitled')}")
            lines.append(f"**Category:** {rec.get('category','?')} | **Effort:** {rec.get('effort','?')} | **Impact:** {rec.get('impact','?')}")
            lines.append(f"\n**Current:** {rec.get('current_state','N/A')}")
            lines.append(f"**Recommendation:** {rec.get('recommendation','N/A')}")
            lines.append(f"**Rationale:** {rec.get('rationale','N/A')}\n")

    qw = audit.get("quick_wins", [])
    if qw:
        lines.append("## Quick Wins\n")
        for w in qw:
            lines.append(f"- {w}")
        lines.append("")

    rewrites = audit.get("copy_rewrites", [])
    if rewrites:
        lines.append("## Copy Rewrites\n")
        for r in rewrites:
            lines.append(f"**{r.get('element','?')}**")
            lines.append(f"> Current: \"{r.get('current','')}\"")
            lines.append(f"> Suggested: \"{r.get('suggested','')}\"")
            lines.append(f"_{r.get('why','')}_\n")

    for s in audit.get("new_sections_to_add", []):
        lines.append(f"**Add: {s.get('section','?')}** — {s.get('rationale','')}")
        lines.append(f"  → {s.get('content_guidance','')}\n")

    report = "\n".join(lines)
    if output_path:
        output_path.write_text(report)
        print(f"\nReport saved: {output_path}")
    return report


def main():
    parser = argparse.ArgumentParser(description="Competitive landing page audit for Zerg")
    parser.add_argument("--urls", nargs="+", default=[], help="Competitor URLs to analyze")
    parser.add_argument("--zerg-urls", nargs="+", default=["https://zergai.com"])
    parser.add_argument("--insights-dir", help="Use existing JSON insights from this directory")
    parser.add_argument("--output", help="Save markdown report to file")
    parser.add_argument("--no-screenshot", action="store_true")
    args = parser.parse_args()

    take_screenshot = not args.no_screenshot
    save_dir = Path(args.insights_dir) if args.insights_dir else INSIGHTS_DIR
    save_dir.mkdir(parents=True, exist_ok=True)

    if args.insights_dir and not args.urls:
        print(f"Loading competitor insights from {save_dir}...")
        competitor_insights = load_insights_from_dir(save_dir)
    else:
        print(f"\nAnalyzing {len(args.urls)} competitor page(s)...")
        competitor_insights = run_analysis(args.urls, save_dir, take_screenshot) if args.urls else []

    print(f"\nAnalyzing {len(args.zerg_urls)} Zerg page(s)...")
    zerg_insights = run_analysis(args.zerg_urls, save_dir, take_screenshot)

    if not zerg_insights:
        print("Error: No Zerg page insights. Aborting.")
        sys.exit(1)

    audit = generate_audit(competitor_insights, zerg_insights)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = save_dir / f"audit_{ts}.json"
    json_path.write_text(json.dumps(audit, indent=2))
    print(f"Raw audit saved: {json_path}")

    output_path = Path(args.output) if args.output else None
    report = format_report(audit, output_path)
    print("\n" + report)


if __name__ == "__main__":
    main()
