---
name: competitive-review-skill
description: Run a structured competitive review of a product category against a Zerg product. Scrapes competitors across landing/pricing/changelog/docs/G2/Reddit, builds a feature matrix, classifies gaps into 4 buckets (table stakes / differentiator parity / whitespace / we-have-they-don't), reconciles spec-vs-live drift, and emits an Obsidian competitive note + positioning brief + landing-page-skill handoff JSON + proposed Zergboard cards. USE PROACTIVELY when the user mentions reviewing or comparing a product category, asks "what does <competitor> do" or "how do other <X> handle Y", talks about building a feature/product where competitor context would help, says "alternatives to" / "competitive landscape" / "what's the <category> ecosystem", or mentions a known competitor in product context. Always confirm the candidate competitor list with the user before scraping; always confirm proposed Zergboard cards before creating them.
allowed-tools: Bash, Read, Write
---

# Competitive Review Skill

Reusable skill for running a category-level competitive review against a Zerg product. Modeled after `landing-page-skill` (its product-level sibling) — both share the Playwright + Claude-CLI subprocess pattern.

## When to invoke

Run when the user wants to understand a product category vs. a Zerg product. Strong triggers:

- "Review <category> for <Zerg product>" / "compare us to X"
- "What does <competitor> do" / "how does <competitor> handle Y"
- "We're thinking about building <feature>" — competitive context likely useful
- "Alternatives to X" / "competitive landscape" / "<category> ecosystem"
- Standalone competitor name dropped in product/strategy context

When in doubt, suggest running it — Matt can decline.

## Phase flow (with confirmation gates)

1. **discover** — find candidate competitors for the category, merge with any user-supplied seeds, present list. **STOP, await confirmation.** User can add/remove.
2. **priors** — auto-detect prior competitive audits in `~/Obsidian/Zerg/MattZerg/Conversations/Claude/` matching category or competitors; summarize as priors.
3. **scan** — for each confirmed competitor, scrape 6 source types (landing, pricing, changelog, docs/integrations, G2/Capterra, Reddit/HN). Save raw JSON to `insights/`.
4. **compare** — read `~/Obsidian/Zerg/MattZerg/Projects/Zstack/<Product>.md` AND scrape its live URL. Reconcile into Us(spec)+Us(live) columns. Build feature matrix. Classify each gap into 4 buckets.
5. **rank** — present top-10 gaps; ask user to tag strategic fit (1–5) and rough cost (S/M/L). Compute `freq × fit ÷ cost`, sort.
6. **drift** — diff Us(spec) vs Us(live); list mismatches.
7. **report** — write all outputs to `~/Obsidian/Zerg/MattZerg/Competitive/<category>/`. Emit `landing-page-skill/insights/competitive_<category>_<ts>.json` handoff.
8. **diff** — if `archive/` has a prior run, compute "what changed" header.
9. **cards** — propose Zergboard cards for top-N gaps + drift. **STOP, await per-card or batch confirmation.** Create via zergboard-skill CLI with bracketed lane prefixes.

## Default invocation

```bash
python3 ~/.claude/skills/competitive-review-skill/competitive_review.py \
  <category-slug> --product <ZergProduct> [seed1.com seed2.com ...]
```

Walks all phases. Each phase script callable independently for re-runs:

```bash
python3 ~/.claude/skills/competitive-review-skill/discover.py <category> [seeds...]
python3 ~/.claude/skills/competitive-review-skill/scan.py <competitor-url>
python3 ~/.claude/skills/competitive-review-skill/compare.py <category> --product <ZergProduct>
python3 ~/.claude/skills/competitive-review-skill/rank.py <category>
python3 ~/.claude/skills/competitive-review-skill/report.py <category> --product <ZergProduct>
python3 ~/.claude/skills/competitive-review-skill/cards.py <category> [--board UUID]
```

## Output

```
~/Obsidian/Zerg/MattZerg/Competitive/<category>/
  index.md         # YAML frontmatter + "What changed" + top findings + links
  matrix.md        # full feature matrix (markdown table)
  gaps.md          # 4-bucket gap analysis, top-10 ranked with fit/cost
  positioning.md   # differentiator one-liners + headline/subhead candidates
  drift.md         # spec ↔ site mismatches (only if any)
  competitors/<name>.md   # per-competitor deep notes
  archive/YYYY-MM-DD/     # prior runs preserved
```

Plus:
- `~/.claude/skills/competitive-review-skill/insights/<competitor>_<ts>.json` — raw scrape per competitor
- `~/.claude/skills/landing-page-skill/insights/competitive_<category>_<ts>.json` — handoff to landing-page-skill audit

## Conventions

- Vault root: `~/Obsidian/Zerg/MattZerg`
- Product specs: `Projects/Zstack/<Product>.md` (frontmatter has `fly_app` → live URL is `https://<fly_app>.fly.dev`)
- Marketing board UUID: `7bf7ab2a-ac70-4b29-85bf-74a6db6a0760` (fallback for gap cards if product lacks own board)
- Website board UUID: `8ef863c1-765f-493e-8622-2e65b4d2ca61`
- Zergboard cards: prefix titles with bracketed lane (`[Content]`, `[Launches]`, `[Channels]`, `[Brand & Site]`, `[Pipeline]`, `[Measurement]`, `[Infra]`, `[Tools]`)
- Pricing pages are scraped for **feature signal**, not for a pricing matrix output (Zerg undercuts on price; pricing matrix is intentionally not produced)

## Requirements

- `pip install beautifulsoup4 playwright`
- `playwright install chromium`
- `~/.local/bin/claude` (Claude CLI) for subprocess analysis calls
- `~/.claude/skills/zergboard-skill/config.json` with `api_token` for card creation

Run `bash verify.sh` to smoke-test imports, vault paths, dependencies, and the offline pieces of the pipeline. It does not call Claude or scrape sites — those happen in real runs.

## Known limitations

- **Reddit signal is best-effort.** Reddit blocks bot-like queries (subreddit operators 403); the simple search returns broad results that often include unrelated hits. The skill still includes them but Claude downstream filters noise. HN signal (via Algolia) and G2 reviews are the stronger sentiment sources.
- **Pricing matrix is intentionally not produced.** Pricing pages are scraped for feature signal only. Per design decision: Zerg undercuts on price, so a pricing-tier table doesn't drive product decisions.
- **`claude --tools ""` is required** in `lib/claude.py` to prevent the Claude CLI subprocess from invoking other tools during analysis (would explode latency and cost).
