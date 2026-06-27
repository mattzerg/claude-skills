---
name: programmatic-seo
description: Generate programmatic SEO content for Zerg's content engine — comparison pages (Linear vs Zergboard, Slack vs ZergChat, Calendly vs ZergCal, Otter vs ZergMeeting, Front vs ZergMail), GEO-optimized canonical explainers (what is X, how does Y work), and integration pages (Zerg + <partner>). Reads ~/Obsidian/Zerg/MattZerg/Competitive/<category>/positioning.md + competitor matrices to source claims; writes draft Markdown blog posts to ~/zerg/web/src/public/content/blog/<slug>.md with full SEO frontmatter (canonical URL, meta description, structured data). Pairs with blog-imagery (auto-generates hero) and fakematt-copyedit (voice review). Phase 2 build (Day 31–60), L effort. Pair with experiments #3 (comparison pages) + #4 (GEO explainers). USE PROACTIVELY when Matt mentions SEO, comparison pages, integration pages, "Linear vs us", AI-citation traffic, or programmatic content.
allowed-tools: Bash, Read, Write
---

# Programmatic SEO Skill (v0 stub — Phase 2 build, L effort)

Plan: `~/.claude/plans/i-am-planning-growth-splendid-bee.md`. High variance — works in 2026 ONLY with the GEO layer (AI citation optimization) doing real work. If LLM-citation traffic doesn't materialize, RICE drops ~40%.

## Status

**v0 stub — not yet implemented.** Phase 2 Day 31–60 build window. L effort.

## Three modes

### comparison — generate "X vs Zerg" pages

```bash
python3 ~/.claude/skills/programmatic-seo/run.py comparison \\
  --competitor linear --zerg-product zergboard
```

Reads `~/Obsidian/Zerg/MattZerg/Competitive/pm-software/positioning.md` + `differentiation-opportunities.md` for source claims. Outputs `~/zerg/web/src/public/content/blog/linear-vs-zergboard.md` with:
- H1: "Linear vs Zergboard" (target keyword)
- Honest tradeoffs section (per `feedback_idan_pr_review_bar.md` — show where competitor wins)
- Pricing comparison table
- Migration guide section (CTA)
- Schema.org markup for comparison content

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

### integration — generate "Zerg + <partner>" pages

```bash
python3 ~/.claude/skills/programmatic-seo/run.py integration --partner anthropic-claude-code
```

For each BD partner (per `Growth/bd-targets.md`), generate a co-marketing-ready integration page. Phase 3 deliverable: 5 integration pages from converted partner conversations.

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
- File-based; output lands in `~/zerg/web/src/public/content/blog/`
