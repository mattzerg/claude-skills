---
name: webpage-layout
description: Empirical webpage-layout review. Scrapes a curated reference-site corpus (operator/VC/consultancy/product), grades on 6-axis rubric (8+ = exemplar). Two modes — `learn` (scrape + grade corpus) and `audit` (grade target URL, severity-tagged findings + recipes from top exemplars). Different from website-designer (static anti-patterns) + landing-page-skill (generates Zerg pages). USE PROACTIVELY before declaring a personal/agency/fund site done — pairs with website-designer, fakematt-feedback, graphic-layout.
allowed-tools: Bash, Read, Write
---


# Webpage Layout Skill

Empirical sibling to `website-designer`. Where website-designer enforces hard rules (no animated blobs, no Inter+Fraunces stencil), this skill **learns** from a corpus of real sites graded on quality.

## Anchors

This skill draws its voice and pattern catalog from:

- **Voice fingerprint:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/matt_considered_voice.md`
- **Pattern catalog:** `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/feedback_patterns_catalog.md`
- **Domain corpus:** existing 6-axis rubric + reference corpus (this skill's `corpus/references.json` + `state/learned/patterns.md`); cross-reference `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/ui_density_feedback_corpus.md` for density/whitespace findings
- **Catalog patterns to cite by slug** (Section B UI / product design): ia-ordering, main-sticking-action, ui-weight-vs-importance, density-vs-padding, smart-defaults
- **Catalog patterns to cite by slug** (Section E CRO / marketing): hero-clarity, missing-cta
- **Catalog patterns to cite by slug** (Section G Viz / video): scorecard-deltas, action-title

Read these BEFORE producing output. Cite patterns by slug from the catalog.

## Why this exists

`website-designer` knows what to avoid (anti-patterns). This skill knows **what good looks like** by actually grading reference sites and extracting their winning patterns. Built 2026-05-07 after Matt called out that I was giving up on accomplishable searches and not doing data-driven work.

## Visual richness recipes — the "make it more eye-catching" library

`recipes/visual-richness.md` is the durable lookup-table for boldness lifts (full-bleed gradient bands, big-number pull-quotes, animated SVG marks, scroll fade-ins, gradient mesh halos, color-rich hovers, drop-cap shimmer, ornaments, currently sidebars). Each recipe carries: corpus exemplar URLs + ready-to-paste CSS + brand-token mapping (matteisn / vang / zerg) + WCAG/edge-case gotchas.

When asked to make a site "more eye-catching" / "less simple" / "bolder", **read this file first** — don't reinvent. Apply recipes in priority order from the "When to apply which" symptom→recipe table at the bottom.

The full R1–R10 playbook is in production on matteisn.com / vang.capital / vangadvisory.com (deployed 2026-05-08) — those sites' CSS is a working reference implementation.

**Rubric caveat**: the existing 6-axis rubric (typography/hierarchy/distinctiveness/color/density/voice) optimizes for editorial cleanness — Linear scores 4.7, Mercury 3.2, even though they're the canonical bold-and-motion-rich references. The `design_forward` corpus class (`mercury.com`, `linear.app`, `framer.com`, `vercel.com`, `mercury.com`, `ramp.com`, `raycast.com`, `runwayml.com`, `stripe.com`, etc.) is for visual-richness reference, NOT score comparison. Treat scores in that class as orthogonal to the rubric.

## Modes

### `learn`

```bash
python3 ~/.claude/skills/webpage-layout/run.py learn
```

Walks every URL in `corpus/references.json`, screenshots desktop + mobile, fetches HTML, and grades each on the 6-axis rubric using Claude vision. Writes per-site grades to `state/sites/<slug>/grade.json` and a roll-up of winning patterns to `state/learned/patterns.md`.

Re-running re-scrapes (with mtime check; skips already-graded unless `--force`).

### `audit`

```bash
python3 ~/.claude/skills/webpage-layout/run.py audit <url> [--persona personal|fund|advisory]
```

Screenshots the target, runs the same 6-axis rubric, and emits findings:
- Per-axis score + reasoning
- HIGH/MED/LOW findings with concrete fix recipes
- Comparison snippet from top-scoring exemplars in the same persona class
- Pass/fail signal at the top (FAIL if any axis < 6, WARN if avg < 7)

Output: `state/audits/<host>-<timestamp>.md`

## Rubric (6 axes, 1–10)

1. **Typographic identity** — Does the type system have character? Is it the AI-stencil Inter+Fraunces, or something with more discipline?
2. **Hierarchical clarity** — One thing dominates per screen? Headline weight + size do work?
3. **Distinctiveness** — Could you swap the words and have it read as a different person/firm? If yes, low score.
4. **Color discipline** — Restrained palette? Accent ≤ 5% of pixels? Or busy/decorative?
5. **Density/whitespace** — Confident content density? Or generic 96px-everywhere padding?
6. **Voice/structure fit** — Does the IA reflect the person/firm's actual story? Or stencil "Currently / Selected / Testimonials / CTA"?

## Reference corpus

Curated by persona class in `corpus/references.json`. Seed list:

- **Personal (operator/investor)**: frankchimero.com, jasonsantamaria.com, robinrendle.com, elad.com, naval.com, cdixon.org, paulgraham.com, sahillavingia.com, harshjv.com
- **VC fund**: benchmark.com, foundersfund.com, sparkcapital.com, usv.com, generalcatalyst.com, thrive.com
- **Advisory/consultancy**: pentagram.com, thoughtbot.com, workandco.com, high-resolution.studio
- **Brand-strong product**: linear.app, stripe.com, vercel.com, mercury.com

Add new URLs by editing `corpus/references.json`. Re-run `learn` to grade them.

## Output format

Audit output is a markdown file with:
- Verdict (PASS / WARN / FAIL)
- Per-axis grade + 2-line reasoning
- Findings table — severity / axis / fix recipe / exemplar reference
- Distinctiveness diff vs. top exemplar in the same class

## Pair with

- `website-designer` (anti-pattern catch) — runs first, hard-fails on stencil
- `webpage-layout` (this) — empirical grading + pattern recommendations
- `fakematt-feedback` (UX/IA/heuristics) — runs after layout to catch interaction issues
- `graphic-layout` (composition) — for individual rendered images

Ship requires all four to clear.

## Files

- `corpus/references.json` — URLs by persona class
- `state/sites/<slug>/` — one folder per scraped site (html + screenshots + grade.json)
- `state/learned/patterns.md` — extracted winning patterns by class (rebuilt by `learn`)
- `state/audits/<host>-<ts>.md` — per-audit findings
