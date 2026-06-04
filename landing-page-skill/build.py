#!/usr/bin/env python3
"""
Landing Page Builder — generate Nuxt/Vue landing pages matching Zerg's design system,
or standalone HTML, informed by competitive insights.
Uses the Claude Code CLI (claude --print) — no separate API key needed.

Usage:
    python3 build.py "ZTC: AI terminal for serious engineering teams" --product ztc
    python3 build.py "ZDE landing page" --insights-dir ./insights --product zde
    python3 build.py "Zerg homepage refresh" --product zerg --html --output ~/Desktop/
    python3 build.py "ZTC product page" --product ztc --write-to-repo

Options:
    --product NAME          ztc, zde, zergboard, cloud, zerg
    --insights-dir DIR      Directory of JSON insights to inform the build
    --html                  Generate standalone HTML instead of Nuxt .vue
    --write-to-repo         Write directly to ~/zerg/web/src/pages/products/{product}.vue
    --output DIR            Output directory (default: ./output)
    --brief-file FILE       Read brief from file
"""

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

SKILL_DIR = Path(__file__).parent
ZERG_WEB = Path.home() / "zerg" / "web" / "src" / "pages"
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
                "claude-sonnet-4-6", task_kind="draft-prose", caller="landing-page-build",
                quality_floor="medium",
            )
        except ImportError:
            _ROUTED_MODEL = "claude-sonnet-4-6"
    return _ROUTED_MODEL


ZERG_DESIGN_SYSTEM = """
## Zerg Design System

### Colors (Tailwind)
- Background: bg-[#f4f0e7] (warm cream/beige)
- Dark: text-[#111514] / bg-[#111514]
- Muted: text-[#41504c] / text-[#6b766f]
- Accent orange: text-[#b3662f] / text-[#d57a32] / bg-[#d57a32]
- Card bg: bg-[#fffaf0]
- Border: border-[#111514]/10 or /15 or /30

### Typography
- Hero headline: font-black uppercase tracking-[-0.035em] leading-[0.98] text-[clamp(2.9rem,5.8vw,5.6rem)] text-[#111514]
- Eyebrow labels: font-mono text-xs uppercase tracking-[0.42em] text-[#b3662f]
- Body: text-xl leading-8 text-[#41504c]
- Section headings: font-bold uppercase text-[#111514]

### Layout
- Outer: mx-auto max-w-7xl px-6 lg:px-8
- Two-col hero: grid lg:grid-cols-[1.02fr_0.98fr] gap-16 items-end

### Buttons
- Primary: border border-[#111514] bg-[#111514] px-6 py-4 font-mono text-xs uppercase tracking-[0.24em] text-[#f4f0e7] transition hover:bg-[#d57a32] hover:text-[#111514]
- Secondary: border border-[#111514]/30 px-6 py-4 text-center font-mono text-xs uppercase tracking-[0.24em] text-[#111514] transition hover:border-[#111514] hover:bg-[#fffaf0]

### Cards
- rounded-[2rem] border border-[#111514]/15 bg-[#fffaf0]/80 p-5 shadow-[0_30px_80px_rgba(17,21,20,0.14)] backdrop-blur

### Background texture
- bg-[linear-gradient(90deg,rgba(17,21,20,0.06)_1px,transparent_1px),linear-gradient(0deg,rgba(17,21,20,0.06)_1px,transparent_1px)] bg-[size:48px_48px]

### Nuxt conventions
- <script setup lang="ts">
- NuxtLink for internal routes
- No external CSS beyond Tailwind
- lucide-vue-next for icons if needed
"""

PRODUCT_CONTEXTS = {
    "ztc": "ZTC (Zerg Terminal Code) — Claude Code-style terminal UI for autonomous agent-driven development. Target: senior engineers and DevEx teams who live in the terminal.",
    "zde": "ZDE (Zerg Development Environment) — web-based IDE with integrated AI agents. Target: engineering teams wanting AI pair programming at scale.",
    "zergboard": "Zergboard — AI-powered project management where agents create, update, and close tickets autonomously. Target: engineering managers and CTOs.",
    "cloud": "Zerg Cloud — hosted Zerg platform with multi-tenant workspaces, billing, and team collaboration. Target: teams who want Zerg without self-hosting.",
    "zerg": "Zerg Core — open-source autonomous agent framework. Target: platform engineers and AI researchers.",
}

NUXT_PROMPT = """You are a senior frontend engineer building a Nuxt 3 / Vue 3 / Tailwind CSS landing page for Zerg AI.

## Brief
{brief}

## Product Context
{product_context}

{design_system}

## Competitive Insights
{insights_summary}

## Requirements
1. Complete, production-ready Nuxt .vue file
2. Use <script setup lang="ts">
3. Follow the Zerg design system EXACTLY
4. Sections: Hero → Value Props/Features → Social Proof/Use Cases → CTA
5. Mobile-responsive (lg: breakpoints)
6. Realistic placeholder copy informed by brief and competitive insights
7. No external dependencies beyond what's in the design system
8. Premium, technical aesthetic — not generic SaaS

Return ONLY the .vue file content. No explanation, no markdown fences."""

HTML_PROMPT = """You are a senior frontend engineer building a standalone HTML landing page for Zerg AI.

## Brief
{brief}

## Product Context
{product_context}

{design_system}

## Competitive Insights
{insights_summary}

## Requirements
1. Complete, self-contained HTML file with embedded CSS (use CSS variables matching Zerg design)
2. Sections: Hero → Features/Value Props → Social Proof → CTA
3. Mobile-responsive
4. Premium, technical aesthetic
5. Realistic persuasive copy

Return ONLY the HTML file content. No explanation, no markdown fences."""


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


def strip_preamble(content: str, file_starts: list[str]) -> str:
    """Strip any text before the first occurrence of a known file start marker."""
    for marker in file_starts:
        idx = content.find(marker)
        if idx != -1:
            return content[idx:]
    return content


def load_insights_summary(insights_dir: Path, max_chars: int = 6000) -> str:
    summaries = []
    for f in sorted(insights_dir.glob("*.json")):
        if f.name.startswith("audit_"):
            continue
        try:
            data = json.loads(f.read_text())
            summary = {
                "company": data.get("company", f.stem),
                "tagline": data.get("tagline"),
                "value_proposition": data.get("value_proposition"),
                "primary_cta": data.get("primary_cta"),
                "standout_elements": data.get("standout_elements", [])[:3],
                "design_patterns": data.get("design_patterns", {}),
                "features": data.get("features", [])[:5],
            }
            summaries.append(json.dumps(summary))
        except Exception:
            pass
    combined = "\n---\n".join(summaries)
    return combined[:max_chars] if combined else "No competitive insights available."


def build_page(brief: str, product: str, insights_summary: str, html_mode: bool) -> str:
    product_context = PRODUCT_CONTEXTS.get(product, product or "Zerg AI product")
    template = HTML_PROMPT if html_mode else NUXT_PROMPT
    prompt = template.format(
        brief=brief,
        product_context=product_context,
        design_system=ZERG_DESIGN_SYSTEM,
        insights_summary=insights_summary
    )
    print("Generating landing page with Claude...")
    content = call_claude(prompt)
    # Strip any accidental markdown fences
    content = re.sub(r'^```(?:html|vue)?\n?', '', content)
    content = re.sub(r'\n?```$', '', content)
    # Strip any preamble before the actual file start
    if html_mode:
        content = strip_preamble(content, ["<!DOCTYPE", "<html"])
    else:
        content = strip_preamble(content, ["<template>", "<script"])
    return content.strip()


def main():
    parser = argparse.ArgumentParser(description="Build Zerg landing pages with Claude")
    parser.add_argument("brief", nargs="?", help="Page brief")
    parser.add_argument("--brief-file", help="Read brief from file")
    parser.add_argument("--product", choices=list(PRODUCT_CONTEXTS.keys()) + [""], default="")
    parser.add_argument("--insights-dir", help="Directory of competitive insight JSON files")
    parser.add_argument("--html", action="store_true", help="Generate standalone HTML")
    parser.add_argument("--write-to-repo", action="store_true",
                        help="Write to ~/zerg/web/src/pages/products/{product}.vue")
    parser.add_argument("--output", default=str(SKILL_DIR / "output"))
    args = parser.parse_args()

    brief = args.brief
    if args.brief_file:
        brief = Path(args.brief_file).read_text().strip()
    if not brief:
        print("Error: Provide a brief as argument or via --brief-file")
        sys.exit(1)

    insights_dir = Path(args.insights_dir) if args.insights_dir else SKILL_DIR / "insights"
    insights_summary = load_insights_summary(insights_dir) if insights_dir.exists() else "No competitive insights."

    content = build_page(brief, args.product, insights_summary, args.html)

    ext = "html" if args.html else "vue"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = args.product or "page"

    if args.write_to_repo and args.product and not args.html:
        out_path = ZERG_WEB / "products" / f"{args.product}.vue"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if out_path.exists():
            backup = out_path.with_suffix(f".backup_{ts}.vue")
            backup.write_text(out_path.read_text())
            print(f"Backed up: {backup.name}")
    else:
        out_dir = Path(args.output)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{slug}_{ts}.{ext}"

    out_path.write_text(content)
    print(f"\nPage saved: {out_path}")
    print(f"Size: {len(content):,} chars")

    if args.html:
        print(f"Open: open \"{out_path}\"")


if __name__ == "__main__":
    main()
