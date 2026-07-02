---
name: landing-page-skill
description: Analyze competitor/reference landing pages, audit Zerg pages against them, and generate new landing pages matching Zerg's design system. Different from webpage-layout (data-driven 6-axis SCORING of personal/agency/fund/product sites) — landing-page-skill is for analyzing references + auditing + GENERATING Zerg's own marketing pages.
commands:
- analyze
- audit
- build
---


# Landing Page Skill

Three scripts for the full landing page workflow: research → audit → build.

## analyze.py — Research any landing page

Screenshots, scrapes, and sends to Claude for structured insights (headline, value prop, CTAs, social proof, design patterns, scores).

```bash
# Analyze one or more competitor pages
/usr/bin/python3 ~/.claude/skills/landing-page-skill/analyze.py https://cursor.com https://devin.ai

# Skip screenshots (faster, text-only)
/usr/bin/python3 ~/.claude/skills/landing-page-skill/analyze.py https://lovable.dev --no-screenshot

# Save to custom dir
/usr/bin/python3 ~/.claude/skills/landing-page-skill/analyze.py https://replit.com --save ~/Desktop/insights
```

Saves JSON to `~/.claude/skills/landing-page-skill/insights/`.

## audit.py — Competitive gap analysis for Zerg

Compares competitor pages against Zerg's live pages. Produces a ranked recommendation report.

```bash
# Full pipeline: analyze competitors + Zerg homepage, generate report
/usr/bin/python3 ~/.claude/skills/landing-page-skill/audit.py \
  --urls https://cursor.com https://devin.ai https://lovable.dev \
  --zerg-urls https://zergai.com https://zergai.com/products/ztc \
  --output ~/Desktop/zerg-audit.md

# Use existing insights (skip re-fetching)
/usr/bin/python3 ~/.claude/skills/landing-page-skill/audit.py \
  --insights-dir ~/.claude/skills/landing-page-skill/insights \
  --zerg-urls https://zergai.com
```

Output: executive summary, competitive landscape patterns, ranked recommendations, copy rewrites, quick wins.

## build.py — Generate landing pages

Generates Nuxt/Vue pages matching Zerg's design system, informed by competitive insights.

```bash
# Build a new ZTC product page (Nuxt .vue)
/usr/bin/python3 ~/.claude/skills/landing-page-skill/build.py \
  "ZTC: AI terminal for serious engineering teams. Emphasize speed, agent autonomy, and terminal-native workflow." \
  --product ztc \
  --insights-dir ~/.claude/skills/landing-page-skill/insights

# Write directly into the Zerg web repo
/usr/bin/python3 ~/.claude/skills/landing-page-skill/build.py \
  "ZTC product page" --product ztc --write-to-repo

# Generate standalone HTML (for quick review, no Nuxt needed)
/usr/bin/python3 ~/.claude/skills/landing-page-skill/build.py \
  "Zerg Cloud landing page" --product cloud --html --output ~/Desktop/
```

Products: `ztc`, `zde`, `zergboard`, `cloud`, `zerg`

## Typical workflow

```bash
# 1. Research competitors
/usr/bin/python3 ~/.claude/skills/landing-page-skill/analyze.py \
  https://cursor.com https://devin.ai https://lovable.dev https://replit.com

# 2. Run competitive audit vs Zerg
/usr/bin/python3 ~/.claude/skills/landing-page-skill/audit.py \
  --insights-dir ~/.claude/skills/landing-page-skill/insights \
  --zerg-urls https://zergai.com \
  --output ~/zerg-audit-$(date +%Y%m%d).md

# 3. Build an improved page
/usr/bin/python3 ~/.claude/skills/landing-page-skill/build.py \
  "Improved Zerg homepage based on competitive audit" \
  --product zerg --html --output ~/Desktop/
```

## Environment

Requires:
- `ANTHROPIC_API_KEY` env var (or `~/.claude/config.json` with `anthropic_api_key`)
- `pip install anthropic beautifulsoup4 playwright pillow`
- `playwright install chromium` (for screenshots)

Insights are saved to `~/.claude/skills/landing-page-skill/insights/` and accumulate over time.
