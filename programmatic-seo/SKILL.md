---
name: programmatic-seo
description: Generate programmatic SEO content for Zerg's content engine. Routes by SCOPE (see project_zerg_content_routing.md) — single-product comparison/integration pages go to the product site (`~/zerg/<product>/public/content/compare/<slug>.md` or `.../integrations/<slug>.md`); multi-product / category / brand explainers stay on zergai (`~/zerg/web/src/public/content/blog/<slug>.md`). Reads MattZerg/Competitive/<category>/positioning.md + competitor matrices to source claims. Pairs with blog-imagery (hero) and fakematt-copyedit (voice review). Phase 2 build (Day 31–60), L effort.
allowed-tools: Bash, Read, Write
---


# Programmatic SEO Skill (v0 stub — Phase 2 build, L effort)

Plan: `~/.claude/plans/i-am-planning-growth-splendid-bee.md`. High variance — works in 2026 ONLY with the GEO layer (AI citation optimization) doing real work. If LLM-citation traffic doesn't materialize, RICE drops ~40%.

## Status

**v0 stub — not yet implemented.** Phase 2 Day 31–60 build window. L effort.

## Three modes

### comparison — generate "X vs <product>" pages (writes to PRODUCT site)

```bash
python3 ~/.claude/skills/programmatic-seo/run.py comparison \\
  --competitor linear --zerg-product zergboard
```

Reads `MattZerg/Competitive/pm-software/positioning.md` + `differentiation-opportunities.md` for source claims. Writes `~/zerg/zergboard/public/content/compare/linear.md` (slug is just the competitor — context comes from the `/compare/<slug>` route). Canonical URL: `https://zergboard.com/compare/linear`.

Per the routing rule (`project_zerg_content_routing.md`): single-product content goes to the product site, NOT zergai. Comparison pages always sell ONE product, so they always route to that product. Each product has its own `compare/[slug]` route + `constants/compare/<slug>.ts` metadata file — Matt or Claude wires the metadata after scaffolding.

Generated body includes:
- Honest tradeoffs section (per `feedback_idan_pr_review_bar.md` — show where competitor wins)
- Pricing comparison table
- Migration guide section (CTA)
- FAQ section (FAQPage schema rendered by the route)

Phase 2 deliverable: 5 comparison pages (Linear, Asana, Trello, Slack, Calendly).

### explainer — generate GEO-optimized canonical explainers

```bash
python3 ~/.claude/skills/programmatic-seo/run.py explainer \\
  --topic "what is agent-native project management" --target ai-citation
```

Outputs `~/zerg/web/src/public/content/blog/<slug>.md` structured for AI assistant citation:
- Definition-first opener (under 100 words)
- Bulleted summary (LLM-extractable)
- Q&A section (FAQ schema)
- Sources cited (boost for Perplexity)

Phase 2 deliverable: 5 GEO explainers ("what is X" / "how does Y work" topics from competitive matrix whitespace gaps).

### integration — generate partner integration pages (routes by scope)

```bash
# Single-product integration → product site (e.g. Trello import on Zergboard).
python3 ~/.claude/skills/programmatic-seo/run.py integration \\
  --partner trello --zerg-product zergboard
# → ~/zerg/zergboard/public/content/integrations/trello.md
# → canonical https://zergboard.com/integrations/trello

# Multi-product / brand-level integration → zergai blog (e.g. "Zerg + Anthropic" cross-stack story).
python3 ~/.claude/skills/programmatic-seo/run.py integration --partner anthropic-claude-code
# → ~/zerg/web/src/public/content/blog/zerg-and-anthropic-claude-code.md
# → canonical https://zergai.com/blog/zerg-and-anthropic-claude-code
```

Omit `--zerg-product` for multi-product / brand-level integration stories. Include it for single-product partner integration pages. For each BD partner (per `Growth/bd-targets.md`), generate a co-marketing-ready integration page. Phase 3 deliverable: 5 integration pages from converted partner conversations.

## SEO discipline

- **Every page** has canonical URL, meta description (≤160 chars), OG card via `blog-imagery`, structured data (Article + FAQ where applicable)
- **GEO layer**: definition-first openers, bulleted summaries, sources cited inline (not as footer-only) — these earn LLM citations
- **No thin content**: each page minimum 800 words of real, sourced content. Refuses to scaffold below this threshold
- **No keyword stuffing**: Matt's writing voice (`fakematt-copyedit`) enforced

## Pairs with

- `blog-imagery` for hero + share cards
- `fakematt-copyedit` for voice review
- `competitive-review-skill` for source claims
- `landing-page-skill` for the landing-page version of the same content
- `content-distribution` for the 14-surface distribution playbook (every pSEO post runs through it)

## Build phases

- **Phase 2 Day 31–45:** v0 — `comparison` mode + 5 pages shipped
- **Phase 2 Day 45–60:** v0.1 — `explainer` mode + 5 pages shipped
- **Phase 2 Day 60–90:** v0.2 — engagement read-back; what's earning AI citations? what's earning organic? Kill or scale per page
- **Phase 3 Day 91–180:** v1 — `integration` mode for converted partnerships; monthly batch of 20 pages if pSEO motion shows fit

## Implementation notes

- Heavy use of Claude API (similar to `case-study-skill` `scaffold` mode) for content generation
- Reads vault competitive briefs as ground truth; refuses claims not in source material
- Routes through `content-distribution` for distribution after publish
- File-based; output lands in `~/zerg/<product>/public/content/{compare,integrations}/<slug>.md` for single-product pages, or `~/zerg/web/src/public/content/blog/<slug>.md` for multi-product / category content. See `project_zerg_content_routing.md`.
- After scaffolding a comparison/integration page on a product site, the metadata TS file (`constants/<compare|integrations>/<slug>.ts`) needs to be created and registered in `constants/<dir>/index.ts`. v0.1 will auto-emit this; for now do it by hand (mirror an existing entry like `zergboard/constants/compare/trello.ts`).
